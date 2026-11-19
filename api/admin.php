<?php
/* Citadel Brands — site admin API. Used by admin.html when the website runs on a PHP host (InfinityFree).
   Sign-in is checked here against api/admin-config.php (made by tools/build_hosting.py; never public).
   Signed-in admins can: list photo/video folders under assets/, upload images and videos, save the
   settings file (assets/js/site-config.js, rebuilt here from validated JSON) and read saved versions.
   Every change needs the session's CSRF token (X-CSRF header). Nothing else on the server can be written. */
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');
header('Referrer-Policy: same-origin');

const MAX_UPLOAD = 10 * 1024 * 1024;              // the host's per-file limit
const MAX_CONFIG = 2 * 1024 * 1024;
const KEEP_VERSIONS = 40;
const IMAGE_EXT = ['jpg', 'jpeg', 'jfif', 'png', 'webp', 'gif'];
const VIDEO_EXT = ['mp4', 'webm'];
$ROOT = dirname(__DIR__);
$HISTORY = __DIR__ . '/history';
$DATA = __DIR__ . '/data';
$CONF = is_file(__DIR__ . '/admin-config.php') ? (include __DIR__ . '/admin-config.php') : null;

session_name('cbadmin');
session_set_cookie_params(['lifetime' => 0, 'path' => '/', 'httponly' => true, 'samesite' => 'Strict',
  'secure' => (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')]);
session_start();

function out(array $d, int $code = 200): void { http_response_code($code); echo json_encode($d, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE); exit; }
function fail(string $msg, int $code = 400): void { out(['ok' => false, 'error' => $msg], $code); }
function body(): array { $j = json_decode((string)file_get_contents('php://input'), true); return is_array($j) ? $j : []; }
function me(): ?array { return $_SESSION['admin'] ?? null; }
function need_post(): void { if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') fail('Use POST.', 405); }
function need_admin(bool $write = false): void {
  if (!me()) fail('Please sign in.', 401);
  if (time() - ($_SESSION['seen'] ?? 0) > 8 * 3600) { session_unset(); fail('Your session expired. Sign in again.', 401); }
  $_SESSION['seen'] = time();
  if ($write) {
    need_post();
    if (!hash_equals($_SESSION['csrf'] ?? '', (string)($_SERVER['HTTP_X_CSRF'] ?? ''))) fail('Your session expired. Sign in again.', 401);
  }
}
function verify_password(string $pw, string $stored): bool {
  $p = explode('$', $stored);
  if (count($p) !== 4 || $p[0] !== 'pbkdf2_sha256') return false;
  $calc = hash_pbkdf2('sha256', $pw, base64_decode($p[2]), (int)$p[1], 32, true);
  return hash_equals((string)base64_decode($p[3]), $calc);
}
function ensure_dir(string $d): void { if (!is_dir($d)) mkdir($d, 0755, true); }
// folders the admin may browse / upload into (relative to the site root)
function folder_ok(string $rel, bool $upload = false): bool {
  if (strpos($rel, '..') !== false) return false;
  return (bool)preg_match($upload
    ? '#^assets/(uploads|figma|dark-theme|videos|logos|products/[a-z0-9_-]+)$#'
    : '#^assets(/[a-z0-9_-]+){1,2}$#', $rel);
}
function ext_of(string $n): string { return strtolower(pathinfo($n, PATHINFO_EXTENSION)); }
function safe_name(string $n): string {
  $base = strtolower(pathinfo($n, PATHINFO_FILENAME));
  $base = trim(preg_replace('/[^a-z0-9]+/', '-', $base), '-');
  return ($base === '' ? 'file' : substr($base, 0, 80)) . '.' . ext_of($n);
}
function attempts_file(string $data): string { ensure_dir($data); return $data . '/attempts.json'; }
function config_js(array $cfg): string {
  $head = "/* Citadel Brands — website settings, managed with admin.html (open it in Chrome or Edge).\n"
    . "   Saving in the admin page rewrites this file; hand edits are fine but keep it valid JSON.\n"
    . "     catalog   brands / categories / styles added or edited in the admin page, extra colours\n"
    . "     stock     low: below this a size shows \"Only N left\"; tiers: quantities at or above a tier show as \"500+\"\n"
    . "     slides    homepage hero slides, in order (hidden: true keeps a slide without showing it)\n"
    . "     banners   homepage images by slot (data-slot in index.html) -> {src, alt, pos, zoom, fit}\n"
    . "     brands    brand page banners -> {hero, heroPos}\n"
    . "     layout    product card shape, photo fit, inner margin, background, corners, spacing\n"
    . "     products  per style -> {img, img2, gallery, pos, zoom} */\n";
  return $head . 'window.CB_SITE_CONFIG=' . json_encode($cfg, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . ";\n";
}

$action = (string)($_GET['action'] ?? '');
switch ($action) {

case 'ping':
  out(['ok' => true, 'api' => 'citadel-admin', 'configured' => is_array($CONF) && !empty($CONF['users'])]);

case 'me':
  if (!me()) out(['ok' => false], 200);
  need_admin();
  out(['ok' => true, 'user' => me(), 'csrf' => $_SESSION['csrf']]);

case 'login':
  need_post();
  if (!is_array($CONF) || empty($CONF['users'])) fail('The admin account isn\'t set up on this server.', 503);
  $ip = $_SERVER['REMOTE_ADDR'] ?? '?';
  $af = attempts_file($DATA);
  $all = is_file($af) ? (json_decode((string)file_get_contents($af), true) ?: []) : [];
  $rec = $all[$ip] ?? ['n' => 0, 't' => 0];
  if ($rec['n'] >= 5 && time() - $rec['t'] < 900) fail('Too many attempts. Try again in 15 minutes.', 429);
  $b = body();
  $email = strtolower(trim((string)($b['email'] ?? '')));
  $pw = (string)($b['password'] ?? '');
  $user = null;
  foreach ($CONF['users'] as $u) if (hash_equals(strtolower($u['email']), $email) && verify_password($pw, $u['hash'])) $user = $u;
  if (!$user) {
    $all[$ip] = ['n' => (time() - $rec['t'] < 900 ? $rec['n'] : 0) + 1, 't' => time()];
    file_put_contents($af, json_encode($all), LOCK_EX);
    usleep(600000);
    fail('That email and password don\'t match an admin account.', 401);
  }
  unset($all[$ip]); file_put_contents($af, json_encode($all), LOCK_EX);
  session_regenerate_id(true);
  $_SESSION['admin'] = ['email' => $user['email'], 'name' => $user['name'] ?? 'Admin'];
  $_SESSION['csrf'] = bin2hex(random_bytes(32));
  $_SESSION['seen'] = time();
  out(['ok' => true, 'user' => me(), 'csrf' => $_SESSION['csrf']]);

case 'logout':
  need_post();
  $_SESSION = [];
  session_destroy();
  out(['ok' => true]);

case 'list':
  need_admin();
  $rel = trim((string)($_GET['dir'] ?? ''), '/');
  if (!folder_ok($rel)) fail('That folder can\'t be listed.');
  $dir = $ROOT . '/' . $rel;
  $files = [];
  if (is_dir($dir)) foreach (scandir($dir) as $n) {
    if ($n[0] === '.' || !is_file("$dir/$n")) continue;
    if (!in_array(ext_of($n), array_merge(IMAGE_EXT, VIDEO_EXT, ['svg']), true)) continue;
    $files[] = ['name' => $n, 'size' => filesize("$dir/$n")];
  }
  out(['ok' => true, 'files' => $files]);

case 'upload':
  need_admin(true);
  $rel = trim((string)($_POST['dir'] ?? ''), '/');
  if (!folder_ok($rel, true)) fail('Uploads can\'t go into that folder.');
  $f = $_FILES['file'] ?? null;
  if (!$f || ($f['error'] ?? 1) !== UPLOAD_ERR_OK) fail('The upload didn\'t arrive. It may be over the server\'s size limit.');
  if ($f['size'] > MAX_UPLOAD) fail('That file is over 10 MB. Compress it first.');
  $ext = ext_of((string)$f['name']);
  if (in_array($ext, IMAGE_EXT, true)) {
    $info = @getimagesize($f['tmp_name']);
    if (!$info) fail('That file isn\'t a readable image.');
  } elseif (!in_array($ext, VIDEO_EXT, true)) fail('Only JPG, PNG, WebP, GIF, MP4 and WebM files can be uploaded.');
  $dir = $ROOT . '/' . $rel;
  ensure_dir($dir);
  $name = safe_name((string)$f['name']);
  $base = pathinfo($name, PATHINFO_FILENAME);
  for ($i = 2; file_exists("$dir/$name"); $i++) $name = "$base-$i.$ext";
  if (!move_uploaded_file($f['tmp_name'], "$dir/$name")) fail('The server couldn\'t store the file.', 500);
  @chmod("$dir/$name", 0644);
  out(['ok' => true, 'path' => "$rel/$name", 'size' => filesize("$dir/$name")]);

case 'save':
  need_admin(true);
  $raw = (string)file_get_contents('php://input');
  if (strlen($raw) > MAX_CONFIG) fail('The settings are too large.');
  $b = json_decode($raw, true);
  $cfg = $b['config'] ?? null;
  if (!is_array($cfg)) fail('The settings weren\'t valid.');
  $allowed = ['stock', 'slides', 'banners', 'brands', 'products', 'catalog', 'layout'];
  foreach (array_keys($cfg) as $k) if (!in_array($k, $allowed, true)) fail("Unknown setting: $k");
  $js = config_js($cfg);
  $target = $ROOT . '/assets/js/site-config.js';
  ensure_dir($HISTORY);
  $versions = glob($HISTORY . '/site-config-*.js') ?: [];
  if (!$versions && is_file($target)) copy($target, $HISTORY . '/site-config-' . date('Y-m-d_His', time() - 1) . '-before-admin.js');
  if (file_put_contents($target . '.tmp', $js, LOCK_EX) === false || !rename($target . '.tmp', $target)) fail('The server couldn\'t write the settings file.', 500);
  file_put_contents($HISTORY . '/site-config-' . date('Y-m-d_His') . '.js', $js, LOCK_EX);
  $versions = glob($HISTORY . '/site-config-*.js') ?: [];
  sort($versions);
  foreach (array_slice($versions, 0, max(0, count($versions) - KEEP_VERSIONS)) as $old) @unlink($old);
  out(['ok' => true, 'saved' => date('c')]);

case 'history':
  need_admin();
  $list = [];
  foreach (glob($HISTORY . '/site-config-*.js') ?: [] as $f) $list[] = ['name' => basename($f), 'size' => filesize($f)];
  out(['ok' => true, 'versions' => $list]);

case 'version':
  need_admin();
  $n = (string)($_GET['name'] ?? '');
  if (!preg_match('/^site-config-[0-9_-]+(-before-admin)?\.js$/', $n) || !is_file("$HISTORY/$n")) fail('That version doesn\'t exist.', 404);
  out(['ok' => true, 'text' => file_get_contents("$HISTORY/$n")]);

default:
  fail('Unknown action.', 404);
}
