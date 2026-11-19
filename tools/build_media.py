"""Build assets/js/product-media.js from the manifests written by tools/awdis_import.py.

Run from the site folder after importing:  python tools/build_media.py
For every style folder in assets/products/<code>/manifest.json it produces:
  gallery      model photos (US page first, then UK page), used before the brochure photos
  colorImages  colour name -> packshot (only photos that passed the duplicate check)
  colors       the live colour range from the awdis.com US page
  colorHex     hex values from awdis.com for colour names that are not in the 2025 colour chart
  defaultColor the colour closest to the garment in the first photo
The generated file is merged into CB_PRODUCTS in the browser (see the bottom of product-media.js)."""
import json, os, re, glob
from PIL import Image

ROOT = 'assets/products'
CHART_JS = open('assets/js/site.js', encoding='utf-8').read()
# only official chart colours (entries that carry a Pantone reference)
chart_names = set(re.findall(r'\["([^"]+)","#[0-9a-fA-F]{6}","[^"]+"', CHART_JS))

def title(n):
    n = re.sub(r'\s*/\s*', '/', n.strip())
    t = ' '.join(w.capitalize() for w in n.replace('/', ' / ').split())
    t = t.replace(' / ', '/')
    # US site short forms inside two-tone names
    if '/' in t:
        t = '/'.join({'Sky': 'Sky Blue', 'White': 'Arctic White'}.get(x, x) for x in t.split('/'))
    return {'Heather Gray': 'Heather Grey', 'Turquiose': 'Turquoise', 'Prepared For Dye': 'Prepared for Dye'}.get(t, t)

def rgb_of(path, box=(.38, .42, .62, .62)):
    im = Image.open(path).convert('RGB'); w, h = im.size
    c = im.crop((int(w * box[0]), int(h * box[1]), int(w * box[2]), int(h * box[3]))).resize((1, 1), Image.LANCZOS)
    return c.getpixel((0, 0))

def hex_rgb(h):
    h = (h or '').lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) == 6 else None

media, extra_hex, report = {}, {}, []
for mf in sorted(glob.glob(ROOT + '/*/manifest.json')):
    folder = os.path.basename(os.path.dirname(mf))
    m = json.load(open(mf, encoding='utf-8'))
    code = folder.upper()
    base = '%s/%s/' % (ROOT, folder)
    gallery = [base + g + '.jpg' for g in m.get('gallery', [])]
    srcs = list(m.get('gallery_src', []))[:len(gallery)]
    srcs += [''] * (len(gallery) - len(srcs))
    for names in m.get('extra_gallery', {}).values():
        gallery += [base + g + '.jpg' for g in names]
        extra = list(m.get('extra_gallery_src', []))[:len(names)]
        srcs += extra + [''] * (len(names) - len(extra))
    pairs = [(g, sname) for g, sname in zip(gallery, srcs) if os.path.exists(g)]
    gallery = [g for g, _ in pairs]
    colors, color_images, hexes, color_backs, own_hex = [], {}, {}, {}, {}
    for c in m.get('colours', []):
        name = title(c['name'])
        if name in colors: continue
        colors.append(name)
        if c.get('hex') and not c['hex'].startswith('#'): c['hex'] = '#' + c['hex']   # awdis.com sometimes omits '#'
        if c.get('hex'): hexes[name] = c['hex']
        if c.get('file') and os.path.exists(base + c['file'] + '.jpg'):
            color_images[name] = base + c['file'] + '.jpg'
        if c.get('back') and os.path.exists(base + c['back'] + '.jpg'):
            color_backs[name] = base + c['back'] + '.jpg'
        # this style's own shade for names that are not official chart colours (e.g. WoodBrook "Navy")
        # (non-AWDis brands use their own shade for every colour — the AWDis chart does not apply)
        if '/' not in name and c.get('hex') and (name not in chart_names or m.get('source') == 'citadelbrands.com'):
            own_hex[name] = c['hex']
        # colours not in the chart (and not two-tone) take their hex from awdis.com
        if '/' not in name and name not in chart_names and c.get('hex'):
            extra_hex.setdefault(name, c['hex'])
    # default colour = the colour named in a photo's file name (e.g. JH009_JET_BLACK_FIRE_RED_...);
    # that photo is moved to the front so the first image and the selected colour always match
    ALIAS = {'deep black': 'jet black', 'new french navy': 'french navy', 'black': 'jet black', 'white': 'arctic white', 'solid white': 'arctic white'}
    norm = lambda x: re.sub(r'[^a-z]+', ' ', x.lower()).strip()
    def colour_in(fname):
        rest = re.sub(r'^[A-Za-z]{2,3}\d{3}[A-Za-z]?[_-]', '', fname)
        words = norm(rest)
        for a, b in ALIAS.items():
            if words.startswith(a + ' '): words = b + words[len(a):]
        best = None
        for c in colors:
            key = norm(c.replace('/', ' '))
            if (words + ' ').startswith(key + ' ') and (best is None or len(key) > len(norm(best))): best = c
        return best
    default = None
    mw = norm(m.get('model_wearing', ''))            # citadelbrands.com: "Model Wearing: Royal Blue"
    if mw:
        for c in colors:
            k = norm(c)
            if mw == k or mw.startswith(k + ' ') or k.startswith(mw + ' '):
                default = c; break
    for i, (g, sname) in enumerate(pairs):
        if default: break
        hit = colour_in(sname) if sname else None
        if hit:
            default = hit
            if i: gallery.insert(0, gallery.pop(i))
            break
    if not gallery and colors:
        default = 'Jet Black' if 'Jet Black' in colors else colors[0]
    if default is None and gallery and hexes:
        rgb = rgb_of(gallery[0])
        def d(n):
            parts = [hex_rgb(hexes.get(p.strip())) or hex_rgb(hexes.get(n)) for p in n.split('/')]
            parts = [x for x in parts if x]
            return min(sum((a - b) ** 2 for a, b in zip(rgb, x)) for x in parts) if parts else 1e9
        default = min(colors, key=d)
    entry = {'zoomBase': base, 'gallery': gallery, 'colorImages': color_images, 'colors': colors}
    if color_backs: entry['colorBacks'] = color_backs
    if own_hex: entry['colorHex'] = own_hex
    if m.get('source') == 'citadelbrands.com':      # specs straight from Citadel's product page
        spec = {k: m[k] for k in ('fabric', 'weight', 'sizes', 'features') if m.get(k)}
        if m.get('case_quantity'): spec['caseQty'] = m['case_quantity']
        if m.get('url'): spec['url'] = m['url']
        entry['specs'] = spec
    if default: entry['defaultColor'] = default
    media[code] = entry
    report.append('%-7s photos=%-2d colours=%-2d packshots=%-2d default=%s%s' % (
        code, len(gallery), len(colors), len(color_images), default,
        ('  skipped(wrong photo on awdis.com): ' + ', '.join(m['skipped_wrong_photo'])) if m.get('skipped_wrong_photo') else '') + ('  backs=%d' % len(color_backs) if color_backs else ''))

