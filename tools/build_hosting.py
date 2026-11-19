"""Build an upload-ready copy of the site for static hosting (e.g. InfinityFree htdocs).

    python tools/build_hosting.py [output folder]      (default: ~/Desktop/Infinity Hosting Files)

Stock and prices (assets/js/stock.js) are NOT uploaded readable. They are encrypted
(AES-256) into assets/js/stock.enc.js and can only be unlocked in the browser by logging in
with an account password from assets/js/auth.js. The script asks for each account's password
(or reads CB_PW_<n> environment variables, n = account number in auth.js starting at 1).
Re-run it whenever stock.js is rebuilt, then upload the new folder.

The online site admin (admin.html + api/admin.php) is included. Its sign-in account is written to
api/admin-config.php as a salted PBKDF2 hash; the script asks for the admin email and password
(or reads CB_ADMIN_EMAIL / CB_ADMIN_PW). The password itself is never stored.
"""
import base64, getpass, json, os, re, secrets, shutil, sys, hashlib
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser('~'), 'Desktop', 'Infinity Hosting Files'))
ITER = 20000
MARK = b'CB-STOCK'
MAX_FILE = 10 * 1024 * 1024          # InfinityFree free plan: 10 MB per file

SKIP_DIRS = {'BrandGuideLine'}          # brand guidelines aren't used by any page
SKIP_FILES = {'stock.js', 'manifest.json'}


def b64(b):
    return base64.b64encode(b).decode()


def aes_cbc(key, iv, data):
    p = padding.PKCS7(128).padder()
    data = p.update(data) + p.finalize()
    e = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return e.update(data) + e.finalize()


def js_hash(s):
    """Same as hash() in assets/js/auth.js."""
    imul = lambda a, b: (a * b) & 0xFFFFFFFF
    x = 2166136261
    for ch in s:
        x ^= ord(ch)
        x = imul(x, 16777619)
    for r in range(1000):
        x ^= x >> 13
        x = imul(x, 1540483477)
        x ^= r
    return format(x, 'x')


def php_str(s):
    """A PHP single-quoted string literal ($ and the rest are taken literally)."""
    return "'" + s.replace('\\', '\\\\').replace("'", "\\'") + "'"


def read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8', newline='').read()


def write(rel, text):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8', newline='').write(text)


# ---------- 0. refresh the admin's homepage-image list and colour chart ----------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_admin_data
build_admin_data.build()

# ---------- 1. copy pages and assets ----------
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)
skipped_big = []
for name in os.listdir(ROOT):
    if name.endswith('.html') or name in ('robots.txt', 'sitemap.xml'):
        shutil.copy2(os.path.join(ROOT, name), OUT)
for dirpath, dirs, files in os.walk(os.path.join(ROOT, 'assets')):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for f in files:
        if f in SKIP_FILES:
            continue
        src = os.path.join(dirpath, f)
        rel = os.path.relpath(src, ROOT)
        if os.path.getsize(src) > MAX_FILE:
            skipped_big.append(rel)
            continue
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
shutil.copy2(os.path.join(ROOT, 'tools', 'vendor', 'crypto-js.min.js'), os.path.join(OUT, 'assets', 'js', 'crypto-js.min.js'))

# ---------- 1b. online admin: api/ (code and access rules only, never local data) ----------
for dirpath, dirs, files in os.walk(os.path.join(ROOT, 'api')):
    rel_dir = os.path.relpath(dirpath, ROOT)
    os.makedirs(os.path.join(OUT, rel_dir), exist_ok=True)
    for f in files:
        if f.endswith('.php') and f != 'admin-config.php' or f == '.htaccess':
            shutil.copy2(os.path.join(dirpath, f), os.path.join(OUT, rel_dir, f))
