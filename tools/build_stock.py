"""Build assets/js/stock.js from an inventory export (Citadel scraper JSON/xlsx, or any CSV/Excel).

Usage (from the site folder):
    python tools/build_stock.py                      # newest tools/data/citadel_warehouse_inventory_*.json,
                                                     # else newest citadel_inventory_*.json|.xlsx|.csv
    python tools/build_stock.py <file> [--updated "2026-10-01 08:00"]

Citadel scraper exports (citadel_inventory_YYYYMMDD_HHMMSS.json / .xlsx) are read directly:
style_code, color, size, warehouse_code, available_quantity, available_quantity_display ("1000+"),
price, scraped_at, source_url. These are website figures: one combined number per size, capped at 1000+.

Citadel warehouse stock reports (citadel_warehouse_inventory_YYYYMMDD_HHMMSS.json) give real, uncapped
stock per warehouse (KC / KT): available_quantity and committed_quantity. They carry no prices, so
prices are merged from the catalogue file named in catalog_metadata_source (or the newest
citadel_inventory_* file in tools/data/), matched on style / colour / size.

Other files need one row per style / colour / size / warehouse;
column names are matched loosely:
    style     : style, style code, item, product
    colour    : color, colour, color description, color desc
    size      : size, size description
    warehouse : warehouse code, warehouse, whse, location, branch   (optional — defaults to "ALL")
    quantity  : available quantity, qty, quantity, on hand, available, free stock
    price     : price, unit price                                     (optional)
Colour and size names are matched to the site's colour/size names (case-insensitive; 2X = 2XL,
XXL = 2XL; COLOUR_ALIASES below for spelling differences). Rows for styles that are not on the
site are reported and skipped. Warehouse names can be set in WAREHOUSE_NAMES below."""
import sys, re, csv, json, os, glob, datetime

WAREHOUSE_NAMES = {'KC': 'Kansas City, MO', 'KT': 'Kingstree, SC', 'LA': 'Los Angeles', 'SC': 'Kingstree, SC',
                   'ALL': 'All warehouses'}

# export colour name (upper case) -> site colour name, where the spelling differs
COLOUR_ALIASES = {
    'PFD (PREPARED FOR DYE)': 'Prepared for Dye', 'PFD': 'Prepared for Dye',
    'ELEC YELLOW': 'Electric Yellow', 'HEATHER': 'Heather Grey', 'SHERBERT LEMON': 'Sherbet Lemon',
    'SPORTS GREY': 'Sports Grey', 'SPORT GREY': 'Sport Grey',
    'JET BLACK/WHITE': 'Jet Black/Arctic White', 'OXFORD NAVY/WHITE': 'Oxford Navy/Arctic White',
    'JET BLACK': 'Black',
}

args = [a for a in sys.argv[1:] if not a.startswith('--')]
updated = None
if '--updated' in sys.argv: updated = sys.argv[sys.argv.index('--updated') + 1]
def newest(pats):
    found = sorted(sum((glob.glob('tools/data/' + p) for p in pats), []), key=lambda f: re.sub(r'\D', '', os.path.basename(f)))
    return found[-1] if found else None
CATALOG = ['citadel_inventory_*.json', 'citadel_inventory_*.xlsx', 'citadel_inventory_*.csv']
if args: src = args[0]
else:
    src = newest(['citadel_warehouse_inventory_*.json']) or newest(CATALOG)
    if not src: sys.exit('No inventory file given and none found in tools/data/ (citadel_warehouse_inventory_*.json '
                         'or citadel_inventory_*.json|.xlsx|.csv).')
meta = {}
if src.lower().endswith('.json'):
    _d = json.load(open(src, encoding='utf-8-sig'))
    if isinstance(_d, dict): meta = {k: v for k, v in _d.items() if k != 'rows'}
by_whse = 'warehouse_sources' in meta     # warehouse stock report: real per-warehouse figures, no prices

def rows_from(path):
    low = path.lower()
    if low.endswith('.json'):
        data = json.load(open(path, encoding='utf-8-sig'))
        rows = data
        if isinstance(data, dict):
            rows = next((data[k] for k in ('rows', 'inventory', 'items', 'data', 'records') if isinstance(data.get(k), list)), [])
            meta = data.get('summary') if isinstance(data.get('summary'), dict) else data
            if meta.get('scraped_at'): yield {'__scraped_at': meta['scraped_at']}
        for r in rows:
            if isinstance(r, dict): yield {k: '' if v is None else str(v).strip() for k, v in r.items()}
    elif low.endswith(('.xlsx', '.xlsm')):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb['Inventory'] if 'Inventory' in wb.sheetnames else wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        head = [str(h or '').strip() for h in next(it)]
        for r in it: yield dict(zip(head, ['' if v is None else str(v).strip() for v in r]))
    else:
        with open(path, newline='', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f): yield {k.strip(): (v or '').strip() for k, v in r.items() if k}

