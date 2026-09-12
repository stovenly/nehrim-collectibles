import { parseSave, screenshotImageData, SaveError } from './ess.js';

const KINDS = {
  symbol: { name: 'Magic Symbols', one: 'Magic Symbol' },
  firespark: { name: 'Sparks of Fire Caps', one: 'Sparks of Fire Cap' },
  iceclaw: { name: 'Ice Claws', one: 'Ice Claw' },
  almanac: { name: 'Almanacs of Conjuration', one: 'Almanac of Conjuration' },
  potion: { name: 'Potions of Encumbrance', one: 'Potion of Encumbrance' },
};
const KNOWN_PLUGINS = new Set(['nehrim.esm', 'translation.esp', 'magic symbol collection.esp', 'fire sparks collection.esp', 'ice claws collection.esp']);

// app.js sits at <root>/js/, so this resolves assets the same from the landing page and from a collectible page.
const BASE = new URL('../', import.meta.url);
const asset = path => new URL(path, BASE).href;
// A collectible page declares its own kind; the landing page can be sent one with ?kind=<key>.
const linkedKind = document.body.dataset.kind || new URLSearchParams(location.search).get('kind');

const $ = id => document.getElementById(id);
const el = (tag, { dataset, ...props } = {}, ...kids) => {
  const e = Object.assign(document.createElement(tag), props);
  if (dataset) Object.assign(e.dataset, dataset);
  e.append(...kids.filter(k => k != null));
  return e;
};
const icon = kind => el('img', { className: 'icon', src: asset(`img/${kind}.png`), alt: '', draggable: false });

const state = {
  data: null,
  found: new Set(),
  kinds: new Set([Object.hasOwn(KINDS, linkedKind) ? linkedKind : 'symbol']),
  showFound: false,
  selected: new Set(),
  world: 'nehrim',
  view: { s: 1, x: 0, y: 0 },
};

const dataReady = fetch(asset('data/collectibles.json')).then(r => r.json()).then(d => (state.data = d));

// ---------- file input ----------

const drop = $('drop');
const fileInput = $('file');
// Not showOpenFilePicker: Chromium refuses files under Program Files, where Steam keeps the saves.
function choose() {
  fileInput.click();
}

drop.addEventListener('click', e => { if (!e.target.closest('.copy')) choose(); });
drop.addEventListener('keydown', e => { if (e.target === drop && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); choose(); } });
fileInput.addEventListener('change', () => fileInput.files[0] && load(fileInput.files[0]));
$('reload').addEventListener('click', choose);

for (const b of document.querySelectorAll('.copy')) {
  b.addEventListener('click', async () => {
    await navigator.clipboard.writeText(b.dataset.path);
    b.textContent = 'Copied';
    setTimeout(() => (b.textContent = 'Copy'), 1500);
  });
}
for (const t of ['dragenter', 'dragover']) window.addEventListener(t, e => { e.preventDefault(); drop.classList.add('over'); });
for (const t of ['dragleave', 'drop']) window.addEventListener(t, e => { e.preventDefault(); drop.classList.remove('over'); });
window.addEventListener('drop', e => e.dataTransfer.files[0] && load(e.dataTransfer.files[0]));

async function load(file) {
  $('error').hidden = true;
  try {
    const [bytes] = await Promise.all([file.arrayBuffer().then(b => new Uint8Array(b)), dataReady]);
    const save = parseSave(bytes);
    show(save, bytes);
  } catch (err) {
    console.error(err);
    $('error').textContent = err instanceof SaveError ? err.message : `Could not read that file: ${err.message}`;
    $('error').hidden = false;
  }
}

// ---------- results ----------

