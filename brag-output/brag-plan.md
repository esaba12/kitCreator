# Brag Plan: kitCreator

## The 9-question rubric

1. **What is the app?** A CLI (`kitforge`) that turns any song into a fully playable, multi-octave sampler kit — separates stems (Demucs), transcribes every note (Basic Pitch/CREPE), clusters real one-shots by timbre (CLAP), and exports ready-to-load SFZ/DecentSampler presets. No mockup — the shipped web demo plays back real generated output.
2. **Funniest/most impressive claim:** "This is a real render. Not a mockup." — the demo's own headline, and a great meta-hook since the video itself has to prove it's showing something real.
3. **Visual hook:** The dark landing hero's giant condensed type — "ANY SONG BECOMES A **PLAYABLE KIT.**" in Chakra Petch, white-to-amber (#ff7a1a) — paired with the live-look terminal block running the actual `kitforge build` command with green ✓ stage checkmarks.
4. **What to show from the UI:** The terminal run (landing page), the three real labeled waveforms (Original Mix / Isolated Drums / Isolated Bass — demo page), and the real MPC-style drum pad grid actually triggering.
5. **Shortest satisfying video:** ~20-21s — four dense but real beats (hero claim → CLI actually running → separation proof → playable payoff) each need a couple seconds to read.
6. **Tone:** preset `default` (playful, clean, postable) — user's custom direction: "playful, nerdy, technical-showcase confidence, dark audio-gear aesthetic, not corporate, not jokey-loud." Confidence comes from showing real technical output, not from jokes.
7. **Audio:** Energetic-but-grounded music bed under the CLI/waveform beats, then the payoff scene's SFX are **diegetic and real**: the actual extracted drum one-shots (`kick_v96_1.wav`, `snare_v96_1.wav`, `hihat`, `toms`, `cymbals`) from `site/demo/assets/drums/samples/` fire when each pad triggers — this is the single most "specific, not generic" audio choice available, since the whole product is about turning songs into real drum hits.
8. **Share caption:** "I built a CLI that turns any song into a playable sampler kit — real Demucs separation, real CLAP timbre clustering, real SFZ export. This is a real render. Not a mockup. 🥁"
9. **User flow worth showing:** entry (run `kitforge build --song track.wav --instrument "lead synth" --range C2-C7`) → key action (separation/transcription/timbre-match/export stages completing live) → result (the real waveforms prove separation happened; the real drum pad grid proves you can now play it).

## The angle

Two registers, borrowed directly from the real site's own navigation: the video opens in the site's dark "landing" register (bold claim, live terminal) and punches into the lighter "demo chassis" register exactly like a user clicking "Try the demo" would — because that cut *is* the site's real information architecture, not an invented transition. The whole video is built to answer its own headline: "this is a real render, not a mockup" — every visual is the actual UI/audio, nothing invented.

## Hook (first 2-3s)
Full-bleed dark background (`#0b0c0d`). Eyebrow line settles first, mono, small caps, amber: "SONG → SAMPLER KIT." Then the real hero copy builds fast, line by line, Chakra Petch condensed bold: "ANY SONG" (white) / "BECOMES A" (white) / "PLAYABLE KIT." (amber `#ff7a1a`, largest).

## Key moments (the middle)
- **The CLI actually running:** dark terminal panel (`#131416`/`#17191c`, JetBrains Mono), the real command types in — `$ kitforge build --song track.wav --instrument "lead synth" --range C2-C7` — then four stage lines land one by one with green (`#4be07a`) ✓: `separation htdemucs_ft` / `transcription basic_pitch` / `timbre cluster clap · hdbscan` / `export synth_kit/kit.sfz`. Cursor blinks at a `$` prompt after the last line.
- **The proof — real waveforms:** hard cut/punch-in to the demo's light chassis register (`#f2efe7` bg, `#17140f` ink). Headline lands verbatim: "THIS IS A REAL RENDER. NOT A MOCKUP." Three real labeled waveforms slide in in sequence: "ORIGINAL MIX" (black/ink), "ISOLATED DRUMS" (orange `#ff5a1f`), "ISOLATED BASS" (teal `#0aa89a`) — same visual language as the shipped `WaveSurfer.js` waveform rows.
- **The payoff — a real playable kit:** the real drum pad grid (Kick / Snare / Hi-Hat / Toms / Cymbals, same chassis styling) lights up pad by pad as if triggered, each hit paired with its *actual* extracted one-shot audio firing in sync — proving the "any song becomes a playable kit" claim literally, with real sound.