ALIASES = {
    'style': ['style_code', 'style', 'style code', 'stylecode', 'item', 'product', 'style no', 'style #'],
    'colour': ['color', 'colour', 'color description', 'color desc', 'colour description', 'color name'],
    'size': ['size', 'size description', 'size desc'],
    'warehouse': ['warehouse_code', 'warehouse code', 'warehouse', 'whse', 'location', 'branch', 'wh'],
    'committed': ['committed_quantity', 'committed'],
    'qty': ['available_quantity', 'available quantity', 'qty', 'quantity', 'on hand', 'onhand', 'available',
            'avail qty', 'qty available', 'free stock', 'stock'],
    'display': ['available_quantity_display', 'available quantity display'],
    'price': ['price', 'unit price', 'unit_price'],
    'scraped': ['scraped_at', 'scraped at'],
    'url': ['source_url', 'source url'],
}
def pick(row, key):
    low = {k.lower(): v for k, v in row.items()}
    for a in ALIASES[key]:
        if a in low: return low[a]
    return ''

# site catalogue: style -> colour names, sizes
site = {}
media = open('assets/js/product-media.js', encoding='utf-8').read()
cm = json.loads(re.search(r'window\.CB_MEDIA=(\{.*?\});\n', media, re.S).group(1))
for code, m in cm.items(): site[code] = {c.lower(): c for c in m.get('colors', [])}
prod = open('assets/js/products.js', encoding='utf-8').read()
for code in re.findall(r'\{code:"([A-Z0-9]+)"', prod): site.setdefault(code, {})

def canon_size(z):
    z = re.sub(r'\s+', '', str(z).upper())
    if z == 'XXL': return '2XL'
    m = re.match(r'^(\d)X$', z)
    return m.group(1) + 'XL' if m else z
def title(c):
    return ' '.join(w.capitalize() for w in re.sub(r'\s*/\s*', ' / ', c).split()).replace(' / ', '/')
def site_colour(style, colour):
    known = site[style]
    key = re.sub(r'\s*/\s*', '/', colour.strip().upper())
    for cand in (colour, title(colour), COLOUR_ALIASES.get(key, '')):
        if cand and cand.lower() in known: return known[cand.lower()]
    return None

items, prices, committed, capped, skipped_styles, unknown_colours, n = {}, {}, {}, set(), {}, {}, 0
scraped = ''
def ingest(path, take_qty=True, take_price=True):
  global scraped, n
  for r in rows_from(path):
    if '__scraped_at' in r:
        if take_qty: scraped = r['__scraped_at']
        continue
    style = pick(r, 'style').upper()
    colour = pick(r, 'colour'); size = pick(r, 'size')
    whse = (pick(r, 'warehouse') or 'ALL').upper()
    q = pick(r, 'qty').replace(',', '')
    if not style or not colour or not size: continue
    try: q = int(float(q or 0))
    except ValueError: continue
    if take_qty: scraped = scraped or pick(r, 'scraped')
    if style not in site:
        if take_qty: skipped_styles[style] = skipped_styles.get(style, 0) + 1
        continue
    name = site_colour(style, colour)
    if not name:
        if take_qty: unknown_colours.setdefault(style, set()).add(colour)
        name = title(colour)
    z = canon_size(size)
    if take_qty:
        cell = items.setdefault(style, {}).setdefault(name, {}).setdefault(z, {})
        cell[whse] = cell.get(whse, 0) + max(q, 0)
        if pick(r, 'display').endswith('+'): capped.add(q)
        try: cq = int(float(pick(r, 'committed') or 0))
        except ValueError: cq = 0
        if cq > 0:
            cc = committed.setdefault(style, {}).setdefault(name, {}).setdefault(z, {})
            cc[whse] = cc.get(whse, 0) + cq
        n += 1
    if not take_price: continue
    try:
        pr = float(pick(r, 'price'))
        if pr > 0: prices.setdefault(style, {}).setdefault(name, {})[z] = round(pr, 2)
    except ValueError: pass

ingest(src)
price_src = None
if by_whse:
    cat = os.path.basename((meta.get('catalog_metadata_source') or '').replace('\\', '/'))
    cand = os.path.join('tools/data', cat) if cat else ''
    price_src = cand if cand and os.path.exists(cand) else newest(CATALOG)
    if price_src: ingest(price_src, take_qty=False)

