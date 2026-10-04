"""Builds docs/data/collectibles.json and the map images from Nehrim.esm, Translation.esp and the Collection plugins."""
import json, math, re, struct
from collections import Counter, deque
from pathlib import Path
from PIL import Image
import bsa, tes4

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'data'
SCRIPTS = {'NehrimSymbolScript': 'symbol', 'UNIPerFeuerfunkeScript': 'firespark', 'UNIPerEisprankeScript': 'iceclaw'}
# Item base forms by editor ID: (kind, id prefix, is a loose ingredient)
ITEMS = {
    '1AlmanachDerBeschwoerung': ('almanac', 'AC', False),
    '1TrankTragkraft': ('potion', 'PE', False),
    'UNIFeuerfunkenkapsel': ('firespark', 'FS-I', True),
    'UNIEispranke': ('iceclaw', 'IC-I', True),
}
# Copies in an actor's or container's inventory (holder is the base form); found once the save shows them taken.
CARRIED = [
    dict(item='1AlmanachDerBeschwoerung', holder=0x23b9c0, count=1,
         note='Carried by this boss during the main quest The Task of Fathoming.'),
    dict(item='UNIFeuerfunkenkapsel', holder=0x1d8735, count=1,
         note="On the Dwarven Thief's corpse, side quest The Dwarven Thief."),
    dict(item='UNIEispranke', holder=0x2331fb, count=2,
         note='In the hard reward barrel of the side quest Advanced Tower Defense.'),
]
COLLECTION_PLUGINS = ['Magic Symbol Collection.esp', 'Fire Sparks Collection.esp', 'Ice Claws Collection.esp']
TEST_CELLS = {'GameplayNewObjects'}
NEHRIM, ARKTWEND = 0x809, 0x1b1696
MAP_MARKER = 0x10
NEHRIM_SYMBOL_VAR = 0x2098f5
UNITS_PER_M = 70.0

# Image crop in texture pixels (left, top, right, bottom); the texture is 2048x2048.
# Nehrim comes from SureAI's own map instead (tools/fetch_tiles.py), so it carries their projection: offsets are in
# cells and are applied before the scale, per https://map.nehrim.sureai.net/Config.js.
WORLDS = {
    NEHRIM: dict(key='nehrim', tiles=dict(path='map/nehrim', size=256, min=2, max=5),
                 proj=dict(sx=97.0, ox=65.75, sy=101.5, oy=45.65)),
    ARKTWEND: dict(key='arktwend', tex='arktwendworldmapkontinental.dds', crop=(600, 380, 1500, 960)),
}

REALM_NAMES = {'MQ37Start': 'Main quest: The Task of Fathoming', 'MQ37ErothinVorhof': 'Main quest: The Task of Fathoming'}
# Interiors only reachable through quest teleports; door-following would pin them somewhere misleading.
NO_MAP_CELLS = {'InodanSeraphimgruft'}
# Realms with no load door back out; pin their contents at the world marker you go through to reach them.
REALM_ENTRANCES = {'DarothmarWorldPart01': 'Portal of Darothmar', 'DarothmarWorldPart02': 'Portal of Darothmar'}
PLANT_NOTES = {
    'FS01': 'Only reachable during the main quest The Task of Fathoming. On the shore of the Lonely Island, about 75 m '
            'north of the door you arrive through, among the beach rocks. Gone once the quest is over.',
    'FS04': 'Only reachable during the main quest The Task of Fathoming. In the fern forest, about 20 m north-east of '
            'the door you arrive through. Gone once the quest is over.',
    'FS02': 'Stoneworld (Zerobilon).',
    'FS03': 'Inside the Portal of Darothmar.',
    'IC001': 'Sildren Mountain Camp.',
    'IC002': 'Portal of Darothmar.',
    'IC003': 'Inside the Portal of Darothmar, part 2.',
    'IC004': 'Inside the Portal of Darothmar, part 2.',
}

esm = tes4.load('Nehrim.esm')
byid = {r.fid: r for r in esm}
trans = {r.fid: r for r in tes4.load('Translation.esp')}


def u32(b):
    return struct.unpack('<I', b[:4])[0]


def text(b):
    # Translation.esp has "üR" where the German original had an opening quote mark.
    return re.sub(r'\s*üR', ' ', tes4.zs(b)).strip()


def full(fid):
    r = trans.get(fid) or byid.get(fid)
    return text(r.sub('FULL')) if r is not None and r.sub('FULL') else ''


def place(r):
    cell = wrld = None
    for gtype, label in r.path:
        lid = struct.unpack('<I', label)[0]
        if gtype == 1:
            wrld = lid
        elif gtype in (6, 8, 9, 10):
            cell = lid
    return cell, wrld


parent = {r.fid: u32(r.sub('WNAM')) for r in esm if r.type == 'WRLD' and r.sub('WNAM')}


def main_world(w):
    seen = set()
    while w is not None and w not in WORLDS and w not in seen:
        seen.add(w)
        w = parent.get(w)
    return w if w in WORLDS else None


