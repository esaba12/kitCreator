# Hyperframes Composition Brief: kitCreator

## Objective
Create a short launch-style brag video for kitCreator (kitforge CLI) — a tool that turns any song into a playable multi-octave sampler kit.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: ~21 seconds

## Source Material
- Project root: `/Users/ethansaba/code/kitCreator`
- Primary files read: `site/index.html` (dark landing hero + live-look terminal block), `site/demo/index.html` + `site/shared.css` (light "chassis" register: waveforms, drum pad grid, bass keyboard), `site/demo/assets/manifest.json` + `site/demo/assets/drums/samples/*.wav` (real extracted one-shots), `README.md`, `CLAUDE.md`
- Product name: kitCreator (CLI: `kitforge`)
- Tagline / strongest claim: "Any song becomes a playable kit." Secondary claim used as a mid-video pivot: "This is a real render. Not a mockup."
- Key UI/visual moments to recreate:
  1. The dark landing hero's condensed bold type treatment
  2. The live terminal block running `kitforge build --song track.wav --instrument "lead synth" --range C2-C7` with real green ✓ stage checkmarks
  3. The demo page's three labeled waveform rows (Original Mix / Isolated Drums / Isolated Bass)
  4. The demo page's real MPC-style drum pad grid (Kick/Snare/Hi-Hat/Toms/Cymbals)
- Copy that must appear verbatim:
  - "ANY SONG BECOMES A PLAYABLE KIT."
  - "$ kitforge build --song track.wav --instrument \"lead synth\" --range C2-C7"
  - "separation", "transcription", "timbre cluster", "export" (stage labels, with their real tool tags: `htdemucs_ft`, `basic_pitch`, `clap · hdbscan`, `synth_kit/kit.sfz`)
  - "THIS IS A REAL RENDER. NOT A MOCKUP."
  - "ORIGINAL MIX", "ISOLATED DRUMS", "ISOLATED BASS"

## Creative Direction
- Tone preset: `default`
- Creative direction: "playful, nerdy, technical-showcase confidence — dark audio-gear aesthetic, not corporate, not jokey-loud. Confidence comes from showing real technical output (a real CLI run, real waveforms, real drum hits), not from jokes or hype language."
- Interpretation: punchy but clean cuts, condensed bold display type, monospace for anything technical/code, one hard register-punch (dark → light chassis) as the single biggest transition, otherwise quick crossfades/slides. No cartoonish bounce, no over-the-top zooms.
- Angle: The video borrows the site's own real navigation structure — it opens in the dark "landing" register (bold claim, live terminal) and punches into the lighter "demo chassis" register exactly like a user clicking "Try the demo" would. Every visual is the actual UI/audio, nothing invented, which directly proves the video's own mid-point claim: "this is a real render, not a mockup."
- Hook: Eyebrow "SONG → SAMPLER KIT." then the real hero copy building line by line, landing on "PLAYABLE KIT." in amber.
- Outro / punchline: "Any song becomes a playable kit." settling a final time over the dark register, small credit line beneath.
- Avoid:
  - Generic SaaS language
  - Abstract filler visuals
  - Inventing UI that doesn't exist in the project
  - Waveform/equalizer-style "generic visualizer" graphics as a stand-in for audio-reactivity

## Visual Identity

**Landing register (hook + outro scenes):**
- Background: `#0b0c0d`; panels `#131416` / `#17191c`; lines `#2a2c30` / `#1e2023`
- Amber accent: `#ff7a1a` (dim `#7a3d12`); success green: `#4be07a`
- Text: `#e8e6e1` (primary), `#8a8d92` (dim), `#55585d` (faint)
- Display font: Chakra Petch (600/700)
- Mono font: JetBrains Mono (400/500/600)

**Demo/chassis register (proof + payoff scenes):**
- Background: `#f2efe7` (chassis), raised `#fbfaf6`, panel `#e8e4d8`
- Ink: `#17140f` (primary), `#6b6558` (dim), `#a39d8d` (faint)
- Lines: `#d6d0c0` / `#b8b1a0`
- Orange (drums): `#ff5a1f`; Teal (bass): `#0aa89a`; Yellow accent: `#f2b705`
- Display font: Archivo (600/700/800)
- Mono font: IBM Plex Mono (400/500/600)

- Visual references from the project: `site/index.html` hero + terminal block; `site/demo/index.html` waveform rows + drum pad grid + bass keyboard; `site/shared.css` chassis design tokens.

