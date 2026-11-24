# TikTok（@0021_taiko）の最新動画を yt-dlp で取り、latest-tiktok.js に書く。トップページが「TikTok の最新動画」に表示する。
# TikTok は RSS などが無いので yt-dlp（動画の一覧だけ取る。ダウンロードはしない）を使う。取れなかったときは前回のファイルのままにする。
import json, os, re, subprocess, sys, time

USER = '0021_taiko'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'latest-tiktok.js')

import shutil
YTDLP = [shutil.which('yt-dlp')] if shutil.which('yt-dlp') else [sys.executable, '-m', 'yt_dlp']
r = subprocess.run(YTDLP + ['--flat-playlist', '--playlist-end', '8', '-J', 'https://www.tiktok.com/@' + USER],
                   capture_output=True, timeout=300)
if r.returncode != 0:
    sys.exit('TikTok の一覧が取れませんでした: ' + r.stderr.decode('utf-8', 'replace')[-300:])
entries = [e for e in json.loads(r.stdout.decode('utf-8')).get('entries', []) if e.get('id')]
if not entries:
    sys.exit('TikTok の動画が見つかりませんでした')
# 固定表示の動画が先頭に来ることがあるので、投稿日時が一番新しいものを選ぶ
e = max(entries, key=lambda x: x.get('timestamp') or 0)
full = (e.get('description') or e.get('title') or '').strip()
title = re.split(r'\s+左利きの太鼓の達人', full)[0].strip() or full  # 自己紹介文の前までを動画のタイトルとする
# 説明欄: タイトルより後ろの文章（使用機材の紹介の手前まで）にハッシュタグを足す
rest = full[len(title):].strip()
rest = re.split(r'\s*(?:モニター|キーボード|カメラ|イヤホン|マウス|コントローラー)\s*[:：]', rest)[0]
tags = re.findall(r'#\S+', full)
desc = ' '.join([re.sub(r'#\S+', '', rest).strip()] + tags).strip()
ts = e.get('timestamp')
v = {'id': str(e['id']), 'title': title[:120], 'desc': desc[:200],
     'date': time.strftime('%Y/%m/%d', time.gmtime(ts + 9 * 3600)) if ts else '',
     'url': e.get('url') or f'https://www.tiktok.com/@{USER}/video/{e["id"]}'}
# サムネイル: TikTok の画像の URL は数日で期限が切れるので、取得できたときにファイル（latest-tiktok.jpg）として保存して使う
THUMB = os.path.join(os.path.dirname(OUT), 'latest-tiktok.jpg')
v['thumb'] = False


def shrink(data):
    """表示サイズ（高さ 180px）の 2 倍＝高さ 360px の JPEG に縮める（元は 500KB 前後 → 20KB 前後）。Pillow が無ければそのまま"""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert('RGB')
        if im.height > 360:
            im = im.resize((round(im.width * 360 / im.height), 360), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=78, optimize=True)
        return buf.getvalue()
    except Exception as ex:
        print('!! 画像を縮められませんでした（そのまま使います）:', type(ex).__name__, flush=True)
        return data

try:
    import urllib.request
    cands = sorted([t for t in (e.get('thumbnails') or []) if t.get('url')], key=lambda t: (t.get('id') != 'cover', -(t.get('preference') or 0)))
    for t in cands:
        req = urllib.request.Request(t['url'], headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.tiktok.com/'})
        resp = urllib.request.urlopen(req, timeout=60)
        data = resp.read()
        if 'image' in (resp.headers.get('Content-Type') or '') and len(data) > 1000:
            data = shrink(data)
            open(THUMB, 'wb').write(data)  # 同じファイル名で上書きするので、古いサムネイルは残らない
            v['thumb'] = True
            break
except Exception as ex:
    print('!! サムネイルが取れませんでした:', type(ex).__name__, flush=True)
if not v['thumb'] and os.path.exists(THUMB):
    # 取れなかったとき、前回と同じ動画ならサムネイルも前回のものを使う
    try:
        prev = json.loads(open(OUT, encoding='utf-8').read().split('window.LATEST_TIKTOK=', 1)[1].rsplit(';', 1)[0])
        v['thumb'] = prev.get('id') == v['id'] and bool(prev.get('thumb'))
    except Exception:
        pass
js = '// 自動生成: scripts/fetch_tiktok.py（TikTok の最新動画）\nwindow.LATEST_TIKTOK=' + json.dumps(v, ensure_ascii=False, indent=1) + ';\n'
old = open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
if old != js:
    open(OUT, 'w', encoding='utf-8', newline='\n').write(js)
    print('updated', v['id'])
else:
    print('no change')