script_kind = {r.fid: SCRIPTS[r.edid] for r in esm if r.type == 'SCPT' and r.edid in SCRIPTS}
base_kind = {r.fid: script_kind[u32(r.sub('SCRI'))] for r in esm
             if r.type in ('ACTI', 'FLOR') and r.sub('SCRI') and u32(r.sub('SCRI')) in script_kind}
base_kind.update({r.fid: ITEMS[r.edid][0] for r in esm if r.type in ('MISC', 'INGR') and r.edid in ITEMS})

refs, doors_by_cell, cells_by_world, placed_by_base, markers = {}, {}, {}, {}, []
for r in esm:
    if r.type not in ('REFR', 'ACHR', 'ACRE'):
        continue
    cell, wrld = place(r)
    pos = struct.unpack('<3f', r.sub('DATA')[:12])
    refs[r.fid] = (cell, wrld, pos)
    base = u32(r.sub('NAME'))
    placed_by_base.setdefault(base, []).append(r.fid)
    if wrld is not None:
        cells_by_world.setdefault(wrld, set()).add(cell)
    if r.sub('XTEL'):
        doors_by_cell.setdefault(cell, []).append(u32(r.sub('XTEL')))
    if base == MAP_MARKER and wrld is not None:
        t = trans.get(r.fid, r)
        if t.sub('FULL'):
            markers.append(dict(name=text(t.sub('FULL')), wrld=wrld, x=pos[0], y=pos[1]))

DIRS = ['E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE']


