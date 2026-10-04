"""Lists the cells to export with the Construction Set's World > Create Local Maps, into research/cs_export_list.md."""
import json, struct
from collections import defaultdict
from pathlib import Path
import tes4

ROOT = Path(__file__).resolve().parent.parent
data = json.loads((ROOT / 'docs' / 'data' / 'collectibles.json').read_text(encoding='utf-8'))
esm = tes4.load('Nehrim.esm')
byid = {r.fid: r for r in esm}
trans = {r.fid: r for r in tes4.load('Translation.esp')}


def full(fid):
    r = trans.get(fid) or byid.get(fid)
    return tes4.zs(r.sub('FULL')) if r is not None and r.sub('FULL') else ''


where = {}
for r in esm:
    if r.type in ('REFR', 'ACHR', 'ACRE'):
        cell = wrld = None
        for gtype, label in r.path:
            lid = struct.unpack('<I', label)[0]
            if gtype == 1:
                wrld = lid
            elif gtype in (6, 8, 9, 10):
                cell = lid
        where[r.fid] = (cell, wrld, struct.unpack('<3f', r.sub('DATA')[:12]))

interiors = defaultdict(list)
exteriors = defaultdict(set)
for i in data['items']:
    cell, wrld, pos = where[i.get('holder') or i['ref']]
    if wrld is None:
        interiors[cell].append(i['id'])
    else:
        # Local maps show the cells around the item, so take the 3x3 block.
        gx, gy = int(pos[0] // 4096), int(pos[1] // 4096)
        exteriors[wrld].update((gx + dx, gy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))

lines = ['# Construction Set local map export', '',
         'World > Create Local Maps. Load only `Nehrim.esm` (and `Translation.esp` if the CS allows it).', '',
         '## Worldspaces', '',
         '| Worldspace (editor ID) | Name | Cells needed | Upper-left cell | Lower-right cell |', '|---|---|---|---|---|']
for wrld, cells in sorted(exteriors.items(), key=lambda kv: -len(kv[1])):
    xs, ys = [c[0] for c in cells], [c[1] for c in cells]
    lines.append(f'| `{byid[wrld].edid}` | {full(wrld) or "-"} | {len(cells)} | {min(xs)}, {max(ys)} | {max(xs)}, {min(ys)} |')
lines += ['', f'## Interior cells ({len(interiors)})', '', '| Editor ID | Name | Collectibles |', '|---|---|---|']
for cell, ids in sorted(interiors.items(), key=lambda kv: byid[kv[0]].edid.lower()):
    lines.append(f'| `{byid[cell].edid}` | {full(cell)} | {", ".join(sorted(ids))} |')

out = ROOT / 'research' / 'cs_export_list.md'
out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(out, f'{len(interiors)} interiors,', {byid[w].edid: len(c) for w, c in exteriors.items()})
