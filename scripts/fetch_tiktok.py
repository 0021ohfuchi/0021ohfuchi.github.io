# TikTok（@0021_taiko）の最新動画を yt-dlp で取り、latest-tiktok.js に書く。トップページの「TikTok」の枠に表示する。
# TikTok は RSS などが無いので yt-dlp（動画の一覧だけ取る。ダウンロードはしない）を使う。取れなかったときは前回のファイルのままにする。
# 新しい順に最大 N 本。サムネイルは tiktok/<動画ID>.jpg に保存する（TikTok の画像の URL は数日で期限が切れるため）。
import json, os, re, shutil, subprocess, sys, time, urllib.request

USER = '0021_taiko'
N = 6
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'latest-tiktok.js')
THUMBS = os.path.join(ROOT, 'tiktok')

YTDLP = [shutil.which('yt-dlp')] if shutil.which('yt-dlp') else [sys.executable, '-m', 'yt_dlp']
r = subprocess.run(YTDLP + ['--flat-playlist', '--playlist-end', str(N + 4), '-J', 'https://www.tiktok.com/@' + USER],
                   capture_output=True, timeout=300)
if r.returncode != 0:
    sys.exit('TikTok の一覧が取れませんでした: ' + r.stderr.decode('utf-8', 'replace')[-300:])
entries = [e for e in json.loads(r.stdout.decode('utf-8')).get('entries', []) if e.get('id')]
if not entries:
    sys.exit('TikTok の動画が見つかりませんでした')
# 固定表示の動画が先頭に来ることがあるので、投稿日時の新しい順に並べ直す
entries = sorted(entries, key=lambda x: x.get('timestamp') or 0, reverse=True)[:N]


def shrink(data):
    """縦 480px の JPEG に縮める（元は 500KB 前後 → 30KB 前後）。Pillow が無ければそのまま"""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert('RGB')
        if im.height > 480:
            im = im.resize((round(im.width * 480 / im.height), 480), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=80, optimize=True)
        return buf.getvalue()
    except Exception as ex:
        print('!! 画像を縮められませんでした（そのまま使います）:', type(ex).__name__, flush=True)
        return data


def save_thumb(e, path):
    """サムネイルを保存できたら True。すでに保存してあればそれを使う"""
    if os.path.exists(path):
        return True
    cands = sorted([t for t in (e.get('thumbnails') or []) if t.get('url')],
                   key=lambda t: (t.get('id') != 'cover', -(t.get('preference') or 0)))
    for t in cands:
        try:
            req = urllib.request.Request(t['url'], headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.tiktok.com/'})
            resp = urllib.request.urlopen(req, timeout=60)
            data = resp.read()
            if 'image' in (resp.headers.get('Content-Type') or '') and len(data) > 1000:
                open(path, 'wb').write(shrink(data))
                return True
        except Exception as ex:
            print('!! サムネイルが取れませんでした:', e['id'], type(ex).__name__, flush=True)
    return False


os.makedirs(THUMBS, exist_ok=True)
videos = []
for e in entries:
    full = (e.get('description') or e.get('title') or '').strip()
    title = re.split(r'\s+左利きの太鼓の達人', full)[0].strip() or full  # 自己紹介文の前までを動画のタイトルとする
    ts = e.get('timestamp')
    vid = str(e['id'])
    videos.append({'id': vid, 'title': title[:120],
                   'date': time.strftime('%Y/%m/%d', time.gmtime(ts + 9 * 3600)) if ts else '',
                   'thumb': save_thumb(e, os.path.join(THUMBS, vid + '.jpg'))})
# 表示しなくなった動画のサムネイルは消す
keep = {v['id'] + '.jpg' for v in videos}
for f in os.listdir(THUMBS):
    if f.endswith('.jpg') and f not in keep:
        os.remove(os.path.join(THUMBS, f))

js = '// 自動生成: scripts/fetch_tiktok.py（TikTok の最新動画。新しいものが先頭。thumb: tiktok/<id>.jpg があるか）\nwindow.LATEST_TIKTOKS=' + json.dumps(videos, ensure_ascii=False, indent=1) + ';\n'
old = open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
if old != js:
    open(OUT, 'w', encoding='utf-8', newline='\n').write(js)
    print('updated', videos[0]['id'], len(videos))
else:
    print('no change')
