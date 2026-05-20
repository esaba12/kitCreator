"""Query-based sub-instrument separation via Banquet (kwatcharasupat/query-bandit)."""
from __future__ import annotations

import contextlib
import io
import logging
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

_BANQUET_DIR = Path("~/.cache/kitforge/banquet").expanduser()
_REPO_DIR = _BANQUET_DIR / "repo"
_WEIGHTS_PATH = _BANQUET_DIR / "ev-pre-aug.ckpt"
_ZENODO_URL = "https://zenodo.org/records/13694558/files/ev-pre-aug.ckpt?download=1"

# Banquet stem names for each instrument alias
_STEM_MAP: dict[str, str] = {
    "guitar":           "clean_electric_guitar",
    "electric guitar":  "clean_electric_guitar",
    "acoustic guitar":  "acoustic_guitar",
    "piano":            "grand_piano",
    "keys":             "grand_piano",
    "keyboard":         "grand_piano",
    "electric piano":   "electric_piano",
    "rhodes":           "electric_piano",
    "synth":            "synth_lead",
    "lead synth":       "synth_lead",
    "synth lead":       "synth_lead",
    "lead":             "synth_lead",
    "pad":              "synth_pad",
    "organ":            "organ_electric_organ",
    "bass":             "bass_guitar",
    "bass guitar":      "bass_guitar",
    "808":              "bass_synthesizer",
    "bass synthesizer": "bass_synthesizer",
}

_BANQUET_VERSION = "1.0"
_old_config_root: str | None = None


def is_available() -> bool:
    if not _REPO_DIR.exists() or not _WEIGHTS_PATH.exists():
        return False
    # A valid PyTorch checkpoint (zip) must be > 500 MB; reject truncated downloads
    return _WEIGHTS_PATH.stat().st_size > 500 * 1024 * 1024


def setup(download_weights: bool = True) -> None:
    """Clone repo, install Python deps, optionally download weights."""
    from rich.console import Console
    console = Console()

    if not _REPO_DIR.exists():
        console.print("  Cloning query-bandit repo...")
        _REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git", "clone", "--depth=1",
                "https://github.com/kwatcharasupat/query-bandit.git",
                str(_REPO_DIR),
            ],
            check=True,
        )
        console.print("  [green]Repo cloned[/green]")

    _ensure_deps(console)

    if _WEIGHTS_PATH.exists():
        console.print("  [green]Weights already present[/green]")
    elif download_weights:
        console.print("  Downloading Banquet weights (~646 MB)...")
        _download_weights(console)
    else:
        console.print(
            f"\n  [yellow]Download weights manually:[/yellow]\n"
            f"  wget '{_ZENODO_URL}' -O {_WEIGHTS_PATH}"
        )


def separate(
    audio_path: Path,
    query_wav_path: Path,
    out_path: Path,
    instrument: str,
    batch_size: int = 4,
) -> Path:
    """
    Separate one instrument from a mixture using Banquet query-based separation.

    audio_path:      mixture WAV (original song or mix at any SR)
    query_wav_path:  10-second reference clip of the target instrument
    out_path:        where to write the separated stem
    instrument:      key into _STEM_MAP (e.g. "guitar", "piano", "lead synth")
    batch_size:      chunks processed simultaneously; 4 is safe on Apple Silicon MPS
    """
    if not is_available():
        raise RuntimeError(
            "Banquet not set up. Call query_separator.setup() first, "
            "or run 'kitforge setup-banquet'."
        )

    _ensure_deps()
    stem_name = _STEM_MAP.get(instrument.lower().strip(), "clean_electric_guitar")

    _add_repo_to_path()
    _push_config_root()
    try:
        _infer(audio_path, query_wav_path, out_path, stem_name, batch_size)
    finally:
        _pop_config_root()

    return out_path


# ── internal helpers ──────────────────────────────────────────────────────────

def _add_repo_to_path() -> None:
    repo_str = str(_REPO_DIR)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)


def _push_config_root() -> None:
    global _old_config_root
    _old_config_root = os.environ.get("CONFIG_ROOT")
    os.environ["CONFIG_ROOT"] = str(_REPO_DIR / "config")


def _pop_config_root() -> None:
    global _old_config_root
    if _old_config_root is None:
        os.environ.pop("CONFIG_ROOT", None)
    else:
        os.environ["CONFIG_ROOT"] = _old_config_root


def _load_banquet_config():
    from omegaconf import OmegaConf
    config_path = _REPO_DIR / "expt" / "bandit-everything-test.yml"
    raw = OmegaConf.load(str(config_path))
    merged = {}
    for k, v in raw.items():
        merged[k] = OmegaConf.load(v) if isinstance(v, str) and v.endswith(".yml") else v
    return OmegaConf.merge(merged)