## Outro / punchline
Cut back to the dark hero register. Hook line settles a final time as a closing statement: "Any song becomes a playable kit." Small mono credit line beneath: "kitforge · github.com/esaba12/kitCreator." Hold, fade.

## User flow worth showing
Entry → key action → result, pulled straight from the actual pipeline:
1. **Entry:** the real `kitforge build` command, typed and run.
2. **Key action:** the four real pipeline stages completing live (separation → transcription → timbre match → export).
3. **Result:** real waveform separation proof, then a real drum kit you can actually hit.

## Tone
- Preset: `default`
- Creative direction: "playful, nerdy, technical-showcase confidence — dark audio-gear aesthetic, not corporate, not jokey-loud. Confidence comes from showing real technical output (a real CLI run, real waveforms, real drum hits), not from jokes or hype language."
- Interpretation: punchy but clean cuts, condensed bold display type, monospace for anything technical/code, one hard register-punch (dark → light chassis) as the single biggest transition, otherwise quick crossfades/slides. No cartoonish bounce, no over-the-top zooms.

## Format: landscape — 1920x1080
## Duration: ~21s

## Visual identity (from the project — two registers)
**Landing register (hero + outro):**
- Background: `#0b0c0d`; panels `#131416` / `#17191c`; lines `#2a2c30` / `#1e2023`
- Amber accent: `#ff7a1a` (dim variant `#7a3d12`); success green: `#4be07a`
- Text: `#e8e6e1` (primary), `#8a8d92` (dim), `#55585d` (faint)
- Display font: Chakra Petch (600/700) — bold, condensed, technical
- Mono font: JetBrains Mono (400/500/600) — terminal, code, labels

**Demo/chassis register (proof + payoff):**
- Background: `#f2efe7` (chassis), raised `#fbfaf6`, panel `#e8e4d8`
- Ink: `#17140f` (primary text), `#6b6558` (dim), `#a39d8d` (faint)
- Lines: `#d6d0c0` / `#b8b1a0`
- Orange: `#ff5a1f` (drums); Teal: `#0aa89a` (bass); Yellow: `#f2b705` (accent)
- Display font: Archivo (600/700/800); Mono font: IBM Plex Mono (400/500/600)

## Share copy (draft)
I built a CLI that turns any song into a playable sampler kit — real Demucs separation, real CLAP timbre clustering, real SFZ export. This is a real render. Not a mockup. 🥁

