"""Add colours that citadelbrands.com sells but the site doesn't list yet.

Run from the site folder:
    python tools/add_live_colours.py            # compare + download + update manifests
    python tools/add_live_colours.py --check    # only report the differences
    python tools/build_media.py                 # then rebuild assets/js/product-media.js
    python tools/build_stock.py                 # and stock/outlet, so stock rows match the new colours

How it works
  1. The newest tools/data/citadel_inventory_*.json (Citadel scraper export) gives each style's live
     colour range and its citadelbrands.com product page.
  2. Live colours are compared with assets/products/<code>/manifest.json. Spelling differences
     ("PFD" = Prepared for Dye, "Jet Black/ White" = Jet Black/Arctic White, ...) are not counted.
  3. For every missing colour the product page is read for that colour's packshot (hi-res PNG).
     The garment is placed on a white square like the other packshots: <code>/<colour>.jpg (1000px)
     and <code>/zoom/<colour>.jpg (2000px).
  4. The colour is appended to the manifest. Its swatch hex is sampled from the photo, because the
     hex values on citadelbrands.com are generic placeholders (e.g. Forest Green = #FFFFFF on JHA030).
     Official AWDis chart colours keep their chart hex (build_media.py applies the chart)."""
import sys, os, re, io, json, glob, urllib.request
from PIL import Image

CHECK = '--check' in sys.argv
UA = {'User-Agent': 'Mozilla/5.0 (Citadel site builder)'}
# live spelling -> site spelling (upper case, spaces around "/" removed)
SAME = {'PFD (PREPARED FOR DYE)': 'PREPARED FOR DYE', 'PFD': 'PREPARED FOR DYE', 'SHERBERT LEMON': 'SHERBET LEMON',
        'ELEC YELLOW': 'ELECTRIC YELLOW', 'HEATHER': 'HEATHER GREY', 'JET BLACK/WHITE': 'JET BLACK/ARCTIC WHITE',
        'OXFORD NAVY/WHITE': 'OXFORD NAVY/ARCTIC WHITE', 'HEATHER GRAY': 'HEATHER GREY'}
SAME_PER_STYLE = {('JHA101', 'JET BLACK'): 'BLACK'}     # the site lists this style's black as "Black"

def key(n):
    k = re.sub(r'\s*/\s*', '/', re.sub(r'\s+', ' ', n.strip().upper()))
    if '/' in k:      # two-tone short forms, as in build_media.title(): Sky = Sky Blue, White = Arctic White
        k = '/'.join({'SKY': 'SKY BLUE', 'WHITE': 'ARCTIC WHITE'}.get(x, x) for x in k.split('/'))
    return k
def slug(n): return re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-')
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()

src = sorted(glob.glob('tools/data/citadel_inventory_*.json'), key=lambda f: re.sub(r'\D', '', f))
if not src: sys.exit('No tools/data/citadel_inventory_*.json found.')
rows = json.load(open(src[-1], encoding='utf-8'))
rows = rows['rows'] if isinstance(rows, dict) else rows
live, page = {}, {}
for r in rows:
    if not r.get('style_code') or not r.get('color'): continue
    live.setdefault(r['style_code'], [])
    if r['color'] not in live[r['style_code']]: live[r['style_code']].append(r['color'])
    page[r['style_code']] = r.get('source_url')
print('live colour ranges from', src[-1])

def frame(img, size):
    """garment on a white square, ~88% of the height, centred (matches the existing packshots)"""
    img = img.convert('RGBA'); bg = Image.new('RGBA', img.size, (255, 255, 255, 255)); bg.alpha_composite(img)
    img = bg.convert('RGB')
    box = img.convert('L').point(lambda v: 255 if v < 245 else 0).getbbox() or (0, 0) + img.size
    img = img.crop(box)
    s = min(size * .883 / img.height, size * .9 / img.width)
    img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    out = Image.new('RGB', (size, size), 'white'); out.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return out, bg.convert('RGB').crop(box)

def sample_hex(garment):
    w, h = garment.size
    c = garment.crop((int(w * .3), int(h * .35), int(w * .7), int(h * .6))).resize((1, 1), Image.LANCZOS).getpixel((0, 0))
    return '#%02x%02x%02x' % c

total = 0
for code in sorted(live):
    mf = 'assets/products/%s/manifest.json' % code.lower()
    if not os.path.exists(mf):
        print('%-7s not on the site (no %s) — skipped' % (code, mf)); continue
    m = json.load(open(mf, encoding='utf-8'))
    have = {key(SAME.get(key(c['name']), c['name'])) for c in m.get('colours', [])}
    missing = [c for c in live[code] if key(SAME_PER_STYLE.get((code, key(c)), SAME.get(key(c), c))) not in have]
    if not missing: continue
    print('%-7s site %d · live %d · missing: %s' % (code, len(have), len(live[code]), ', '.join(missing)))
    total += len(missing)
    if CHECK: continue
    html = get(page[code]).decode('utf-8', 'replace')
    recs = {}
    for t in re.findall(r'\{"origStyleCode":.*?"imgAltText":"[^"]*"\}', html):
        try: d = json.loads(t)
        except ValueError: continue
        recs.setdefault(key(d.get('description', '')), d)
    base = 'assets/products/%s/' % code.lower()
    os.makedirs(base + 'zoom', exist_ok=True)
    for c in missing:
        d = recs.get(key(c))
        url = d and (d.get('imageZm') or d.get('imageLg'))
        if not url:
            print('   %s: no photo on the live page — added without a packshot' % c)
            m['colours'].append({'name': c, 'source': 'citadelbrands.com'}); continue
        img = Image.open(io.BytesIO(get(url)))
        big, garment = frame(img, 2000)
        f = slug(c)
        big.save(base + 'zoom/' + f + '.jpg', quality=88, optimize=True)
        big.resize((1000, 1000), Image.LANCZOS).save(base + f + '.jpg', quality=88, optimize=True)
        hx = sample_hex(garment)
        m['colours'].append({'name': c, 'hex': hx, 'file': f, 'source': 'citadelbrands.com', 'photo': url})
        print('   %-18s %s  <- %s' % (c, hx, url.rsplit('/', 1)[-1]))
    json.dump(m, open(mf, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)

print(('%d colour(s) missing' % total) + ('' if CHECK or not total else ' — added. Now run tools/build_media.py and tools/build_stock.py'))
