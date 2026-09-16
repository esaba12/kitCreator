import { parseSfz, regionInt, regionFloat, midiToNoteName } from "./sfz-parser.js";
import WaveSurfer from "https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js";

const ASSETS = "/demo/assets";
const DRUM_CLASS_ORDER = ["kick", "snare", "hihat", "toms", "cymbals"];
const DRUM_CLASS_LABEL = { kick: "Kick", snare: "Snare", hihat: "Hi-Hat", toms: "Toms", cymbals: "Cymbals" };
const DRUM_KEY_BINDING = { kick: "1", snare: "2", hihat: "3", toms: "4", cymbals: "5" };

document.addEventListener("pointerdown", () => Tone.start(), { once: true });
document.addEventListener("keydown", () => Tone.start(), { once: true });

async function main() {
  const manifest = await fetch(`${ASSETS}/manifest.json`).then((r) => r.json());

  document.getElementById("song-title").textContent = manifest.song.title;
  document.getElementById("song-artist").textContent = manifest.song.artist;
  document.getElementById("song-license").textContent = manifest.song.license;
  document.getElementById("song-source").href = manifest.song.source_url;

  setupWaveforms(manifest);
  setupExtractionGrid(manifest);
  setupTimbrePanel(manifest);
  await setupPlayableExport(manifest);
}

// ---------- Stage 1: Separation ----------
function setupWaveforms(manifest) {
  const rows = [
    { id: "wave-original", url: `${ASSETS}/original.mp3`, color: "#17140f", label: "Original mix" },
    { id: "wave-drums", url: `${ASSETS}/drums/stem.mp3`, color: "#ff5a1f", label: "Isolated drums" },
    { id: "wave-bass", url: `${ASSETS}/bass/stem.mp3`, color: "#0aa89a", label: "Isolated bass" },
  ];
  const instances = [];
  for (const row of rows) {
    const container = document.getElementById(row.id);
    const ws = WaveSurfer.create({
      container,
      waveColor: row.color,
      progressColor: row.color,
      cursorColor: "#f2b705",
      cursorWidth: 3,
      height: 56,
      barWidth: 2,
      barGap: 2,
      barRadius: 1,
      url: row.url,
    });
    const btn = container.closest(".wave-row").querySelector(".wave-play");
    btn.addEventListener("click", () => ws.playPause());
    ws.on("play", () => {
      btn.classList.add("is-pressed");
      // Only one track plays at a time — stop every other waveform.
      for (const other of instances) {
        if (other.ws !== ws && other.ws.isPlaying()) other.ws.pause();
      }
    });
    ws.on("pause", () => btn.classList.remove("is-pressed"));
    ws.on("finish", () => btn.classList.remove("is-pressed"));
    instances.push({ ws, btn });
  }
}

// ---------- Stage 2: Extraction ----------
function setupExtractionGrid(manifest) {
  const grid = document.getElementById("drum-grid");
  const byClass = {};
  for (const s of manifest.drums.samples) {
    (byClass[s.class] ??= []).push(s);
  }
  for (const cls of DRUM_CLASS_ORDER) {
    const samples = (byClass[cls] || []).sort((a, b) => a.vel_low - b.vel_low || a.rr - b.rr);
    if (!samples.length) continue;
    const col = document.createElement("div");
    col.className = "extract-col";
    col.innerHTML = `<div class="extract-col-label">${DRUM_CLASS_LABEL[cls]}</div>`;
    const tiles = document.createElement("div");
    tiles.className = "tile-stack";
    for (const s of samples) {
      const tile = document.createElement("button");
      tile.className = "sample-tile";
      tile.innerHTML = `<span class="vel">v${s.vel_low}</span><span class="rr">rr${s.rr}</span>`;
      tile.addEventListener("click", () => new Audio(`${ASSETS}/drums/samples/${s.file}`).play());
      tiles.appendChild(tile);
    }
    col.appendChild(tiles);
    grid.appendChild(col);
  }

  const bassStrip = document.getElementById("bass-strip");
  const bassSamples = [...manifest.bass.samples].sort((a, b) => a.midi - b.midi);
  for (const s of bassSamples) {
    const tile = document.createElement("button");
    tile.className = "sample-tile sample-tile-bass";
    tile.innerHTML = `<span class="note">${midiToNoteName(s.midi)}</span>`;
    tile.addEventListener("click", () => new Audio(`${ASSETS}/bass/samples/${s.file}`).play());
    bassStrip.appendChild(tile);
  }
}

// ---------- Stage 3: Timbre ----------
function setupTimbrePanel(manifest) {
  const velBuckets = new Set(manifest.drums.samples.map((s) => s.vel_low)).size;
  const maxRr = Math.max(...manifest.drums.samples.map((s) => s.rr_count));
  document.getElementById("timbre-stats").innerHTML = `
    <div><b>${manifest.drums.classes.length}</b><span>drum classes</span></div>
    <div><b>${velBuckets}</b><span>velocity layers</span></div>
    <div><b>${maxRr}</b><span>round-robins / layer</span></div>
    <div><b>${manifest.drums.sample_count}</b><span>one-shots kept</span></div>
  `;
}

