# YouTube チャンネル（@0021_taiko）の最新動画を RSS から取り、latest-video.js に書く。
# トップページ（index.html）がこれを読んで「最新の動画」を表示する。GitHub Actions（.github/workflows/latest-video.yml）が定期的に実行する。
import json, os, re, sys, urllib.request, html

CHANNEL_ID = 'UCILPNLmKxGQXJHtdp-Stcvw'
URL = 'https://www.youtube.com/feeds/videos.xml?channel_id=' + CHANNEL_ID
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'latest-video.js')

req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
xml = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
videos = []
for e in re.findall(r'<entry>(.*?)</entry>', xml, re.S)[:5]:
    vid = re.search(r'<yt:videoId>(.*?)</yt:videoId>', e)
    title = re.search(r'<title>(.*?)</title>', e, re.S)
    pub = re.search(r'<published>(.*?)</published>', e)
    if vid and title and pub:
        videos.append({'id': vid.group(1), 'title': html.unescape(title.group(1)).strip(), 'date': pub.group(1)[:10].replace('-', '/')})
if not videos:
    sys.exit('動画が取得できませんでした')
js = '// 自動生成: scripts/fetch_youtube.py（YouTube の最新動画。新しいものが先頭）\nwindow.LATEST_VIDEOS=' + json.dumps(videos, ensure_ascii=False, indent=1) + ';\n'
old = open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
if old != js:
    open(OUT, 'w', encoding='utf-8', newline='\n').write(js)
    print('updated', videos[0]['id'])
else:
    print('no change')