def nearest_marker(wrld, x, y):
    cands = [m for m in markers if main_world(m['wrld']) == wrld]
    m = min(cands, key=lambda m: math.hypot(x - m['x'], y - m['y']))
    d = math.hypot(x - m['x'], y - m['y'])
    ang = math.degrees(math.atan2(y - m['y'], x - m['x'])) % 360
    return dict(name=m['name'], metres=round(d / UNITS_PER_M), dir=DIRS[int((ang + 22.5) // 45) % 8])


def exit_to_overworld(seeds, home_world):
    """BFS through load doors to a door in Nehrim (or Arktwend if that is all there is); never walks through other realms."""
    seen, q, fallback = set(seeds), deque(seeds), None
    while q:
        c = q.popleft()
        for dest in doors_by_cell.get(c, []):
            if dest not in refs:
                continue
            dcell, dwrld, dpos = refs[dest]
            if dwrld is not None and dwrld != home_world:
                mw = main_world(dwrld)
                if mw == NEHRIM:
                    return mw, dpos
                if mw == ARKTWEND and fallback is None:
                    fallback = (mw, dpos)
                continue
            if dcell not in seen:
                seen.add(dcell)
                q.append(dcell)
    return fallback


def map_uv(wrld, x, y):
    pr = WORLDS[wrld].get('proj')
    if pr:
        return (round((x / 4096 + pr['ox']) / pr['sx'], 5),
                round(1 - (y / 4096 + pr['oy']) / pr['sy'], 5))
    w = byid[wrld]
    # MNAM's usable dimensions, not the texture size, set the scale: the painting overruns 2048 and is cropped right and bottom.
    ux, uy, nwx, nwy, sex, sey = struct.unpack('<2i4h', w.sub('MNAM'))
    fx = (x / 4096 - nwx) / (sex - nwx + 1) * ux
    fy = (nwy + 1 - y / 4096) / (nwy - sey + 1) * uy
    l, t, r, b = WORLDS[wrld]['crop']
    return round((fx - l) / (r - l), 5), round((fy - t) / (b - t), 5)


def locate(item, cell, wrld, pos):
    c = byid[cell]
    item['interior'] = wrld is None
    if wrld is None:
        item['area'] = full(cell) or c.edid
        item['cell'] = c.edid
    elif main_world(wrld) is None:
        item['area'] = REALM_NAMES.get(byid[wrld].edid) or full(wrld) or byid[wrld].edid
        item['realm'] = True
    mw = main_world(wrld) if wrld is not None else None
    if c.edid in NO_MAP_CELLS:
        item['realm'] = True
        ow = None
    elif mw is not None:
        ow = (mw, pos)
    else:
        ow = exit_to_overworld(list(cells_by_world[wrld]) if wrld else [cell], wrld)
    if not ow and wrld is not None:
        entrance = REALM_ENTRANCES.get(byid[wrld].edid)
        if entrance:
            m = next((m for m in markers if m['name'] == entrance), None)
            assert m, f'no map marker named {entrance!r}'
            ow = (main_world(m['wrld']), (m['x'], m['y']))
    if ow:
        owrld, opos = ow
        u, v = map_uv(owrld, opos[0], opos[1])
        item['map'] = dict(world=WORLDS[owrld]['key'], u=u, v=v)
        item['near'] = nearest_marker(owrld, opos[0], opos[1])
        item['viaDoor'] = opos is not pos


def wiki_symbol_notes():
    lines = (ROOT / 'research' / 'fandom_Magic_Symbols.txt').read_text(encoding='utf-8').split('\n')

    def clean(s):
        s = re.sub(r'^\|\s*(style="[^"]*"\s*)?\|?', '', s).strip()
        s = re.sub(r'\[\[([^\]|]*)\|([^\]]*)\]\]', r'\2', s)
        s = re.sub(r'\[\[([^\]]*)\]\]', r'\1', s)
        return re.sub(r'\s+', ' ', s).strip()

    rows, i = {}, 0
    while i < len(lines):
        m = re.match(r'^\|\s*(style="[^"]*"\s*)?\|\s*(\d+)\s*$', lines[i])
        if m:
            j = i + 1
            loc = clean(lines[j])
            if not loc:
                j += 1
                loc = clean(lines[j])
            num = int(m.group(2))
            # The wiki numbers Thoian's Hideout 36 as well; it is the 37th row.
            if num in rows:
                num += 1
            rows[num] = dict(loc=loc, note=clean(lines[j + 1]))
            i = j + 1
        i += 1
    ids = json.loads((ROOT / 'tools' / 'symbol_wiki_map.json').read_text())
    assert sorted(ids.values()) == list(range(1, 101)), 'symbol_wiki_map must use each wiki row once'
    return {sid: rows[n] for sid, n in ids.items()}


collection_ids = {}
for p in COLLECTION_PLUGINS:
    for r in tes4.load(p):
        if r.type == 'REFR' and r.edid.endswith('Ref') and r.fid >> 24 == 0:
            collection_ids[r.fid] = r.edid[:-3]

symbol_notes = wiki_symbol_notes()
item_notes = json.loads((ROOT / 'tools' / 'item_notes.json').read_text(encoding='utf-8'))
items = []
for r in esm:
    if r.type != 'REFR' or u32(r.sub('NAME')) not in base_kind:
        continue
    cell, wrld, pos = refs[r.fid]
    c = byid[cell]
    if c.edid in TEST_CELLS:
        continue
    base = byid[u32(r.sub('NAME'))]
    kind = base_kind[base.fid]
    item = dict(id=collection_ids.get(r.fid, ''), kind=kind, ref=r.fid, base=base.edid)
    if base.edid in ITEMS and ITEMS[base.edid][2]:
        item['ingredient'] = True
    locate(item, cell, wrld, pos)
    if item['id'] in symbol_notes:
        item['note'] = symbol_notes[item['id']]['note']
        item['wikiLoc'] = symbol_notes[item['id']]['loc']
    elif item['id'] in PLANT_NOTES:
        item['note'] = PLANT_NOTES[item['id']]
    elif c.edid in item_notes.get(kind, {}):
        item['note'] = item_notes[kind][c.edid]
    items.append(item)

item_base = {r.edid: r.fid for r in esm if r.type in ('MISC', 'INGR') and r.edid in ITEMS}
for spec in CARRIED:
    kind, _, ingredient = ITEMS[spec['item']]
    holder = placed_by_base[spec['holder']][0]
    for nth in range(1, spec['count'] + 1):
        item = dict(id='', kind=kind, ref=0, base=spec['item'], holder=holder, item=item_base[spec['item']], nth=nth, note=spec['note'])
        if ingredient:
            item['ingredient'] = True
        locate(item, *refs[holder])
        item['area'] = ', '.join(x for x in (full(spec['holder']), item.get('area')) if x)
        items.append(item)

for edid, (_, prefix, _) in ITEMS.items():
    group = sorted((i for i in items if i['base'] == edid), key=lambda i: (i['ref'] == 0, i['ref']))
    for n, it in enumerate(group, 1):
        it['id'] = f'{prefix}{n:02d}'
for i in items:
    del i['base']
assert all(i['id'] for i in items)

items.sort(key=lambda i: i['id'])
worlds = {}
OUT.mkdir(parents=True, exist_ok=True)
for fid, w in WORLDS.items():
    if w.get('tiles'):
        # fetch_tiles.py mirrors the tiles and flattens one of the zoom levels into this image.
        im = Image.open(OUT / f"{w['key']}.webp")
    else:
        raw = bsa.extract(bsa.DATA / 'L - Misc.bsa', rf"textures\menus\map\world\{w['tex']}")
        tmp = ROOT / 'research' / 'maps' / f"{w['key']}.dds"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(raw)
        im = Image.open(tmp).convert('RGB').crop(w['crop'])
        im.save(OUT / f"{w['key']}.webp", quality=94, method=6)
    worlds[w['key']] = dict(name=full(fid), image=f"data/{w['key']}.webp", width=im.width, height=im.height)
    if w.get('tiles'):
        worlds[w['key']]['tiles'] = w['tiles']

(OUT / 'collectibles.json').write_text(json.dumps(
    dict(worlds=worlds, symbolVar=NEHRIM_SYMBOL_VAR, items=items),
    ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

print(Counter((i['kind'], 'ingredient' if i.get('ingredient') else '', 'carried' if i.get('holder') else '') for i in items))
print('no map position:', [(i['id'], i['area']) for i in items if 'map' not in i])
print('on arktwend map:', [(i['id'], i.get('area')) for i in items if i.get('map', {}).get('world') == 'arktwend'])
print('new kinds:', [(i['id'], i['area'], i.get('note', '')[:40]) for i in items if i['kind'] in ('almanac', 'potion') or i.get('ingredient')])