function show(save, bytes) {
  const nehrimIdx = save.plugins.findIndex(p => p.toLowerCase() === 'nehrim.esm');
  if (nehrimIdx < 0) throw new SaveError('This save does not use Nehrim.esm, so it is not a Nehrim save.');
  const hi = nehrimIdx << 24;
  const fid = local => (hi | local) >>> 0;

  const collected = i => i.holder ? -save.inventoryChange(fid(i.holder), fid(i.item)) >= i.nth : !!save.removed.get(fid(i.ref));
  state.found = new Set(state.data.items.filter(collected).map(i => i.id));

  const h = save.header;
  $('pc-name').textContent = h.name;
  $('pc-line').textContent = `Level ${h.level} · ${h.location}`;
  $('save-line').textContent = `Saved ${h.savedAt.toLocaleString()} · played ${formatPlaytime(h.playMs)}`;
  const shot = $('shot');
  if (h.screenshot) {
    shot.width = h.screenshot.width;
    shot.height = h.screenshot.height;
    shot.getContext('2d').putImageData(screenshotImageData(bytes, h.screenshot), 0, 0);
  } else {
    shot.width = shot.height = 0;
  }

  const warnings = $('warnings');
  warnings.replaceChildren();
  const extra = save.plugins.filter(p => !KNOWN_PLUGINS.has(p.toLowerCase()));
  if (extra.length) {
    warnings.append(el('p', { className: 'warn', textContent:
      `This save also uses ${extra.length === 1 ? 'a mod' : `${extra.length} mods`}: ${extra.join(', ')}. If any of them move or remove collectibles, some results may be wrong.` }));
  }
  const counter = save.globals.get(fid(state.data.symbolVar));
  const counted = state.data.items.filter(i => i.kind === 'symbol' && state.found.has(i.id)).length;
  if (counter != null && Math.round(counter) !== counted) {
    warnings.append(el('p', { className: 'warn', textContent:
      `The game's own symbol counter says ${Math.round(counter)}, but ${counted} symbols are marked collected in this save. A mod or console command may have changed some symbols.` }));
  }

  drop.hidden = true;
  $('about').hidden = true;
  $('results').hidden = false;
  renderTallies();
  renderChips();
  renderMapTabs();
  setWorld(state.world);
  render();
}