os.makedirs(os.path.join(OUT, 'assets', 'uploads'), exist_ok=True)
admin_email = os.environ.get('CB_ADMIN_EMAIL') or input('Admin email for the online site admin: ').strip()
admin_pw = os.environ.get('CB_ADMIN_PW')
while not admin_pw:
    admin_pw = getpass.getpass('Admin password (at least 10 characters): ')
    if len(admin_pw) < 10:
        print('  Use at least 10 characters.'); admin_pw = None; continue
    if getpass.getpass('Type it again: ') != admin_pw:
        print('  The passwords did not match.'); admin_pw = None
if len(admin_pw) < 10:
    sys.exit('The admin password must be at least 10 characters.')
salt = secrets.token_bytes(16)
admin_hash = 'pbkdf2_sha256$200000$%s$%s' % (b64(salt), b64(hashlib.pbkdf2_hmac('sha256', admin_pw.encode('utf-8'), salt, 200000, 32)))
write('api/admin-config.php', "<?php\n// Made by tools/build_hosting.py: the online site admin's sign-in (password stored only as a salted hash).\n"
      "return ['users' => [['email' => %s, 'name' => 'Admin', 'hash' => %s]]];\n" % (php_str(admin_email), php_str(admin_hash)))

# ---------- 2. accounts and passwords ----------
auth = read('assets/js/auth.js')
users = re.findall(r'\{email:"([^"]+)".*?hash:"([0-9a-f]+)"\}', auth)
if not users:
    sys.exit('No accounts found in assets/js/auth.js')
passwords = {}
for n, (email, h) in enumerate(users, 1):
    pw = os.environ.get('CB_PW_%d' % n)
    while True:
        if pw is None:
            pw = getpass.getpass('Password for %s: ' % email)
        if js_hash('cb1|%s|%s' % (email, pw)) == h:
            break
        print('  That password does not match the account in auth.js.')
        if os.environ.get('CB_PW_%d' % n):
            sys.exit(1)
        pw = None
    passwords[email] = pw

# ---------- 3. encrypt stock data ----------
stock_src = read('assets/js/stock.js')
m = re.search(r'window\.CB_STOCK\s*=\s*(\{.*\})\s*;?\s*$', stock_src, re.S)
stock = json.loads(m.group(1))
data_key = secrets.token_bytes(32)
iv = secrets.token_bytes(16)
ct = aes_cbc(data_key, iv, json.dumps(stock, separators=(',', ':')).encode('utf-8'))
write('assets/js/stock.enc.js',
      '/* Encrypted stock & prices. Unlocked in the browser after login (see auth.js). */\n'
      'window.CB_STOCK_ENC={"iv":"%s","ct":"%s"};\n'
      'if(window.CB_AUTH&&window.CB_AUTH.unlock)window.CB_AUTH.unlock();\n' % (b64(iv), b64(ct)))

wraps = {}
for email, pw in passwords.items():
    salt, wiv = secrets.token_bytes(16), secrets.token_bytes(16)
    kek = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, ITER, 32)
    wraps[email] = {'s': b64(salt), 'i': b64(wiv), 'c': b64(aes_cbc(kek, wiv, data_key + MARK))}

# ---------- 4. patch auth.js ----------
def sub(text, old, new):
    if old not in text:
        sys.exit('Could not patch: %r' % old[:60])
    return text.replace(old, new, 1)

auth = re.sub(r'\n\s*Test account:[^\n]*?(\*/)', r' \1', auth)
auth = sub(auth, '  function hash(s){',
           '  // per-account wrapped key that unlocks assets/js/stock.enc.js (built by tools/build_hosting.py)\n'
           '  var ITER=%d,MARK="%s",WRAPS=%s;\n'
           '  function unwrap(email,password){\n'
           '    var w=WRAPS[email],C=window.CryptoJS;if(!w||!C)return null;\n'
           '    try{\n'
           '      var kek=C.PBKDF2(password,C.enc.Base64.parse(w.s),{keySize:8,iterations:ITER,hasher:C.algo.SHA256});\n'
           '      var hex=C.AES.decrypt({ciphertext:C.enc.Base64.parse(w.c)},kek,{iv:C.enc.Base64.parse(w.i)}).toString(C.enc.Hex);\n'
           '      return hex.length===80&&hex.slice(64)===MARK?hex.slice(0,64):null;\n'
           '    }catch(e){return null;}\n'
           '  }\n'
           '  function hash(s){' % (ITER, MARK.hex(), json.dumps(wraps, separators=(',', ':'))))
