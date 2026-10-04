"""Exports the game icons and menu textures the site uses into docs/img."""
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
import bsa, tes4

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'img'
DATA = ROOT / 'docs' / 'data'
RESEARCH = ROOT / 'research'


def tex(path):
    name = 'textures' + chr(92) + path.replace('/', chr(92))
    for p in sorted(bsa.DATA.glob('*.bsa')):
        b = bsa.extract(p, name)
        if b:
            return Image.open(io.BytesIO(b)).convert('RGBA')
    raise FileNotFoundError(path)


OUT.mkdir(parents=True, exist_ok=True)
tex('menus/icons/iconfeuerfunkekapsel.dds').save(OUT / 'firespark.png', optimize=True)
tex('menus/icons/iconeispranke.dds').save(OUT / 'iceclaw.png', optimize=True)
misc = {r.edid: r for r in tes4.load('Nehrim.esm') if r.type == 'MISC'}
for kind, edid in (('almanac', '1AlmanachDerBeschwoerung'), ('potion', '1TrankTragkraft')):
    im = tex('menus/icons/' + tes4.zs(misc[edid].sub('ICON')).replace(chr(92), '/'))
    im.thumbnail((64, 64), Image.LANCZOS)
    im.save(OUT / f'{kind}.png', optimize=True)
# The menu leather has a frame and corner ornaments; mirror a clean interior patch into a seamless tile.
patch = tex('menus/shared/main_background.dds').crop((160, 160, 672, 672)).convert('RGB')
tile = Image.new('RGB', (1024, 1024))
tile.paste(patch, (0, 0))
tile.paste(patch.transpose(Image.FLIP_LEFT_RIGHT), (512, 0))
tile.paste(patch.transpose(Image.FLIP_TOP_BOTTOM), (0, 512))
tile.paste(patch.transpose(Image.ROTATE_180), (512, 512))
tile.save(OUT / 'leather.jpg', quality=80, optimize=True, progressive=True)
tex('menus/shared/shared_paper_no_tabs.dds').save(OUT / 'paper.webp', quality=88)
tex('menus/shared/shared_border_horizontal_1.dds').save(OUT / 'rule.webp', quality=90)

# The Nehrim mark ships as near-black; retint it to the masthead's parchment tones so it reads on dark leather.
mark = Image.open(RESEARCH / 'nehrimicon.png').convert('RGBA')
lum = ImageOps.autocontrast(mark.convert('L').point(lambda v: min(255, int(v * 1.25))), cutoff=1)
gold = ImageOps.colorize(lum, (86, 58, 28), (242, 223, 178), (188, 150, 92), blackpoint=0, midpoint=118, whitepoint=255)
gold.putalpha(mark.split()[3])
trimmed = gold.crop(mark.split()[3].getbbox())
trimmed.resize((200, 200), Image.LANCZOS).save(OUT / 'mark.png', optimize=True)

# The mark is gold on nothing, so a favicon needs the dark ground under it to survive a light browser tab.
ico = Image.new('RGBA', (512, 512), (27, 18, 10, 255))
glyph = trimmed.copy()
glyph.thumbnail((408, 408), Image.LANCZOS)
ico.paste(glyph, ((512 - glyph.width) // 2, (512 - glyph.height) // 2), glyph)
ico.convert('RGB').save(ROOT / 'docs' / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
ico.resize((180, 180), Image.LANCZOS).save(OUT / 'icon-180.png', optimize=True)

# In game a Magic Symbol burns orange with a yellow core, not gold; midpoint 170 keeps the orange dominant at 30px.
bright = ImageOps.colorize(lum, (132, 34, 4), (255, 206, 30), (226, 96, 4), blackpoint=0, midpoint=170, whitepoint=255)
bright.putalpha(mark.split()[3])
glyph = bright.crop(mark.split()[3].getbbox())
glyph.thumbnail((64, 64), Image.LANCZOS)
sym = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
sym.paste(glyph, ((64 - glyph.width) // 2, (64 - glyph.height) // 2), glyph)
sym.save(OUT / 'symbol.png', optimize=True)


def og_card():
    """1200x630 link-preview card: the world map dimmed back to a backdrop, with the title and the five icons."""
    W, H = 1200, 630
    card = Image.open(DATA / 'nehrim.webp').convert('RGB').crop((250, 380, 1750, 1168)).resize((W, H), Image.LANCZOS)
    card = Image.blend(card, Image.new('RGB', (W, H), (26, 17, 9)), 0.68)
    vig = Image.new('L', (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * .25, -H * .55, W * 1.25, H * 1.55), fill=255)
    card = Image.composite(card, Image.new('RGB', (W, H), (16, 10, 5)), vig.filter(ImageFilter.GaussianBlur(110)))

    d = ImageDraw.Draw(card)
    title = ImageFont.truetype(r'C:\Windows\Fonts\georgiab.ttf', 76)
    sub = ImageFont.truetype(r'C:\Windows\Fonts\georgia.ttf', 32)

    def centred(text, font, y, fill):
        for dx, dy in ((0, 3), (0, 0)):
            d.text((W / 2 + dx, y + dy), text, font=font, fill=(0, 0, 0) if dy else fill, anchor='mm')

    m = Image.open(OUT / 'mark.png').convert('RGBA').resize((108, 108), Image.LANCZOS)
    card.paste(m, (int(W / 2 - 54), 66), m)
    centred('Nehrim Collectibles Tracker', title, 255, (240, 225, 190))
    d.line([(W / 2 - 262, 305), (W / 2 + 262, 305)], fill=(146, 114, 64), width=2)
    centred('Drop in a save, see what you still have to find', sub, 348, (206, 180, 130))

    icons = [Image.open(OUT / f'{k}.png').convert('RGBA').resize((88, 88), Image.LANCZOS)
             for k in ('symbol', 'firespark', 'iceclaw', 'almanac', 'potion')]
    gap = 52
    x = int((W - (len(icons) * 88 + (len(icons) - 1) * gap)) / 2)
    for ic in icons:
        card.paste(ic, (x, 430), ic)
        x += 88 + gap
    card.save(OUT / 'og.jpg', quality=88, optimize=True, progressive=True)


og_card()

for f in sorted(OUT.iterdir()):
    print(f.name, f.stat().st_size)