function formatPlaytime(ms) {
  const m = Math.floor(ms / 60000);
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`;
}

function renderTallies() {
  $('tallies').replaceChildren(...Object.entries(KINDS).map(([k, meta]) => {
    const all = state.data.items.filter(i => i.kind === k);
    const got = all.filter(i => state.found.has(i.id)).length;
    const left = all.length - got;
    return el('div', { className: 'tally paper', dataset: { kind: k } },
      el('div', { className: 'tally-head' }, icon(k), meta.name),
      el('div', { className: 'tally-num', innerHTML: `${got}<small> / ${all.length}</small>` }),
      el('div', { className: 'tally-sub', textContent: left ? `${left} still to find` : 'All found!' }),
      el('div', { className: 'bar' }, el('i', { style: `width:${(got / all.length) * 100}%` })));
  }));
}

function renderChips() {
  $('kind-chips').replaceChildren(...Object.entries(KINDS).map(([k, meta]) => {
    const b = el('button', { type: 'button', className: 'chip', dataset: { kind: k } }, icon(k), meta.name);
    b.setAttribute('aria-pressed', state.kinds.has(k));
    b.addEventListener('click', () => {
      state.kinds.has(k) ? state.kinds.delete(k) : state.kinds.add(k);
      b.setAttribute('aria-pressed', state.kinds.has(k));
      render();
    });
    return b;
  }));
}

$('show-found').addEventListener('change', e => { state.showFound = e.target.checked; render(); });

function title(i) {
  if (i.interior || i.realm || i.holder) return i.area;
  if (i.wikiLoc) return i.wikiLoc;
  return i.near ? `Near ${i.near.name}` : i.area;
}

function where(i) {
  const bits = [];
  if (i.ingredient) bits.push('Ingredient');
  if (i.near) {
    const rel = i.near.metres < 25 ? `at ${i.near.name}` : `${i.near.metres} m ${i.near.dir} of ${i.near.name}`;
    bits.push(i.viaDoor ? `Entrance ${rel}` : rel[0].toUpperCase() + rel.slice(1));
  }
  if (i.map?.world === 'arktwend') bits.push('Arktwend');
  if (i.realm && !i.map) bits.push('Separate area, not on the world map');
  if (i.cell) bits.push(`cell ${i.cell}`);
  return bits.join(' · ');
}

function visible() {
  return state.data.items.filter(i => state.kinds.has(i.kind) && (state.showFound || !state.found.has(i.id)));
}

function render() {
  const items = visible().sort((a, b) => title(a).localeCompare(title(b)) || a.id.localeCompare(b.id));
  const missing = items.filter(i => !state.found.has(i.id)).length;
  $('list-count').textContent = !state.kinds.size ? 'Pick a collectible type above.'
    : items.length ? `${missing} missing${state.showFound ? `, ${items.length - missing} collected` : ''}`
    : 'All found.';
  $('list').replaceChildren(...items.map(listItem));
  renderPins(items);
}

function listItem(i) {
  const found = state.found.has(i.id);
  const li = el('li', { className: `item${found ? ' found' : ''}${state.selected.has(i.id) ? ' active' : ''}`, id: `item-${i.id}`, dataset: { kind: i.kind } },
    el('div', { className: 'item-top' },
      icon(i.kind),
      el('span', { className: 'item-title', textContent: title(i) }),
      found ? el('span', { className: 'badge ok', textContent: 'collected' }) : null,
      el('span', { className: 'item-id', textContent: i.id, title: i.ref ? `${KINDS[i.kind].one} · reference ${i.ref.toString(16).toUpperCase().padStart(8, '0')}` : KINDS[i.kind].one })),
    el('div', { className: 'item-where', textContent: where(i) }),
    i.note ? el('div', { className: 'item-note', textContent: i.note }) : null);
  li.addEventListener('click', () => { select([i]); focusItem(i); });
  return li;
}

// ---------- map ----------

const map = $('map');
const stage = $('stage');
const pins = $('pins');
const img = $('map-img');
const tiles = $('tiles');
const tip = $('tip');

function renderMapTabs() {
  const worlds = Object.entries(state.data.worlds);
  $('map-tabs').replaceChildren(...worlds.map(([k, w]) => {
    const b = el('button', { type: 'button', role: 'tab', textContent: w.name, dataset: { world: k } });
    b.addEventListener('click', () => { setWorld(k); render(); });
    return b;
  }));
}

function setWorld(k) {
  state.world = k;
  const w = state.data.worlds[k];
  for (const b of $('map-tabs').children) b.setAttribute('aria-selected', b.dataset.world === k);
  map.style.aspectRatio = `${w.width} / ${w.height}`;
  img.src = asset(w.image);
  tiles.replaceChildren();
  tileEls.clear();
  resetView();
}

function renderPins(items) {
  pins.replaceChildren();
  const groups = new Map();
  for (const i of items) {
    if (i.map?.world !== state.world) continue;
    const key = `${i.kind}|${i.map.u.toFixed(3)}|${i.map.v.toFixed(3)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(i);
  }
  const frag = document.createDocumentFragment();
  for (const group of groups.values()) {
    const i = group[0];
    const allFound = group.every(g => state.found.has(g.id));
    const pin = el('div', { className: `pin ${i.kind}${allFound ? ' found' : ''}`, dataset: { kind: i.kind, ids: group.map(g => g.id).join(' ') } },
      el('img', { src: asset(`img/${i.kind}.png`), alt: '', draggable: false }), group.length > 1 ? el('span', { textContent: group.length }) : null);
    pin._u = i.map.u;
    pin._v = i.map.v;
    pin._items = group;
    frag.append(pin);
  }
  pins.append(frag);
  layoutPins();
}

let laidOut = null;
function layoutPins() {
  const { width, height } = map.getBoundingClientRect();
  const s = state.view.s;
  for (const pin of pins.children) {
    pin.style.left = `${pin._u * width * s}px`;
    pin.style.top = `${pin._v * height * s}px`;
  }
  laidOut = `${width}|${s}`;
}