auth = sub(auth, 'if(!u||hash("cb1|"+email+"|"+password)!==u.hash)return null;',
           'if(!u||hash("cb1|"+email+"|"+password)!==u.hash)return null;\n      var k=unwrap(email,password);')
auth = sub(auth, 'exp:Date.now()+(remember?DAYS*864e5:12*36e5)};',
           'exp:Date.now()+(remember?DAYS*864e5:12*36e5),k:k};')
auth = sub(auth, 'logout:function(){clear();},',
           'logout:function(){clear();},\n'
           '    unlock:function(){\n'
           '      var me=user(),E=window.CB_STOCK_ENC,C=window.CryptoJS;\n'
           '      if(!me||!me.k||!E||!C)return;\n'
           '      try{window.CB_STOCK=JSON.parse(C.AES.decrypt({ciphertext:C.enc.Base64.parse(E.ct)},C.enc.Hex.parse(me.k),{iv:C.enc.Base64.parse(E.iv)}).toString(C.enc.Utf8));}catch(e){}\n'
           '    },')
auth = sub(auth, "document.write('<script src=\"assets/js/stock.js\"><\\/script>');",
           "document.write('<script src=\"assets/js/stock.enc.js\"><\\/script>');")
write('assets/js/auth.js', auth)

# ---------- 5. pages: load CryptoJS first, drop the public test-password box (and a brochure link that can't work) ----------
brochure_left_out = any('BROCHURE' in r.upper() for r in skipped_big)
for name in os.listdir(OUT):
    if not name.endswith('.html') or name == 'admin.html':
        continue
    t = read(name)
    t = sub(t, '<script src="assets/js/auth.js"', '<script src="assets/js/crypto-js.min.js"></script>\n    <script src="assets/js/auth.js"')
    if name == 'login.html':
        t = re.sub(r'\s*<div class="cb-login-test">.*?</button>\s*</div>', '', t, count=1, flags=re.S)
    if brochure_left_out:                      # the PDF isn't on the host: no link to it
        t = re.sub(r'\s*<a class="cb-brochure".*?</a>', '', t, count=1, flags=re.S)
    write(name, t)
if brochure_left_out:
    product_js = open(os.path.join(OUT, 'assets', 'js', 'product.js'), encoding='utf-8', newline='').read()
    product_js = re.sub(r'\r?\n[ \t]*if\(p\.brand==="awdis"\)addLink\("AWDis US brochure[^\n]*', '', product_js, count=1)
    write('assets/js/product.js', product_js)
login_js = read('assets/js/login.js')
login_js = re.sub(r'\n\s*\$\("\.cb-login-fill"\)\.addEventListener\("click",function\(\)\{.*?\n\s*\}\);', '', login_js, count=1, flags=re.S)
write('assets/js/login.js', login_js)

# ---------- report ----------
leaks = [f for f in ('login.html', 'assets/js/login.js', 'assets/js/auth.js') if any(pw in read_out for pw in passwords.values()
         for read_out in [open(os.path.join(OUT, f), encoding='utf-8').read()])]
count = sum(len(fs) for _, _, fs in os.walk(OUT))
size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(OUT) for f in fs)
print('Built %s: %d files, %.0f MB' % (OUT, count, size / 1e6))
print('Stock encrypted for: %s' % ', '.join(passwords))
if leaks:
    print('WARNING: a password still appears in %s' % leaks)
for r in skipped_big:
    print('Left out (over 10 MB, too big for InfinityFree): %s' % r)
