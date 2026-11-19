"""Write assets/admin/admin-data.js: the homepage image slots (from index.html) and the colour chart
(from assets/js/site.js) for admin.html.

When admin.html is opened straight from the folder (file://) the browser won't let it read index.html
or site.js until the project folder is connected, so it uses this file instead.
Run it after changing index.html or the colour chart (tools/build_hosting.py runs it too):

    python tools/build_admin_data.py
"""
import json, os, re
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Slots(HTMLParser):
    def __init__(self):
        super().__init__()
        self.slots = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'img' and a.get('data-slot'):
            self.slots.append({'key': a['data-slot'], 'label': a.get('data-slot-label') or a['data-slot'],
                               'src': a.get('src', ''), 'alt': a.get('alt') or ''})


def build():
    p = Slots()
    p.feed(open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read())
    site = open(os.path.join(ROOT, 'assets', 'js', 'site.js'), encoding='utf-8').read()
    m = re.search(r'CB\.colorList=(\[[\s\S]*?\]);', site)
    colors = {}
    if m:
        # drop the "// note" comments after the last quote on a line, then read it as JSON
        lines = []
        for line in m.group(1).split('\n'):
            q = line.rfind('"')
            c = line.find('//', q + 1)
            lines.append(line[:c] if c > -1 else line)
        for row in json.loads('\n'.join(lines)):
            colors.setdefault(row[0], row[1])
    out = os.path.join(ROOT, 'assets', 'admin', 'admin-data.js')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* Made by tools/build_admin_data.py from index.html and assets/js/site.js. Do not edit by hand. */\n')
        f.write('window.CB_ADMIN_DATA=' + json.dumps({'slots': p.slots, 'colors': colors}, ensure_ascii=False, separators=(',', ':')) + ';\n')
    return len(p.slots), len(colors)


if __name__ == '__main__':
    n, c = build()
    print('admin-data.js: %d homepage images, %d colours' % (n, c))