def fmt_time(s):
    try:
        t = datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
        if t.tzinfo: t = t.astimezone(datetime.timezone.utc); return t.strftime('%Y-%m-%d %H:%M UTC')
        return t.strftime('%Y-%m-%d %H:%M')
    except Exception: return s

whses = sorted({w for s in items.values() for c in s.values() for z in c.values() for w in z})
if by_whse:
    # stock report: keep the report's warehouse order; "as of" = the newest warehouse file
    order = meta.get('warehouses') or []
    whses = [w for w in order if w in whses] + [w for w in whses if w not in order]
    mods = [v.get('modified_utc', '') for v in meta['warehouse_sources'].values() if isinstance(v, dict)]
    stamp = re.sub(r':\d\d UTC$', ' UTC', max(mods)) if any(mods) else fmt_time(meta.get('generated_at', ''))
    auto_updated, auto_source = stamp, ('Citadel warehouse stock report ' + str(meta.get('report_date') or '')).strip()
else:
    auto_updated = fmt_time(scraped) if scraped else datetime.datetime.fromtimestamp(os.path.getmtime(src)).strftime('%Y-%m-%d %H:%M')
    auto_source = 'citadelbrands.com' if 'citadel_inventory' in os.path.basename(src) else os.path.basename(src)
out = {'updated': updated or auto_updated,
       'source': auto_source,
       'aggregate': whses == ['ALL'],
       'cap': max(capped) if capped else None,
       'currency': 'USD',
       'warehouses': {w: WAREHOUSE_NAMES.get(w, w) for w in whses}, 'items': items, 'prices': prices}
if committed: out['committed'] = committed       # units already allocated to open orders (not in "available")
if by_whse and meta.get('upcoming_stock_available') is False: out['incoming'] = False
js = ('/* GENERATED by tools/build_stock.py from %s — do not edit by hand. */\nwindow.CB_STOCK=%s;\n'
      % (os.path.basename(src) + (' + prices from ' + os.path.basename(price_src) if price_src else ''), json.dumps(out, separators=(',', ':'), ensure_ascii=False)))
open('assets/js/stock.js', 'w', encoding='utf-8').write(js)
print('source: %s · as of %s' % (src, out['updated']))
if price_src: print('prices from: %s · styles priced: %d' % (price_src, len(prices)))
print('rows used: %d · styles: %d · warehouses: %s · cap: %s' % (n, len(items), ', '.join(whses), out['cap']))
missing = sorted(set(site) - set(items))
if missing: print('site styles with no stock rows:', ', '.join(missing))
if skipped_styles: print('styles not on the site (skipped):', ', '.join('%s(%d)' % kv for kv in sorted(skipped_styles.items())))
for s, cs in unknown_colours.items(): print('colour names not in %s range (kept as-is): %s' % (s, ', '.join(sorted(cs))))

# ---- Outlet: slow-moving colourways, sold online (assets/js/outlet.js, public) ----
# A colourway is "slow-moving" when Citadel has marked it down: its lowest price is under OUTLET_RATIO x the
# style's usual price (median of the colours' lowest prices) and it still has stock. Add style/colour pairs
# to OUTLET_EXTRA to list more. Public file = style, colour and % off only; prices and stock stay in stock.js.
OUTLET_RATIO = 0.8
OUTLET_EXTRA = []          # e.g. [('JHA001', 'Mustard')]
outlet = []
for style, cols in prices.items():
    lows = {c: min(z.values()) for c, z in cols.items() if z}
    if len(lows) < 3: continue
    usual = sorted(lows.values())[len(lows) // 2]
    for c, lo in lows.items():
        units = sum(q for z in items.get(style, {}).get(c, {}).values() for q in z.values())
        if units <= 0: continue
        if lo < usual * OUTLET_RATIO or (style, c) in OUTLET_EXTRA:
            outlet.append({'code': style, 'color': c, 'off': int(round((1 - lo / usual) * 100)),
                           'onSite': c.lower() in site.get(style, {})})
outlet.sort(key=lambda x: (-x['off'], x['code'], x['color']))
open('assets/js/outlet.js', 'w', encoding='utf-8').write(
    '/* GENERATED by tools/build_stock.py — slow-moving colourways for outlet.html. Do not edit by hand. */\n'
    'window.CB_OUTLET=%s;\n' % json.dumps({'updated': out['updated'], 'items': outlet}, separators=(',', ':'), ensure_ascii=False))
print('outlet: %d slow-moving colourways (%d styles)' % (len(outlet), len({x['code'] for x in outlet})))