## Audio direction
- Role: energetic-but-grounded bed under the CLI/waveform beats; the payoff scene is carried by **real, diegetic drum one-shots** instead of stock SFX.
- Music: `happy-beats-business-moves-vol-9-by-ende-dot-app.mp3` (mid-energy, slightly laid-back — leaves room for the real drum hits to read clearly in the payoff scene rather than competing with a dense music bed)
- Music treatment: enters under the hook at moderate volume (0.3), stays present through the CLI/waveform scenes, ducks down (~0.15) under the payoff scene so the real extracted drum hits read clearly, then returns to 0.3 for the outro settle.
- Music cue guidance: no bundled cue preset confirmed for vol-9 at plan time — run `npx hyperframes beats <output-dir>/composition` once the track is wired in, and lock the hero-line landing ("PLAYABLE KIT.") and the terminal's final ✓ to the nearest strong beat within ±0.15s. If beat data isn't available, keep to the scene timings below without hard sync.
- SFX posture: keyboard typing uses randomized `keyboard/keypress-*.wav` per character on the CLI command; each of the 4 stage-checkmarks gets one `interface/click_00X.ogg`-family tick (ascending, not identical, so it doesn't feel robotic); the register-punch cut (dark→chassis) gets one `interface/drop_001.ogg`; the payoff scene's pad hits use the **real extracted drum samples** (`kick_v96_1.wav`, `snare_v96_1.wav`, one hihat/toms/cymbals one-shot each) copied in from `site/demo/assets/drums/samples/`; outro gets one restrained `impact/impactSoft_medium_001.ogg` on the final hook-line settle — no big cinematic bell, this isn't that kind of tone.
- Audio-reactive treatment: subtle — let the amber hero glow/terminal panel breathe slightly with music RMS during the hook and outro only; no waveform/equalizer-style visualizers (the real WaveSurfer-style waveforms already shown are static proof images, not audio-reactive graphics, and should stay that way to avoid looking like a generic music-app cliché).

## Storyboard

### Scene 1 — Hook — 3s
Full-bleed `#0b0c0d`. Eyebrow "SONG → SAMPLER KIT." (JetBrains Mono, amber, small caps) settles first. Then real hero copy builds line by line in Chakra Petch bold/condensed: "ANY SONG" (white) → "BECOMES A" (white) → "PLAYABLE KIT." (amber `#ff7a1a`, largest scale).
Sequential/interaction: 3 lines land in quick succession, ~0.3-0.4s apart
Audio intent: music enters under the eyebrow; each line lands with a soft interface tick, final "PLAYABLE KIT." gets a slightly stronger accent
Audio-coupled idea: `interface/drop_001.ogg` on eyebrow, `interface/click_002.ogg` + `click_003.ogg` on lines 2-3, `impact/impactSoft_medium_000.ogg` on "PLAYABLE KIT." landing
Music: bed enters at 0.3 volume
Transition mood: quick cut → Scene 2

### Scene 2 — The CLI actually running — 5s
Dark terminal panel (`#131416`, JetBrains Mono). Real command types in character by character: `$ kitforge build --song track.wav --instrument "lead synth" --range C2-C7`. Then four real stage lines land one at a time with green ✓ (`#4be07a`): `separation  htdemucs_ft` / `transcription  basic_pitch` / `timbre cluster  clap · hdbscan` / `export  synth_kit/kit.sfz`. Blinking `$` cursor holds briefly at the end.
Sequential/interaction: command types in (~1.2s), then 4 stage lines land ~0.5s apart
Audio intent: real per-character typing sound, then one clean tick per stage completion — feels like watching a real build finish
Audio-coupled idea: randomized `keyboard/keypress-*.wav` per typed character; `interface/click_001.ogg`–`click_004.ogg` (one per stage, varied not identical) on each ✓ landing
Music: bed continues at 0.3
Transition mood: hard register-punch (dark → light chassis) → Scene 3

### Scene 3 — The proof: real waveforms — 5s
Cut to the demo's chassis register (`#f2efe7` bg, `#17140f` ink, Archivo display, IBM Plex Mono labels). Headline lands verbatim: "THIS IS A REAL RENDER. NOT A MOCKUP." Three real labeled waveform rows slide in in sequence: "ORIGINAL MIX" (ink/black) → "ISOLATED DRUMS" (orange `#ff5a1f`) → "ISOLATED BASS" (teal `#0aa89a`).
Sequential/interaction: headline lands, then 3 waveform rows slide in ~0.4s apart
Audio intent: the register punch itself is the loudest single transition moment in the video; waveform rows get soft, quick pop-ins
Audio-coupled idea: `interface/drop_001.ogg` exactly at the punch-cut (0.0s of this scene); `interface/drop_002.ogg` on each waveform row settle
Music: bed continues at 0.3
Transition mood: quick cut → Scene 4

### Scene 4 — The payoff: a real playable kit — 5s
Same chassis register. The real MPC-style drum pad grid (Kick / Snare / Hi-Hat / Toms / Cymbals) is shown; pads light up one at a time as if being triggered — Kick → Snare → Hi-Hat → Toms → Cymbals — each lighting paired with its real extracted one-shot audio actually playing.
Sequential/interaction: 5 pads trigger in sequence, ~0.5-0.6s apart, each with a lit/pressed visual state
Audio intent: this is the emotional core — real drum sounds, not stock SFX, proving the product's exact claim; music ducks under these so the real hits read clearly
Audio-coupled idea: each pad's light-up plays its real sample — `kick_v96_1.wav`, `snare_v96_1.wav`, one real hihat one-shot, one real toms one-shot, one real cymbals one-shot (all from `site/demo/assets/drums/samples/`)
Music: ducks to 0.15 for this scene only
Transition mood: quick cut → Scene 5

### Scene 5 — Outro — 3s
Cut back to the dark landing register (`#0b0c0d`). Hook line settles a final time, now as a closing statement: "Any song becomes a playable kit." Small mono credit line beneath, dim: "kitforge · github.com/esaba12/kitCreator." Hold, fade to black.
Sequential/interaction: hook line settles, then credit line fades in beneath
Audio intent: music returns to 0.3, one restrained settle accent on the hook line, then fades out under the hold
Audio-coupled idea: `impact/impactSoft_medium_001.ogg` on the hook line's final settle
Music: resolves to a soft fade-out
Transition mood: fade to black

**Music mood for this video:** energetic but grounded — present and driving through the claim/CLI/proof beats, then steps back for the payoff so the real drum hits are the star, returns for the close.
**Audio summary:** Real per-character typing and real stage-completion ticks carry Scene 2; the register-punch cut is the loudest transition; the payoff scene trades music prominence for real, diegetic drum one-shots — the single most "specific, not generic" choice in the whole video, since the product's entire premise is turning songs into exactly these sounds.
