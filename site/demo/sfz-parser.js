// Minimal SFZ opcode parser — reads the real kit.sfz kitforge exports.
// Supports exactly the opcodes kitforge's sfz_writer.py emits: <global>, <group>,
// <region>, lokey/hikey/pitch_keycenter, lovel/hivel, seq_position/seq_length,
// group/off_by/off_mode (choke), ampeg_* (ADSR), loop_mode/loop_start/loop_end.
export function parseSfz(text) {
  const lines = text.split("\n").map((l) => l.trim());
  let currentGroup = {};
  const regions = [];

  for (const line of lines) {
    if (!line || line.startsWith("//")) continue;
    if (line.startsWith("<group>")) {
      currentGroup = parseOpcodes(line.slice("<group>".length));
    } else if (line.startsWith("<region>")) {
      const opcodes = parseOpcodes(line.slice("<region>".length));
      regions.push({ ...currentGroup, ...opcodes });
    }
  }
  return regions;
}

function parseOpcodes(str) {
  const out = {};
  for (const match of str.matchAll(/(\w+)=(\S+)/g)) {
    out[match[1]] = match[2];
  }
  return out;
}

export function regionInt(region, key, fallback = undefined) {
  return key in region ? parseInt(region[key], 10) : fallback;
}
export function regionFloat(region, key, fallback = undefined) {
  return key in region ? parseFloat(region[key]) : fallback;
}

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
export function midiToNoteName(midi) {
  const octave = Math.floor(midi / 12) - 1;
  return `${NOTE_NAMES[midi % 12]}${octave}`;
}
