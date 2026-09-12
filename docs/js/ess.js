// Oblivion .ess reader: header, plugin list, which changed references are gone from the world, and inventory changes.

const REFR = 49, ACHR = 50, ACRE = 51;
const CHANGE_FORM_FLAGS = 0x1, CHANGE_INVENTORY = 0x08000000;
const PLAYER = 0x14;
// 0x800 disabled (symbols and plants disable themselves), 0x20 deleted (picked-up items)
const FORM_GONE = 0x800 | 0x20;

class Reader {
  constructor(bytes) {
    this.b = bytes;
    this.v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    this.o = 0;
  }
  u8() { return this.v.getUint8(this.o++); }
  u16() { const x = this.v.getUint16(this.o, true); this.o += 2; return x; }
  u32() { const x = this.v.getUint32(this.o, true); this.o += 4; return x; }
  f32() { const x = this.v.getFloat32(this.o, true); this.o += 4; return x; }
  skip(n) { this.o += n; }
  str(n) {
    let s = '';
    for (let i = 0; i < n; i++) s += String.fromCharCode(this.b[this.o + i]);
    this.o += n;
    return s;
  }
  bzstring() { return this.str(this.u8()).replace(/\0$/, ''); }
  bstring() { return this.str(this.u8()); }
  systemtime() {
    const [y, mo, , d, h, mi, s] = [this.u16(), this.u16(), this.u16(), this.u16(), this.u16(), this.u16(), this.u16()];
    this.u16();
    return new Date(y, mo - 1, d, h, mi, s);
  }
}

export class SaveError extends Error {}

export function parseSave(bytes) {
  if (bytes.byteLength < 64) throw new SaveError('File is too small to be a save.');
  const r = new Reader(bytes);
  if (r.str(12) !== 'TES4SAVEGAME') throw new SaveError('Not an Oblivion/Nehrim save (.ess) file.');
  r.skip(2);
  r.systemtime();

  r.u32();
  const headerSize = r.u32();
  const headerEnd = r.o + headerSize;
  const header = {};
  header.saveNum = r.u32();
  header.name = r.bzstring();
  header.level = r.u16();
  header.location = r.bzstring();
  header.gameDays = r.f32();
  header.playMs = r.u32();
  header.savedAt = r.systemtime();
  const shotSize = r.u32();
  if (shotSize >= 8) {
    const w = r.u32(), h = r.u32();
    if (w * h * 3 + 8 === shotSize) header.screenshot = { width: w, height: h, offset: r.o };
  }
  r.o = headerEnd;

  const plugins = [];
  for (let n = r.u8(), i = 0; i < n; i++) plugins.push(r.bstring());

  const formIdsOffset = r.u32();
  const recordsNum = r.u32();
  r.skip(4 + 4 + 8 + 16);
  const globalsByIref = new Map();
  for (let n = r.u16(), i = 0; i < n; i++) globalsByIref.set(r.u32(), r.f32());
  r.skip(r.u16());
  r.skip(r.u16());
  r.skip(r.u16());
  r.skip(r.u16());
  r.u32();
  for (let n = r.u32(), i = 0; i < n; i++) {
    r.skip(4);
    r.skip(r.u32() + 12);
  }
  r.skip(r.u16());
  r.skip(r.u16());
  r.skip(r.u16());
  r.skip(r.u16());

  const removed = new Map();
  const inventories = new Map();
  for (let i = 0; i < recordsNum; i++) {
    const formId = r.u32();
    const type = r.u8();
    const flags = r.u32();
    r.skip(1);
    const size = r.u16();
    const start = r.o;
    const end = start + size;
    if (end > bytes.byteLength) throw new SaveError('Save file is truncated or corrupt.');
    if ((type === REFR || type === ACHR || type === ACRE) && formId !== PLAYER) {
      skipLocation(r, flags);
      if (type !== REFR) r.skip(1);
      if (flags & CHANGE_FORM_FLAGS) {
        const formFlags = r.u32();
        if (type === REFR) removed.set(formId, (formFlags & FORM_GONE) !== 0);
      }
      if (flags & CHANGE_INVENTORY) inventories.set(formId, [r.o, end]);
    }
    r.o = end;
  }
  if (r.o > formIdsOffset) throw new SaveError('Could not read change records; the save may be from an unsupported version.');

  r.o = formIdsOffset;
  const formIds = new Uint32Array(r.u32());
  for (let i = 0; i < formIds.length; i++) formIds[i] = r.u32();
  const globals = new Map();
  for (const [iref, value] of globalsByIref) globals.set(iref < formIds.length ? formIds[iref] : iref, value);

  let irefOf = null;
  // Change in `item` count held by the placed reference `holder`, relative to the game data; -1 means one was taken.
  function inventoryChange(holder, item) {
    const span = inventories.get(holder);
    if (!span) return 0;
    irefOf ??= new Map(Array.from(formIds, (f, i) => [f, i]));
    const iref = irefOf.get(item);
    return iref === undefined ? 0 : stackChange(r.v, span, iref);
  }

  return { header, plugins, removed, globals, inventoryChange };
}

// Cell-changed and position blocks precede the actor flag and form flags; their sizes depend on the change flags.
function skipLocation(r, flags) {
  if (flags & 0x80000000) r.skip(16);
  if (flags & 0x2) r.skip(36);
  else if (flags & 0x4) r.skip(28);
  else if (flags & 0x8) r.skip(28);
  else if (flags & 0x00800000) r.skip(4);
}

// Entries are [iref u32][count change i32][property sets u32][sets]; sets have variable-size properties,
// so after the first entry that has any, scan for the item's iref followed by a negative count instead.
function stackChange(v, [start, end], iref) {
  let o = start + 2;
  for (let n = v.getUint16(start, true); n > 0 && o + 12 <= end; n--, o += 12) {
    if (v.getUint32(o, true) === iref) return v.getInt32(o + 4, true);
    if (v.getUint32(o + 8, true) !== 0) break;
  }
  for (; o + 8 <= end; o++) {
    if (v.getUint32(o, true) === iref && v.getInt32(o + 4, true) < 0) return v.getInt32(o + 4, true);
  }
  return 0;
}

export function screenshotImageData(bytes, shot) {
  const { width, height, offset } = shot;
  const out = new Uint8ClampedArray(width * height * 4);
  for (let i = 0, j = offset; i < width * height; i++, j += 3) {
    out[i * 4] = bytes[j];
    out[i * 4 + 1] = bytes[j + 1];
    out[i * 4 + 2] = bytes[j + 2];
    out[i * 4 + 3] = 255;
  }
  return new ImageData(out, width, height);
}