// ---------- Stage 4: Export — parse the real kit.sfz client-side and make it playable ----------
async function setupPlayableExport(manifest) {
  const [drumSfzText, bassSfzText] = await Promise.all([
    fetch(`${ASSETS}/drums/kit.sfz`).then((r) => r.text()),
    fetch(`${ASSETS}/bass/kit.sfz`).then((r) => r.text()),
  ]);
  const drumRegions = parseSfz(drumSfzText);
  const bassRegions = parseSfz(bassSfzText);

  document.getElementById("sfz-readout").innerHTML =
    `<span class="bit"></span>PARSED ${drumRegions.length + bassRegions.length} REGIONS FROM REAL kit.sfz`;
  document.getElementById("sfz-readout").classList.add("is-live");

  buildDrumPads(drumRegions);
  await buildBassKeyboard(bassRegions);
}

function buildDrumPads(regions) {
  const byClass = {};
  for (const r of regions) {
    const cls = r.sample.split("/").pop().match(/^([a-z]+)_/)[1];
    (byClass[cls] ??= []).push(r);
  }

  const rrCounters = {};
  const chokeActive = {};

  async function trigger(cls, velocity) {
    const candidates = byClass[cls];
    if (!candidates || !candidates.length) return;
    const inBand = candidates.filter(
      (r) => velocity >= regionInt(r, "lovel", 0) && velocity <= regionInt(r, "hivel", 127)
    );
    const pool = inBand.length ? inBand : candidates;
    const i = (rrCounters[cls] = (rrCounters[cls] || 0) + 1);
    const region = pool[i % pool.length];

    const chokeGroup = region.group;
    if (chokeGroup && chokeActive[chokeGroup]) {
      chokeActive[chokeGroup].stop();
    }

    const buffer = await Tone.ToneAudioBuffer.fromUrl(`${ASSETS}/drums/samples/${region.sample.split("/").pop()}`);
    const player = new Tone.Player(buffer).toDestination();
    player.start();
    if (chokeGroup) chokeActive[chokeGroup] = player;

    const pad = document.querySelector(`.pad[data-class="${cls}"]`);
    if (pad) {
      pad.classList.add("is-pressed");
      setTimeout(() => pad.classList.remove("is-pressed"), 110);
    }
  }

  const grid = document.getElementById("pad-grid");
  for (const cls of DRUM_CLASS_ORDER) {
    if (!byClass[cls]) continue;
    const pad = document.createElement("button");
    pad.className = "pad";
    pad.dataset.class = cls;
    pad.innerHTML = `
      <span class="pad-face">
        <span class="pad-name">${DRUM_CLASS_LABEL[cls]}</span>
        <span class="pad-key">${DRUM_KEY_BINDING[cls]}</span>
      </span>
      <span class="pad-hint">click near top = hard, bottom = soft</span>
    `;
    pad.addEventListener("pointerdown", (e) => {
      const rect = pad.getBoundingClientRect();
      const rel = 1 - (e.clientY - rect.top) / rect.height;
      const velocity = Math.max(1, Math.min(127, Math.round(rel * 127)));
      trigger(cls, velocity);
    });
    grid.appendChild(pad);
  }

  window.addEventListener("keydown", (e) => {
    if (e.repeat) return;
    const cls = Object.entries(DRUM_KEY_BINDING).find(([, key]) => key === e.key)?.[0];
    if (cls) trigger(cls, 110);
  });
}

async function buildBassKeyboard(regions) {
  const urls = {};
  const recordedMidis = new Set();
  let lo = Infinity;
  let hi = -Infinity;
  for (const r of regions) {
    const midi = regionInt(r, "pitch_keycenter");
    const note = midiToNoteName(midi);
    urls[note] = r.sample.split("/").pop();
    recordedMidis.add(midi);
    lo = Math.min(lo, regionInt(r, "lokey", midi));
    hi = Math.max(hi, regionInt(r, "hikey", midi));
  }

  const sampler = new Tone.Sampler({
    urls,
    baseUrl: `${ASSETS}/bass/samples/`,
    release: 0.4,
  }).toDestination();
  await Tone.loaded();

  const keyboard = document.getElementById("bass-keyboard");
  const BLACK = new Set([1, 3, 6, 8, 10]);
  for (let midi = lo; midi <= hi; midi++) {
    const note = midiToNoteName(midi);
    const key = document.createElement("button");
    key.className = "bkey" + (BLACK.has(midi % 12) ? " bkey-black" : "");
    if (recordedMidis.has(midi)) key.classList.add("bkey-recorded");
    key.title = note;
    key.addEventListener("pointerdown", () => {
      sampler.triggerAttackRelease(note, "8n");
      key.classList.add("is-pressed");
      setTimeout(() => key.classList.remove("is-pressed"), 140);
    });
    keyboard.appendChild(key);
  }
}

main();
