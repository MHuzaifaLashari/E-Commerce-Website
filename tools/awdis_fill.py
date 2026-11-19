"""Fill colours that have no packshot after tools/awdis_import.py (e.g. awdis.com showed the wrong
photo) with the same colour's packshot from another awdis.com page — normally the UK page of the style.

Usage (from the site folder):  python tools/awdis_fill.py <folder> <other awdis product url>
Only colours whose names match exactly (or French Navy <-> New French Navy) are filled, and only with
photos that are not shared by several colours on that page."""
import sys, os, re, io, json, time, html, urllib.request
from PIL import Image

folder, url = sys.argv[1], sys.argv[2]
base = 'assets/products/%s/' % folder
mf = base + 'manifest.json'
m = json.load(open(mf, encoding='utf-8'))
UA = {'User-Agent': 'Mozilla/5.0'}
UP = r'https://awdis\.com/(?:us/)?wp-content/uploads/(?:sites/\d+/)?\d{4}/\d{2}/'

def get(u):
    for _ in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90).read()
        except Exception as e: err = e; time.sleep(2)
    raise err

missing = [c for c in m['colours'] if not c.get('file') or not os.path.exists(base + c['file'] + '.jpg')]
if not missing:
    print(json.dumps({'folder': folder, 'filled': []})); sys.exit()

page = get(url).decode('utf-8', 'ignore')
found = {}
for sm in re.finditer(r'<a href="#" title="([^"]+)" data-hex-code="([^"]*)" data-featherlight="#(colour-\d+)"', page):
    name, cid = html.unescape(sm.group(1)).strip().upper(), sm.group(3)
    i = page.find('id="%s"' % cid)
    block = page[i:page.find('</div>', i)]
    best, bw = None, -1
    for u, w in re.findall(r'(' + UP + r'[^\s",\']+?\.(?:jpe?g|png|webp))(?:\s+(\d+)w)?', block):
        mm = re.search(r'-(\d+)x\d+\.\w+$', u)
        w = int(w) if w else (int(mm.group(1)) if mm else 99999)
        if w > bw: best, bw = u, w
    if best: found[name] = best
shared = {u for u in found.values() if list(found.values()).count(u) > 1}
alias = {'FRENCH NAVY': 'NEW FRENCH NAVY'}
filled = []
for c in missing:
    key = c['name'].upper()
    src = found.get(key) or found.get(alias.get(key, ''))
    if not src or src in shared: continue
    slug = re.sub(r'[^a-z0-9]+', '-', c['name'].lower()).strip('-')
    im = Image.open(io.BytesIO(get(src)))
    im = im.convert('RGB') if im.mode not in ('RGBA', 'LA', 'P') else (lambda a: (lambda bg: (bg.paste(a, mask=a.split()[-1]), bg)[1])(Image.new('RGB', a.size, (255, 255, 255))))(im.convert('RGBA'))
    os.makedirs(base + 'zoom', exist_ok=True)
    z = im.copy(); z.thumbnail((2000, 2000), Image.LANCZOS); z.save(base + 'zoom/' + slug + '.jpg', quality=80, optimize=True, progressive=True)
    im.thumbnail((1000, 1000), Image.LANCZOS); im.save(base + slug + '.jpg', quality=82, optimize=True, progressive=True)
    c['file'] = slug; c['photo_from'] = url
    filled.append(c['name'])
json.dump(m, open(mf, 'w'), indent=1)
print(json.dumps({'folder': folder, 'filled': filled, 'still_missing': [c['name'] for c in missing if c['name'] not in filled]}))