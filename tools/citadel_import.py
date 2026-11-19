"""Import a style's images and specs from a citadelbrands.com product page.

Usage (from the site folder):
    python tools/citadel_import.py https://www.citadelbrands.com/product/WBA010/CLASSIC-PIQUE-POLO.html
Saves to assets/products/<code>/ :
  gallery-N.jpg            model photo(s)
  <colour>.jpg             front packshot per colour      (max 1000px, zoom/ = max 2000px)
  <colour>-back.jpg        back packshot per colour (when the site has one)
  manifest.json            colours (name, hex, files), gallery, sizes, features, fabric, weight, notes
build_media.py picks the manifest up like the AWDis ones."""
import sys, os, re, io, json, time, html, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

url = sys.argv[1]
UA = {'User-Agent': 'Mozilla/5.0'}

def get(u, t=90):
    err = None
    for _ in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read()
        except Exception as e: err = e; time.sleep(2)
    raise err

page = html.unescape(get(url, 60).decode('utf-8', 'ignore'))
code = re.search(r'/product/([A-Za-z0-9]+)/', url).group(1).upper()
lc = code.lower()
text = lambda s: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)).strip()

# ---- colours: <a href="HIRES" ... data-image="LARGE" ... data-colorcode="093" data-desc="KELLY GREEN"> ... background-color:#009448
colours = []
for m in re.finditer(r'<div class="colorOuter">\s*<a href="([^"]+)"[^>]*?data-image="([^"]+)"[^>]*?data-colorcode="([^"]+)"\s+data-desc="([^"]+)">(.*?)</a>', page, re.S):
    hires, large, ccode, name, inner = m.groups()
    hx = re.search(r'background-color:\s*(#[0-9A-Fa-f]{6})', inner)
    back = re.search(r'https://www\.citadelbrands\.com/prodimg/hires/%s%s1back_[^"\s]+?\.(?:png|jpe?g)' % (lc, re.escape(ccode)), page, re.I)
    colours.append({'name': name.strip(), 'code': ccode, 'hex': hx.group(1) if hx else '', 'front': hires, 'back': back.group(0) if back else None})

# ---- model photo(s): hires images of the style without a colour code
model = []
for u in re.findall(r'https://www\.citadelbrands\.com/prodimg/hires/%s_[^"\s]+?\.(?:png|jpe?g)' % lc, page, re.I):
    if u not in model: model.append(u)

# ---- specs
feat = re.search(r"id='prodFeatTab'(.*?)Have a Wholesale Account", page, re.S)
features, fabric, weight = [], '', ''
if feat:
    for k, v in re.findall(r'<td[^>]*>\s*([^<]+?)\s*</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>', feat.group(1)):
        k, v = k.strip().upper(), v.strip()
        if k == 'KEY FEATURES': features.append(v.capitalize().replace('Dtm buttons', 'Dyed-to-match (DTM) buttons'))
        elif k == 'FABRIC': fabric = v.title().replace('/ ', '/ ')
        elif k == 'WEIGHT': weight = v.lower().replace('oz', 'oz').strip()
sizes = re.search(r'Sizes:(.*?)Colors:', page, re.S)
sizes = [s.strip() for s in text(sizes.group(1)).split(',') if s.strip()] if sizes else []
desc = re.search(r'<div class="prodCatalogDesc">(.*?)</div>\s*</div>', page, re.S)
desc_text = text(desc.group(1)) if desc else ''
bullets = [text(b) for b in re.findall(r'<li>(.*?)</li>', desc.group(1), re.S)] if desc else []
model_wearing = re.search(r'Model Wearing:\s*([A-Za-z /]+?)\s+(?:Fabrication|$)', desc_text)
cases = re.findall(r'Case Quantity \(([^)]+)\):\s*(\d+)', desc_text)
title = re.search(r'<h2 class="prodTitle">\s*[A-Z0-9]+\s*-\s*([^<]+)</h2>', page)

out = 'assets/products/' + lc
os.makedirs(out + '/zoom', exist_ok=True)
slug = lambda n: re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-')

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

jobs = [('gallery-%d' % (i + 1), u) for i, u in enumerate(model)]
for c in colours:
    jobs.append((slug(c['name']), c['front']))
    if c['back']: jobs.append((slug(c['name']) + '-back', c['back']))
with ThreadPoolExecutor(6) as ex:
    errors = [e for e in ex.map(save, jobs) if e]

manifest = {
    'url': url, 'code': code, 'source': 'citadelbrands.com',
    'name': title.group(1).strip().title() if title else '',
    'gallery': ['gallery-%d' % (i + 1) for i in range(len(model))],
    'model_wearing': model_wearing.group(1).strip().title() if model_wearing else '',
    'colours': [{'name': c['name'], 'hex': c['hex'], 'colorcode': c['code'], 'file': slug(c['name']),
                 'back': (slug(c['name']) + '-back') if c['back'] else None} for c in colours],
    'sizes': sizes, 'fabric': fabric, 'weight': weight, 'features': features,
    'description_bullets': bullets, 'case_quantity': {k: int(v) for k, v in cases},
    'failed': errors}
json.dump(manifest, open(out + '/manifest.json', 'w'), indent=1)
print(json.dumps({k: (len(v) if isinstance(v, list) and k in ('colours', 'gallery') else v) for k, v in manifest.items()}, indent=1))
