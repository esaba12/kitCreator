# Video Brief: kitCreator

## Confirmed via local capture
`site/demo` is **not publicly deployed** (no canonical/OG URL in the HTML, no reachable production domain found) — a Vercel project exists (`site/.vercel/project.json`, projectName "site") but isn't linked to a confirmed live URL. Served both `site/index.html` (landing) and `site/demo/index.html` locally via `python3 -m http.server` and screenshotted both to ground the brief in the real, current UI rather than the written description alone.

## Visual identity (confirmed from the real site, two distinct registers)
- **Landing (`site/index.html`)** — dark near-black background (`#0a0a0a`-ish), bold condensed display type in white/orange for the hero ("ANY SONG BECOMES A **PLAYABLE KIT.**"), a numbered 4-step "Signal Path" card row (Separation/Transcription/Timbre Match/Export), and a live-looking terminal block with green ✓ checkmarks running `kitforge build --song track.wav --instrument "lead synth" --range C2-C7`. Orange accent color, monospace for code/labels. This is the register the video's own hook/title cards should match — dark, bold, technical-confident.
- **Demo (`site/demo`)** — a lighter "technical blueprint" register (cream/graph-paper background, black borders, monospace numbered section labels "01 SEPARATION," "02 EXTRACTION," etc.) framing the actual interactive proof: three labeled waveforms (Original Mix / Isolated Drums / Isolated Bass, color-coded black/orange/teal), a real drum-pad grid (Kick/Snare/Hi-Hat/Toms/Cymbals, "click near top = hard, bottom = soft"), and a real bass keyboard with dot-marked recorded zones. Headline: **"THIS IS A REAL RENDER. NOT A MOCKUP."** with the exact source-material line: "Rendered from Glad To Be Stuck Inside by HoliznaCC0 — CC0 1.0 Universal, a 25-second excerpt."

## Tone / hook
- Tone: playful, nerdy, technical-showcase confidence — not corporate, not jokey-loud either. Let the real terminal output and real waveforms carry the "this is legit" feeling.
- Hook: **"Any song becomes a playable kit."** (landing hero, verbatim) with **"This is a real render. Not a mockup."** as a strong secondary beat/pivot line — good meta-hook since the video itself needs to prove it's showing something real.

## Show-the-thing (non-negotiable visual sequence)
1. Open on the dark landing hero type treatment (establishes the product's one-line pitch).
2. Cut to the terminal block actually running `kitforge build` with the ✓ stage checkmarks (separation → transcription → timbre cluster → export) — real CLI copy, don't invent new copy.
3. Cut to the demo's three real waveforms (Original Mix → Isolated Drums → Isolated Bass) — this is the "prove the separation actually happened" beat.
4. Land on the real MPC-style drum pad grid (and/or bass keyboard) actually being triggered/highlighted — the payoff moment: a real song became a real playable instrument.
5. Close back on the dark hero register with the hook line.

## Format / duration
Landscape, 15-25s per brag's creative laws. Given four fairly dense concept beats (pitch → CLI running → waveform proof → playable kit), keep each beat tight; don't try to also show the bass keyboard AND all 5 drum-pad categories — pick drums as the primary payoff (visually clearer for a quick cut than piano-style bass zones).

## Next step
Run `/brag` from `/Users/ethansaba/code/kitCreator`, feeding it this brief as creative direction (tone: playful/nerdy technical-showcase; hook: "Any song becomes a playable kit." / "This is a real render. Not a mockup."; must-show: terminal run → waveform separation → real drum-pad hit). Local demo is running at `http://localhost:4173` (via `python3 -m http.server 4173` from `site/`) if brag's inspection step wants to capture live screenshots rather than working purely from source code.