js = '''/* AUTO-GENERATED by tools/build_media.py from assets/products/<code>/manifest.json — do not edit by hand.
   AWDis: photography and colour ranges from awdis.com/us/products (+ UK model photos).
   WoodBrook: packshots (front + back), model photo and specs from citadelbrands.com product pages.
   Merged into CB_PRODUCTS below: live colour range, packshot per colour, model-photo gallery, zoom folder. */
window.CB_EXTRA_COLORS=%s;
window.CB_MEDIA=%s;
(function(){
  var M=window.CB_MEDIA||{};
  (window.CB_PRODUCTS||[]).forEach(function(p){
    var m=M[(p.code||"").toUpperCase()];
    if(!m)return;
    var brochure=(p.gallery||[p.img,p.img2]).filter(function(s){return s&&s.indexOf(m.zoomBase)!==0;});
    if(m.colors&&m.colors.length){p.colors=m.colors;p.moreColors=false;}
    p.colorImages=m.colorImages;
    if(m.colorBacks)p.colorBacks=m.colorBacks;
    if(m.colorHex)p.colorHex=m.colorHex;
    if(m.specs){
      ["fabric","weight","sizes","features","url"].forEach(function(k){if(m.specs[k])p[k]=m.specs[k];});
      if(m.specs.caseQty){p.caseQty=m.specs.caseQty;}
    }
    p.zoomBase=m.zoomBase;
    if(m.defaultColor)p.defaultColor=m.defaultColor;
    var photos=m.gallery.length?m.gallery:(m.defaultColor&&m.colorImages[m.defaultColor]?[m.colorImages[m.defaultColor]]:[]);
    p.gallery=photos.concat(brochure);
    if(p.gallery.length){p.img=p.gallery[0];p.img2=p.gallery[1]||null;p.pos="center 20%%";}
  });
})();
''' % (json.dumps(extra_hex, indent=0), json.dumps(media, indent=0))
open('assets/js/product-media.js', 'w', encoding='utf-8').write(js)
print('\n'.join(report))
print('extra colours from awdis.com:', len(extra_hex), sorted(extra_hex)[:40])