def _infer(
    audio_path: Path,
    query_wav_path: Path,
    out_path: Path,
    stem_name: str,
    batch_size: int,
) -> None:
    import warnings
    import torch
    import torchaudio as ta
    from omegaconf import OmegaConf

    MODEL_FS = 44100
    QUERY_SAMPLES = MODEL_FS * 10
    # chunked_inference requires audio longer than chunk + 4*overlap
    # chunk=6s, hop=0.5s → min ≈ 28s at 44.1kHz
    MIN_DURATION_SAMPLES = int(28 * MODEL_FS)

    # Quick pre-check duration before loading the full model (librosa handles all formats)
    import librosa
    duration_s = librosa.get_duration(path=str(audio_path))
    if int(duration_s * MODEL_FS) < MIN_DURATION_SAMPLES:
        raise ValueError(
            f"Audio is too short for Banquet (need ≥28s, got {duration_s:.1f}s)"
        )

    # Suppress verbose hear21passt / pytorch_lightning console output during setup
    _devnull = open(os.devnull, "w")
    _old_out, _old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = _devnull
    logging.disable(logging.CRITICAL)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from core.models.ebase import EndToEndLightningSystem
            from core.models.e2e.bandit.bandit import PasstFiLMConditionedBandit
            from core.losses.base import BaseLossHandler
            from core.losses.l1snr import L1SNRLoss
            from core.metrics.base import MultiModeMetricHandler, BaseMetricHandler
            from core.metrics.snr import SafeSignalNoiseRatio
            import torchmetrics as tm

            config = _load_banquet_config()
            config.data.inference_kwargs.batch_size = batch_size

            model_kwargs = OmegaConf.to_container(config.model.kwargs, resolve=True)
            model = PasstFiLMConditionedBandit(**model_kwargs)

            loss = BaseLossHandler(loss=L1SNRLoss(), modality="audio")

            stems = list(config.stems)
            _metric_for = lambda s: BaseMetricHandler(
                stem=s,
                metric=tm.MetricCollection(SafeSignalNoiseRatio()),
                modality="audio",
                name="snr",
            )
            metrics = MultiModeMetricHandler(
                train_metrics={s: _metric_for(s) for s in stems},
                val_metrics={s: _metric_for(s) for s in stems},
                test_metrics={s: _metric_for(s) for s in stems},
            )

            opt_bundle = SimpleNamespace(
                optimizer=SimpleNamespace(cls=torch.optim.Adam, kwargs={}),
                scheduler=None,
            )

            system = EndToEndLightningSystem.load_from_checkpoint(
                str(_WEIGHTS_PATH),
                strict=True,
                model=model,
                loss_handler=loss,
                metrics=metrics,
                augmentation_handler=torch.nn.Identity(),
                inference_handler=config.data.inference_kwargs,
                optimization_bundle=opt_bundle,
                fast_run=False,
                batch_size=config.data.batch_size,
                effective_batch_size=config.data.get("effective_batch_size", None),
                commitment_weight=config.get("commitment_weight", 1.0),
            )

            # CPU only — model contains float64 buffers (PaSST position embeddings)
            # that MPS doesn't support. CUDA used if available.
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            system = system.to(device)
            system.eval()
    finally:
        sys.stdout, sys.stderr = _old_out, _old_err
        _devnull.close()
        logging.disable(logging.NOTSET)

    mixture, fsm = ta.load(str(audio_path))
    query, fsq = ta.load(str(query_wav_path))

    if fsm != MODEL_FS:
        mixture = ta.functional.resample(mixture, fsm, MODEL_FS)
    if fsq != MODEL_FS:
        query = ta.functional.resample(query, fsq, MODEL_FS)

    # Ensure stereo
    if mixture.shape[0] == 1:
        mixture = mixture.repeat(2, 1)
    if query.shape[0] == 1:
        query = query.repeat(2, 1)

    # Pad/crop query to exactly 10 seconds
    if query.shape[1] < QUERY_SAMPLES:
        reps = -(-QUERY_SAMPLES // query.shape[1])
        query = query.repeat(1, reps)
    query = query[:, :QUERY_SAMPLES]

    query = query.unsqueeze(0).to(device)
    mixture = mixture.unsqueeze(0).to(device)

    batch = {
        "mixture":  {"audio": mixture},
        "query":    {"audio": query},
        "metadata": {"stem": [stem_name]},
        "estimates": {},
    }

    with torch.no_grad():
        out = system.chunked_inference(batch)

    estimate = out["estimates"][stem_name]["audio"].squeeze().cpu()

    if fsm != MODEL_FS:
        estimate = ta.functional.resample(estimate, MODEL_FS, fsm)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(out_path), estimate, fsm)


def _ensure_deps(console=None) -> None:
    import importlib.util
    missing = [
        pkg for pkg, mod in [
            ("pytorch-lightning", "pytorch_lightning"),
            ("hear21passt",       "hear21passt"),
            ("torchmetrics",      "torchmetrics"),
        ]
        if importlib.util.find_spec(mod) is None
    ]
    if not missing:
        return
    if console:
        console.print(f"  Installing: {', '.join(missing)}...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
        check=True,
    )


def _download_weights(console=None) -> None:
    import urllib.request
    _WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    downloaded = [0]

    def _progress(count, block_size, total):
        downloaded[0] = min(count * block_size, total)
        if console and total > 0 and count % 200 == 0:
            pct = downloaded[0] / total * 100
            console.print(f"    {pct:.0f}% ({downloaded[0]//1_000_000} MB)", end="\r")

    urllib.request.urlretrieve(_ZENODO_URL, str(_WEIGHTS_PATH), reporthook=_progress)
    if console:
        console.print(f"\n  [green]Weights saved to {_WEIGHTS_PATH}[/green]")
