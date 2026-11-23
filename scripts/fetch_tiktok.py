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
title = (e.get('description') or e.get('title') or '').strip()
title = re.split(r'\s+左利きの太鼓の達人', title)[0].strip() or title  # 自己紹介文の前までを動画のタイトルとする
ts = e.get('timestamp')
v = {'id': str(e['id']), 'title': title[:120],
     'date': time.strftime('%Y/%m/%d', time.gmtime(ts + 9 * 3600)) if ts else '',
     'url': e.get('url') or f'https://www.tiktok.com/@{USER}/video/{e["id"]}'}
js = '// 自動生成: scripts/fetch_tiktok.py（TikTok の最新動画）\nwindow.LATEST_TIKTOK=' + json.dumps(v, ensure_ascii=False, indent=1) + ';\n'
old = open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
if old != js:
    open(OUT, 'w', encoding='utf-8', newline='\n').write(js)
    print('updated', v['id'])
else:
    print('no change')
