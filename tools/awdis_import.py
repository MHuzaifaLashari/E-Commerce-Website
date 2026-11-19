"""Import all product images from an awdis.com product page (UK or US site).

Usage (run from the site folder):
    python tools/awdis_import.py <awdis product url> <folder> [STYLECODE]
e.g.
    python tools/awdis_import.py https://awdis.com/us/products/college-hoodie-jha001/ jha001
    python tools/awdis_import.py https://awdis.com/us/products/awdis-150-t/ ata001 ATA001

Saves:
  assets/products/<folder>/gallery-N.jpg      model / lifestyle photos of this style, max 1000px
  assets/products/<folder>/<colour-slug>.jpg  one packshot per colour, max 1000px
  assets/products/<folder>/zoom/...           the same files at max 2000px (for the magnifier)
  assets/products/<folder>/manifest.json      colours (name, hex, file), gallery list, warnings
Options: --dry (only list), --gallery-only --prefix=uk (add another page's model photos as uk-N.jpg).
If awdis.com uses one photo for several colours, the photo is kept only for the colour whose hex
matches the garment (the others are listed under 'skipped')."""
import sys, os, re, io, json, time, html, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

args = [a for a in sys.argv[1:] if not a.startswith('--')]
DRY = '--dry' in sys.argv
GALLERY_ONLY = '--gallery-only' in sys.argv          # e.g. extra model photos from the UK page
PREFIX = ([a.split('=',1)[1] for a in sys.argv if a.startswith('--prefix=')] or ['gallery'])[0]
url, folder = args[0], args[1]
UA = {'User-Agent': 'Mozilla/5.0'}
UP = r'https://awdis\.com/(?:us/)?wp-content/uploads/(?:sites/\d+/)?\d{4}/\d{2}/'

def get(u, timeout=90):
    err = None
    for _ in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=timeout).read()
        except Exception as e: err = e; time.sleep(2)
    raise err

page = get(url, 60).decode('utf-8', 'ignore')

m = re.search(r'-(j[a-z]{1,2}\d{3}[a-z]?)/?$', url.rstrip('/'), re.I)
code = (args[2] if len(args) > 2 else (m.group(1) if m else '')).upper()

def variants(block):
    """all (url, width) candidates in a src/srcset block"""
    out = []
    for u, w in re.findall(r'(' + UP + r'[^\s",\']+?\.(?:jpe?g|png|webp))(?:\s+(\d+)w)?', block):
        if w: out.append((u, int(w))); continue
        mm = re.search(r'-(\d+)x\d+\.\w+$', u)
        out.append((u, int(mm.group(1)) if mm else 99999))   # -scaled / original = largest
    return out

def biggest(block):
    v = variants(block)
    return max(v, key=lambda x: x[1])[0] if v else None

# ---- colour swatches: <a title="NAME" data-hex-code=... data-featherlight="#colour-N"> + hidden <div id="colour-N"><img ...>
colours = []
for sm in re.finditer(r'<a href="#" title="([^"]+)" data-hex-code="([^"]*)" data-featherlight="#(colour-\d+)"', page):
    name, hexc, cid = html.unescape(sm.group(1)).strip(), sm.group(2), sm.group(3)
    i = page.find('id="%s"' % cid)
    block = page[i:page.find('</div>', i)]
    img = biggest(block)
    if img: colours.append((name, hexc, img))

# ---- gallery: photos whose file name starts with this style code (UK code JH001 or US code JHA001)
codes = {code}
if re.match(r'^J[HC]A\d{3}$', code): codes.add(code[:2] + code[3:])           # JHA001 -> JH001
if re.match(r'^ATA\d{3}$', code): codes |= {'AT' + code[3:], 'ATA' + code[3:]}
roots = {}
for u, w in variants(page):
    fn = u.rsplit('/', 1)[1]
    if not any(re.match(r'(?i)%s[_-]' % re.escape(c), fn) for c in codes): continue
    if re.search(r'(?i)(torso|front|back|swatch|thumb)', fn) and not re.search(r'_\d{2,3}(-|\.)', fn): continue
    root = re.sub(r'(-\d+x\d+|-scaled)?\.(jpe?g|png|webp)$', '', u)
    if root not in roots: roots[root] = []
    roots[root].append((u, w))
gallery = [max(v, key=lambda x: x[1])[0] for v in roots.values()]

slug = lambda n: re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-')
dup = {}
for n, h, img in colours: dup.setdefault(img, []).append(n)
report = {'url': url, 'code': code, 'gallery': len(gallery), 'colours': len(colours),
          'same_image_for': [v for v in dup.values() if len(v) > 1]}
if DRY:
    report['gallery_files'] = [g.rsplit('/', 1)[1] for g in gallery]
    report['colour_names'] = [c[0] for c in colours]
    print(json.dumps(report, indent=1)); sys.exit()

out = 'assets/products/' + folder
os.makedirs(out + '/zoom', exist_ok=True)

def save(job):
    name, src = job
    try:
        im = Image.open(io.BytesIO(get(src)))
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA'); bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
        else: im = im.convert('RGB')
        z = im.copy(); z.thumbnail((2000, 2000), Image.LANCZOS); z.save('%s/zoom/%s.jpg' % (out, name), quality=80, optimize=True, progressive=True)
        im.thumbnail((1000, 1000), Image.LANCZOS); im.save('%s/%s.jpg' % (out, name), quality=82, optimize=True, progressive=True)
        return None
    except Exception as e:
        return '%s: %s' % (name, e)

jobs = [('%s-%d' % (PREFIX, i + 1), g) for i, g in enumerate(gallery)] + ([] if GALLERY_ONLY else [(slug(n), img) for n, h, img in colours])
with ThreadPoolExecutor(6) as ex:
    errors = [e for e in ex.map(save, jobs) if e]
gal_names = ['%s-%d' % (PREFIX, i + 1) for i in range(len(gallery))]
if GALLERY_ONLY:
    mf = out + '/manifest.json'
    manifest = json.load(open(mf)) if os.path.exists(mf) else {'colours': [], 'gallery': []}
    manifest.setdefault('extra_gallery', {})[url] = gal_names
    json.dump(manifest, open(mf, 'w'), indent=1)
    report['failed'] = errors; print(json.dumps(report)); sys.exit()

def garment_rgb(path):
    im = Image.open(path).convert('RGB'); w, h = im.size
    c = im.crop((int(w * .35), int(h * .35), int(w * .65), int(h * .6))).resize((1, 1), Image.LANCZOS)
    return c.getpixel((0, 0))
def dist(a, hx):
    hx = hx.lstrip('#')
    if len(hx) != 6: return 1e9
    b = tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** .5
skipped = []
for img, names in dup.items():
    if len(names) < 2: continue
    rgb = garment_rgb('%s/%s.jpg' % (out, slug(names[0])))
    keep = min(names, key=lambda n: dist(rgb, [h for nn, h, _ in colours if nn == n][0]))
    for n in names:
        if n != keep:
            skipped.append(n)
            for f in ('%s/%s.jpg' % (out, slug(n)), '%s/zoom/%s.jpg' % (out, slug(n))):
                if os.path.exists(f): os.remove(f)
manifest = {'url': url, 'code': code, 'gallery': gal_names,
            'colours': [{'name': n, 'hex': h, 'file': (None if n in skipped else slug(n))} for n, h, _ in colours],
            'failed': errors, 'skipped_wrong_photo': skipped}
json.dump(manifest, open(out + '/manifest.json', 'w'), indent=1)
report['skipped'] = skipped
report['failed'] = errors
print(json.dumps(report))
