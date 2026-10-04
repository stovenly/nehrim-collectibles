"""Mirrors SureAI's Nehrim map tiles into docs/map as WebP. Run once; the tiles do not change."""
import io
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'map' / 'nehrim'
SRC = 'https://map.nehrim.sureai.net/Tiles/paper/en/{z}/{x}/{y}.png'
# Their projection puts the whole map in one quadrant, so zoom z is a 2**z grid of 256px tiles.
ZOOMS = range(2, 6)
UA = 'nehrim-collectibles-tracker/1.0 (one-off mirror of the Nehrim map for stovenly.github.io/nehrim-collectibles)'


def fetch(z, x, y):
    dest = OUT / str(z) / str(x) / f'{y}.webp'
    if dest.exists():
        return 0
    req = urllib.request.Request(SRC.format(z=z, x=x, y=y), headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except Exception as e:
        print(f'  {z}/{x}/{y}: {e}', file=sys.stderr)
        return -1
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, format='WEBP', quality=86, method=6)
    return dest.stat().st_size


for z in ZOOMS:
    n = 2 ** z
    jobs = [(z, x, y) for x in range(n) for y in range(n)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        sizes = list(pool.map(lambda a: fetch(*a), jobs))
    got = [s for s in sizes if s > 0]
    print(f'zoom {z}: {n}x{n} tiles, {len(got)} written, {sum(sizes[i] for i in range(len(sizes)) if sizes[i] > 0) / 1048576:.1f} MB'
          f'{", " + str(sizes.count(-1)) + " failed" if -1 in sizes else ""}', flush=True)

total = sum(f.stat().st_size for f in OUT.rglob('*.webp'))
print(f'total {total / 1048576:.1f} MB in {sum(1 for _ in OUT.rglob("*.webp"))} tiles')

# Flatten zoom 3 into the still image the map falls back to before tiles load, and that the link card is built from.
FLAT = 3
flat = Image.new('RGB', (256 * 2 ** FLAT,) * 2)
for x in range(2 ** FLAT):
    for y in range(2 ** FLAT):
        flat.paste(Image.open(OUT / str(FLAT) / str(x) / f'{y}.webp'), (x * 256, y * 256))
dest = ROOT / 'docs' / 'data' / 'nehrim.webp'
flat.save(dest, quality=92, method=6)
print(f'{dest.name}: {flat.width}x{flat.height}, {dest.stat().st_size / 1048576:.1f} MB')