pins.addEventListener('pointerover', e => {
  const pin = e.target.closest('.pin');
  if (!pin) return;
  tip.replaceChildren(...pin._items.map(i => el('div', {}, el('strong', { textContent: title(i) }), state.found.has(i.id) ? ' (collected)' : '')));
  tip.hidden = false;
  placeTip(pin);
});
pins.addEventListener('pointerout', e => { if (e.target.closest('.pin')) tip.hidden = true; });

function placeTip(pin) {
  const m = map.getBoundingClientRect();
  const p = pin.querySelector('img').getBoundingClientRect();
  let x = p.right - m.left + 6, y = p.top - m.top;
  if (x + tip.offsetWidth > m.width) x = Math.max(4, p.left - m.left - 6 - tip.offsetWidth);
  if (y + tip.offsetHeight > m.height) y = p.bottom - m.top - tip.offsetHeight;
  tip.style.left = `${x}px`;
  tip.style.top = `${y}px`;
}

pins.addEventListener('click', e => {
  const pin = e.target.closest('.pin');
  if (pin && !moved) select(pin._items, true);
});

function select(items, scroll = false) {
  state.selected = new Set(items.map(i => i.id));
  for (const n of $('list').querySelectorAll('.item.active')) n.classList.remove('active');
  const nodes = items.map(i => document.getElementById(`item-${i.id}`)).filter(Boolean);
  for (const n of nodes) {
    n.classList.add('active');
    n.classList.remove('flash');
    void n.offsetWidth;
    n.classList.add('flash');
  }
  if (scroll && nodes[0]) nodes[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function focusItem(i) {
  if (!i.map) return;
  if (i.map.world !== state.world) { setWorld(i.map.world); render(); }
  const { width, height } = map.getBoundingClientRect();
  const s = Math.max(state.view.s, 3);
  animateView({ s, x: width / 2 - i.map.u * width * s, y: height / 2 - i.map.v * height * s });
  const pin = [...stage.querySelectorAll('.pin')].find(p => p._items.includes(i));
  if (pin) { pin.classList.remove('hot'); void pin.offsetWidth; pin.classList.add('hot'); }
  if (matchMedia('(max-width: 900px)').matches) map.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function resetView() {
  stopAnim();
  state.view = { s: 1, x: 0, y: 0 };
  applyView();
}

function applyView() {
  const { width, height } = map.getBoundingClientRect();
  const v = state.view;
  v.s = Math.min(12, Math.max(1, v.s));
  v.x = Math.min(0, Math.max(width - width * v.s, v.x));
  v.y = Math.min(0, Math.max(height - height * v.s, v.y));
  // Sized in real pixels and only translated: a scale() here would make the browser stretch one cached raster of the
  // whole map instead of drawing the tiles at their own resolution.
  stage.style.width = `${width * v.s}px`;
  stage.style.height = `${height * v.s}px`;
  stage.style.transform = `translate(${v.x}px, ${v.y}px)`;
  if (laidOut !== `${width}|${v.s}`) layoutPins();
  pins.style.transform = `translate(${v.x}px, ${v.y}px)`;
  renderTiles(width, height);
  tip.hidden = true;
}

// The flat image under .tiles is the whole map at zoom 3, so it stands in wherever sharper tiles are not loaded yet.
const tileEls = new Map();
function renderTiles(width, height) {
  const t = state.data.worlds[state.world].tiles;
  if (!t) return;
  const v = state.view;
  const z = Math.max(t.min, Math.min(t.max, Math.ceil(Math.log2((width * v.s) / t.size))));
  const n = 2 ** z;
  const side = (width * v.s) / n;
  const first = (off, box) => [Math.max(0, Math.floor(-off / side)), Math.min(n - 1, Math.floor((box - off) / side))];
  const [x0, x1] = first(v.x, width);
  const [y0, y1] = first(v.y, height);
  const keep = new Set();
  for (let x = x0; x <= x1; x++) {
    for (let y = y0; y <= y1; y++) {
      const key = `${z}/${x}/${y}`;
      keep.add(key);
      let e = tileEls.get(key);
      if (!e) {
        e = el('img', { src: asset(`${t.path}/${key}.webp`), alt: '', draggable: false, decoding: 'async' });
        tiles.append(e);
        tileEls.set(key, e);
      }
      e.style.cssText = `left:${x * side}px;top:${y * side}px;width:${side}px;height:${side}px`;
    }
  }
  for (const [key, e] of tileEls) {
    if (!keep.has(key)) {
      e.remove();
      tileEls.delete(key);
    }
  }
}

// Tweened in JS, not by a CSS transition: the pin layer has to track the map's scale frame by frame.
let anim = null;
const stopAnim = () => { if (anim) cancelAnimationFrame(anim); anim = null; };

function animateView(to, ms = 350) {
  stopAnim();
  const from = { ...state.view };
  const t0 = performance.now();
  const step = now => {
    const k = Math.min(1, (now - t0) / ms);
    const e = k < .5 ? 2 * k * k : 1 - (2 - 2 * k) ** 2 / 2;
    state.view = { s: from.s + (to.s - from.s) * e, x: from.x + (to.x - from.x) * e, y: from.y + (to.y - from.y) * e };
    applyView();
    anim = k < 1 ? requestAnimationFrame(step) : null;
  };
  anim = requestAnimationFrame(step);
}

function zoomAt(factor, cx, cy) {
  stopAnim();
  const v = state.view;
  const s = Math.min(12, Math.max(1, v.s * factor));
  v.x = cx - (cx - v.x) * (s / v.s);
  v.y = cy - (cy - v.y) * (s / v.s);
  v.s = s;
  applyView();
}

map.addEventListener('wheel', e => {
  e.preventDefault();
  const r = map.getBoundingClientRect();
  zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
}, { passive: false });

$('zoom-in').addEventListener('click', () => { const r = map.getBoundingClientRect(); zoomAt(1.6, r.width / 2, r.height / 2); });
$('zoom-out').addEventListener('click', () => { const r = map.getBoundingClientRect(); zoomAt(1 / 1.6, r.width / 2, r.height / 2); });
$('zoom-reset').addEventListener('click', resetView);
window.addEventListener('resize', () => state.data && applyView());

const pointers = new Map();
let moved = false;
let start = null;
let pinch = null;
// Capture only once a drag starts: capturing on pointerdown retargets the click away from the pin.
map.addEventListener('pointerdown', e => {
  if (e.target.closest('.map-ctrl')) return;
  stopAnim();
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  start = { x: e.clientX, y: e.clientY };
  moved = false;
  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    pinch = Math.hypot(a.x - b.x, a.y - b.y);
  }
  map.classList.add('dragging');
});
map.addEventListener('pointermove', e => {
  const prev = pointers.get(e.pointerId);
  if (!prev) return;
  const cur = { x: e.clientX, y: e.clientY };
  pointers.set(e.pointerId, cur);
  if (pointers.size === 2 && pinch) {
    const [a, b] = [...pointers.values()];
    const d = Math.hypot(a.x - b.x, a.y - b.y);
    const r = map.getBoundingClientRect();
    zoomAt(d / pinch, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top);
    pinch = d;
    moved = true;
    return;
  }
  if (!moved && Math.hypot(cur.x - start.x, cur.y - start.y) > 4) {
    moved = true;
    map.setPointerCapture(e.pointerId);
  }
  if (moved) {
    state.view.x += cur.x - prev.x;
    state.view.y += cur.y - prev.y;
    applyView();
  }
});
const endPointer = e => {
  pointers.delete(e.pointerId);
  if (pointers.size < 2) pinch = null;
  if (!pointers.size) map.classList.remove('dragging');
};
map.addEventListener('pointerup', endPointer);
map.addEventListener('pointercancel', endPointer);
