import struct, json, sys
from collections import defaultdict
import tes4

SCRIPTS = {'NehrimSymbolScript': 'symbol', 'UNIPerFeuerfunkeScript': 'firespark', 'UNIPerEisprankeScript': 'iceclaw'}

esm = tes4.load('Nehrim.esm')
tr = {r.fid: r for r in tes4.load('Translation.esp')}
byid = {r.fid: r for r in esm}

script_ids = {r.fid: SCRIPTS[r.edid] for r in esm if r.type == 'SCPT' and r.edid in SCRIPTS}
print('scripts', {hex(k): v for k, v in script_ids.items()})

bases = {}
for r in esm:
    s = r.sub('SCRI')
    if s and struct.unpack('<I', s)[0] in script_ids:
        bases[r.fid] = (script_ids[struct.unpack('<I', s)[0]], r.type, r.edid)
print('bases', {hex(k): v for k, v in bases.items()})


def full(fid):
    r = tr.get(fid) or byid.get(fid)
    return tes4.zs(r.sub('FULL')) if r and r.sub('FULL') else ''


out = []
for r in esm:
    if r.type not in ('REFR', 'ACHR'):
        continue
    b = struct.unpack('<I', r.sub('NAME'))[0]
    if b not in bases:
        continue
    cell = wrld = None
    for gtype, label in r.path:
        lid = struct.unpack('<I', label)[0]
        if gtype == 1:
            wrld = lid
        if gtype in (6, 8, 9, 10):
            cell = lid
    c = byid[cell]
    xclc = c.sub('XCLC')
    pos = struct.unpack('<6f', r.sub('DATA'))
    out.append(dict(
        kind=bases[b][0], ref=r.fid, edid=r.edid, flags=r.flags,
        cell=cell, cellEdid=c.edid, cellName=full(cell),
        interior=wrld is None, wrld=wrld, wrldEdid=byid[wrld].edid if wrld else None, wrldName=full(wrld) if wrld else None,
        grid=list(struct.unpack('<ii', xclc[:8])) if xclc else None,
        pos=[round(p, 1) for p in pos[:3]],
    ))

json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else 'esm_refs.json', 'w'), indent=1)
from collections import Counter
print(Counter(o['kind'] for o in out))
