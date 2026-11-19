"""Set the real public URL and generate crawl files. Run before build_hosting.py.

python tools/build_seo.py https://your-domain.example/
Supports deployments in subdirectories. Re-run after adding catalogue products.
"""
import argparse
import html
import re
from pathlib import Path
from urllib.parse import urlsplit, urljoin, quote
from xml.etree.ElementTree import Element, SubElement, ElementTree, register_namespace

ROOT = Path(__file__).resolve().parents[1]


def build(base):
    parsed = urlsplit(base)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError('Supply the public HTTP(S) site URL without credentials, query or fragment')
    base = base.rstrip('/') + '/'
    for path in ROOT.glob('*.html'):
        source = path.read_text(encoding='utf-8')
        source = re.sub(r'\s*<meta name="cb-site-url"[^>]*>', '', source)
        source = re.sub(r'\s*<link rel="canonical"[^>]*>', '', source)
        source = re.sub(r'(<meta (?:property="og:image"|name="twitter:image") content=")([^"]+)(")',
                        lambda m: m[1] + html.escape(urljoin(base, html.unescape(m[2])), quote=True) + m[3], source)
        source = re.sub(r'\s*<meta property="og:url"[^>]*>', '', source)
        target = '' if path.name in ('index.html', 'sustbl.html') else path.name
        # Query-driven pages receive their precise canonical from seo.js.
        tags = '\n  <meta name="cb-site-url" content="' + html.escape(base, quote=True) + '">'
        if path.name not in ('product.html', 'brand.html'):
            tags += '\n  <link rel="canonical" href="' + html.escape(urljoin(base, target), quote=True) + '">'
            tags += '\n  <meta property="og:url" content="' + html.escape(urljoin(base, target), quote=True) + '">'
        source = source.replace('</head>', tags + '\n</head>', 1)
        path.write_text(source, encoding='utf-8')
    namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    register_namespace('', namespace)
    root = Element('{' + namespace + '}urlset')
    paths = ['', 'brand.html', 'brand.html?brand=awdis', 'brand.html?brand=woodbrook', 'outlet.html', 'sustainability.html']
    catalogue = (ROOT / 'assets/js/products.js').read_text(encoding='utf-8')
    paths += ['product.html?code=' + quote(code) for code in dict.fromkeys(re.findall(r'code:\s*"([A-Z0-9]+)"', catalogue))]
    for path in paths:
        item = SubElement(root, '{' + namespace + '}url')
        SubElement(item, '{' + namespace + '}loc').text = urljoin(base, path)
    ElementTree(root).write(ROOT / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
    (ROOT / 'robots.txt').write_text('User-agent: *\nAllow: /\n\nSitemap: ' + urljoin(base, 'sitemap.xml') + '\n', encoding='utf-8')
    print('Configured SEO for ' + base + ' (' + str(len(paths)) + ' sitemap URLs)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url')
    build(parser.parse_args().base_url)
