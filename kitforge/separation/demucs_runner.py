from __future__ import annotations

from pathlib import Path

import soundfile as sf
import torch


_QUALITY_MODEL = {
    "fast": "htdemucs",
    "default": "htdemucs_ft",
    "high": "htdemucs_ft",
}


def separate(
    audio_path: Path,
    out_dir: Path,
    quality: str = "default",
    six_stem: bool = False,
) -> dict[str, Path]:
    """Run htdemucs separation. Returns stem name → wav path."""
    from demucs.apply import apply_model
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model

    model_name = "htdemucs_6s" if six_stem else _QUALITY_MODEL.get(quality, "htdemucs_ft")
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    model = get_model(model_name)
    model.to(device)
    model.eval()

    wav = AudioFile(audio_path).read(
        streams=0, samplerate=model.samplerate, channels=model.audio_channels
    )
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()

    with torch.no_grad():
        sources = apply_model(model, wav[None].to(device), device=device, progress=True)[0]

    sources = sources * ref.std() + ref.mean()

    out_dir.mkdir(parents=True, exist_ok=True)
    stem_paths: dict[str, Path] = {}
    for stem, source in zip(model.sources, sources):
        out_path = out_dir / f"{stem}.wav"
        # Move to CPU before writing — torchcodec doesn't support MPS encoding
        audio_np = source.cpu().numpy().T  # (samples, channels)
        sf.write(str(out_path), audio_np, model.samplerate, subtype="PCM_24")
        stem_paths[stem] = out_path

    del model
    torch.mps.empty_cache() if torch.backends.mps.is_available() else None

    return stem_paths
