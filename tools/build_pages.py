"""Builds a tracker page per collectible, and the sitemap, by retargeting docs/index.html."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'
SITE = 'https://stovenly.github.io/nehrim-collectibles/'

PAGES = {
    'symbol': dict(
        slug='magic-symbols', name='Magic Symbols', total=100,
        lead='Find the Magic Symbols you are missing',
        what='<p>There are 100 Magic Symbols hidden across Nehrim, most of them waiting at the end of a dungeon or '
             'cave. Each one is worth experience, and finding every one earns the Magic Nehrim achievement. They glow '
             'faintly in the dark, which helps only if you are already in the right room.</p>',
        why='<p>Your journal keeps a count of how many you have picked up, but never says which ones. Somewhere past '
            'the seventieth that count stops being much use: the only way to find the rest is to re-walk dungeons you '
            'already cleared and hope you spot what you missed.</p>',
        extra='<p>It also reads the game&rsquo;s own symbol counter and tells you when it disagrees with the save, '
              'which usually means a mod or a console command has touched one.</p>'),
    'firespark': dict(
        slug='sparks-of-fire-caps', name='Sparks of Fire Caps', total=89,
        lead='Find the Sparks of Fire Caps you are missing',
        what='<p>Sparks of Fire Caps are unique plants placed by hand around Nehrim, and eating one raises Luck '
             'permanently by 1. There are 89 in all: most growing somewhere out in the world, a few sitting loose as '
             'ingredients, and one on a corpse.</p>',
        why='<p>Nothing marks them and nothing counts them. They grow in open country rather than at the end of a '
            'dungeon, so the last few are scattered across ground you have no particular reason to walk again.</p>',
        extra=''),
    'iceclaw': dict(
        slug='ice-claws', name='Ice Claws', total=158,
        lead='Find the Ice Claws you are missing',
        what='<p>Ice Claws are unique plants placed by hand around Nehrim, and eating one raises Encumbrance '
             'permanently by 1. There are 158 of them, the largest set in the game: mostly growing plants, plus a few '
             'loose ingredients and two in a quest reward barrel.</p>',
        why='<p>With 158 spread over the whole map and no counter in the journal, keeping track by hand is hopeless. '
            'Most guides are short of the real total as well, so working from one leaves you hunting for plants it '
            'never listed.</p>',
        extra=''),
    'almanac': dict(
        slug='almanacs-of-conjuration', name='Almanacs of Conjuration', total=22,
        lead='Find the Almanacs of Conjuration you are missing',
        what='<p>Each Almanac of Conjuration raises Conjuration by 5 levels for 5 learning points. Finding your first '
             'one starts the side quest The Books of Conjuration, and there are 22 to collect &mdash; 21 sitting in '
             'the world and one carried by a boss.</p>',
        why='<p>They sit indoors, in crypts and halls and studies, so the last few come down to remembering which '
            'building you have already been through rather than where to start looking.</p>',
        extra=''),
    'potion': dict(
        slug='potions-of-encumbrance', name='Potions of Encumbrance', total=27,
        lead='Find the Potions of Encumbrance you are missing',
        what='<p>Each Potion of Encumbrance permanently raises Encumbrance by 10, and there are 27 of them. The wikis '
             'list fewer, because several exist only inside a quest.</p>',
        why='<p>That is what makes them the easiest set to lose. A good few are gone for good once the quest holding '
            'them ends, so it is worth knowing which ones you are still owed before you finish a questline.</p>',
        extra=''),
}


def about(spec):
    extra = spec['extra'] + '\n' if spec['extra'] else ''
    return f'''  <section id="about" class="about paper">
    <h2>{spec['lead']}</h2>
{spec['what']}
{spec['why']}

    <h2>What this page does</h2>
    <p>Drop your save in above and it works out which of the {spec['total']} {spec['name']} you have already taken.
      Whatever is left is listed with the location of each one and pinned on the world map, so you can see which
      corners of Nehrim still owe you something and clear them in one trip instead of one at a time.</p>
    <p>The save is read in your browser. Nothing is uploaded, and there is nothing to install.</p>
{extra}    <p>If you would rather see everything at once, the <a href="../">full tracker</a> covers all five kinds
      of collectible together.</p>
  </section>
'''


def retarget(src, kind, spec):
    n, name, slug = spec['total'], spec['name'], spec['slug']
    title = f'Nehrim {name} Tracker — see which of the {n} you are missing'
    desc = (f'Drop a Nehrim save on the page and see which of the {n} {name} you have not collected yet, '
            f'listed with their locations and pinned on the world map.')
    s = src
    s = re.sub(r'<title>.*?</title>', f'<title>{title}</title>', s, count=1)
    s = re.sub(r'<meta name="description" content=".*?">', f'<meta name="description" content="{desc}">', s, count=1)
    s = s.replace(f'<link rel="canonical" href="{SITE}">', f'<link rel="canonical" href="{SITE}{slug}/">')
    s = s.replace('<meta property="og:title" content="Nehrim Collectibles Tracker">',
                  f'<meta property="og:title" content="{title}">')
    s = s.replace('<meta name="twitter:title" content="Nehrim Collectibles Tracker">',
                  f'<meta name="twitter:title" content="{title}">')
    s = re.sub(r'<meta property="og:description" content=".*?">',
               f'<meta property="og:description" content="{desc}">', s, count=1)
    s = re.sub(r'<meta name="twitter:description" content=".*?">',
               f'<meta name="twitter:description" content="{desc}">', s, count=1)
    s = s.replace(f'<meta property="og:url" content="{SITE}">', f'<meta property="og:url" content="{SITE}{slug}/">')
    s = re.sub(r'<script type="application/ld\+json">.*?</script>', f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "Nehrim {name} Tracker",
  "url": "{SITE}{slug}/",
  "applicationCategory": "GameApplication",
  "operatingSystem": "Any browser",
  "browserRequirements": "Requires JavaScript",
  "offers": {{ "@type": "Offer", "price": "0", "priceCurrency": "USD" }},
  "description": "{desc}",
  "screenshot": "{SITE}img/og.jpg",
  "about": {{ "@type": "VideoGame", "name": "Nehrim: At Fate's Edge", "publisher": {{ "@type": "Organization", "name": "SureAI" }} }}
}}
</script>''', s, count=1, flags=re.S)

    for attr in ('href', 'src'):
        for d in ('img/', 'css/', 'js/', 'data/'):
            s = s.replace(f'{attr}="{d}', f'{attr}="../{d}')
    s = s.replace('href="favicon.ico"', 'href="../favicon.ico"')

    s = s.replace('<body>', f'<body data-kind="{kind}">', 1)
    s = s.replace('<h1>Nehrim Collectibles Tracker</h1>', f'<h1>Nehrim {name} Tracker</h1>', 1)
    s = s.replace('<main class="wrap">',
                  '<main class="wrap">\n  <nav class="crumbs"><a href="../">Nehrim Collectibles Tracker</a> '
                  f'&rsaquo; {name}</nav>\n', 1)

    start = s.index('  <section id="about"')
    end = s.index('</section>', start) + len('</section>\n')
    return s[:start] + about(spec) + s[end:]


src = (DOCS / 'index.html').read_text(encoding='utf-8')
for kind, spec in PAGES.items():
    d = DOCS / spec['slug']
    d.mkdir(parents=True, exist_ok=True)
    (d / 'index.html').write_text(retarget(src, kind, spec), encoding='utf-8')
    print(spec['slug'], spec['total'], spec['name'])

urls = [SITE] + [SITE + s['slug'] + '/' for s in PAGES.values()]
(DOCS / 'sitemap.xml').write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + ''.join(f'  <url>\n    <loc>{u}</loc>\n    <changefreq>monthly</changefreq>\n'
              f'    <priority>{"1.0" if u == SITE else "0.8"}</priority>\n  </url>\n' for u in urls)
    + '</urlset>\n', encoding='utf-8')
print('sitemap', len(urls), 'urls')