## Storyboard
Full storyboard is in `brag-output/brag-plan.md` — treat it as the creative contract. Scene summary:

1. **Hook** — 3s — eyebrow + 3-line hero build, landing on amber "PLAYABLE KIT."
2. **The CLI actually running** — 5s — real command types in, 4 real pipeline stages complete with green ✓
3. **The proof: real waveforms** — 5s — hard register-punch to chassis look; headline "THIS IS A REAL RENDER. NOT A MOCKUP."; 3 real labeled waveform rows
4. **The payoff: a real playable kit** — 5s — real drum pad grid triggers pad-by-pad with real extracted one-shot audio
5. **Outro** — 3s — cut back to dark register; hook line settles as closing statement + credit line

## Audio
- Audio role: energetic-but-grounded bed under the claim/CLI/proof beats; the payoff scene is carried by real, diegetic drum one-shots instead of stock SFX
- Audio arc: bed enters at 0.3 under the hook, stays present through the CLI-run and waveform-proof scenes, ducks to ~0.15 under the payoff scene so the real drum hits read clearly, returns to 0.3 for the outro settle and fades out
- Music: `happy-beats-business-moves-vol-9-by-ende-dot-app.mp3` (mid-energy, slightly laid-back — leaves headroom for the real drum hits in the payoff scene)
- Music treatment: see arc above; no hard drop, no swell — steady presence that steps back at the right moment
- Music cue guidance: no bundled cue preset confirmed for vol-9 — run `npx hyperframes beats <output-dir>/composition` once the track is wired in and lock the "PLAYABLE KIT." hero landing and the terminal's final ✓ to the nearest strong/high-strength beat within ±0.15s; otherwise use the plan's natural scene timings
- Audio-reactive treatment: subtle — hero glow / terminal panel may breathe slightly with music RMS during the hook and outro only; explicitly avoid waveform/equalizer-style visualizer graphics (the project's own waveform imagery is static proof content, not a generic music-app visualizer, and should stay that way)
- Audio-coupled moments:
  - Scene 1 (hook) — eyebrow/line pop-ins, final "PLAYABLE KIT." landing gets the strongest accent of the scene
  - Scene 2 (CLI) — per-character typing sound on the command, one completion tick per pipeline stage ✓ (varied, not identical)
  - Scene 3 (proof) — the dark→chassis register punch is the single loudest transition in the video; waveform rows get soft pop-ins
  - Scene 4 (payoff) — each drum pad's light-up plays its real extracted one-shot sample; music ducks under this scene
  - Scene 5 (outro) — one restrained settle accent on the final hook-line landing
- SFX selection guidance: keyboard typing → randomized `keyboard/keypress-*.wav`; stage-checkmark ticks → `interface/click_00X.ogg` family (vary the exact file per stage); register-punch → one `interface/drop_001.ogg`; payoff scene → the real extracted drum one-shots from `site/demo/assets/drums/samples/` (copy 5 representative files — one kick, one snare, one hi-hat, one toms, one cymbals — into the composition's assets, e.g. the `v96`/high-velocity round-robin-1 variant of each class for the cleanest single hit); outro → one restrained `impact/impactSoft_medium_001.ogg`, not a big cinematic bell
- SFX analysis guidance: read `skills/brag/assets/sfx/sfx-analysis.md` (or the installed-skill equivalent) and prefer low/medium high-frequency-risk files for the repeated typing/tick moments
- Exact SFX choice: Hyperframes should finalize exact filenames/timestamps/volumes once the animation timing is implemented
- Audio files: copy `happy-beats-business-moves-vol-9-by-ende-dot-app.mp3`, the chosen SFX, and 5 real drum one-shot WAVs into `brag-output/composition/assets/`

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core`, `hyperframes-animation`, `hyperframes-creative`, `hyperframes-keyframes`, `hyperframes-cli`. This is a `/brag` workflow — do not enter the generic `hyperframes` intent interview.

Requirements:
- Show at least one real UI, copy, or visual element from the source project (the brief above lists several — use all of them, they're the point of this video).
- Keep all text readable in the final render.
- Keep the video within 15-25 seconds.
- Include the planned music/SFX layer.
- Treat the audio notes above as guidance; finalize exact SFX/timing once the animation exists.
- Use the real drum one-shot WAV files as the payoff scene's SFX — this is a specific creative requirement from `/brag`, not a generic placeholder choice.
- Run `hyperframes check` before render.
