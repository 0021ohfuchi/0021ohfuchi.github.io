# YouTube チャンネル（@0021_taiko）の最新動画を取り、latest-video.js に書く。
# トップページ（index.html）がこれを読んで「最新の動画」を表示する。GitHub Actions（.github/workflows/latest-video.yml）が定期的に実行する。
#
# 環境変数 YOUTUBE_API_KEY（YouTube Data API v3 のキー）があれば、日本語のタイトル・説明文（YouTube Studio の「翻訳」に登録したもの）を取る。
# キーが無い、または API が失敗したときは、RSS から英語のタイトルだけ取る。
import json, os, re, sys, urllib.request, urllib.parse, html

CHANNEL_ID = 'UCILPNLmKxGQXJHtdp-Stcvw'
RSS = 'https://www.youtube.com/feeds/videos.xml?channel_id=' + CHANNEL_ID
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'latest-video.js')
KEY = os.environ.get('YOUTUBE_API_KEY', '').strip()
N = 5


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=60).read().decode('utf-8')


def short_desc(text):
    """説明文の頭の数行だけ（機材紹介や「チャンネル登録お願いします」以降は載せない）"""
    text = (text or '').replace('\n', '\n')
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.search(r'[ー~\-=]{5,}|チャンネル登録|subscribe', line, re.I) or line.startswith('励み'):
            break
        out.append(line)
    return ' '.join(out)[:160]


def from_api():
    # アップロード一覧（UU + チャンネル ID の後ろ）で最新の動画を取り、日本語（hl=ja）のタイトル・説明文を付ける
    pl = json.loads(get('https://www.googleapis.com/youtube/v3/playlistItems?' + urllib.parse.urlencode(
        {'part': 'contentDetails', 'playlistId': 'UU' + CHANNEL_ID[2:], 'maxResults': N, 'key': KEY})))
    ids = [i['contentDetails']['videoId'] for i in pl.get('items', [])]
    if not ids:
        return []
    vs = json.loads(get('https://www.googleapis.com/youtube/v3/videos?' + urllib.parse.urlencode(
        {'part': 'snippet', 'id': ','.join(ids), 'hl': 'ja', 'key': KEY})))
    by_id = {v['id']: v['snippet'] for v in vs.get('items', [])}
    videos = []
    for i in ids:
        s = by_id.get(i)
        if not s:
            continue
        loc = s.get('localized') or {}
        videos.append({'id': i, 'title': (loc.get('title') or s['title']).strip(),
                       'desc': short_desc(loc.get('description') or s.get('description')),
                       'date': s['publishedAt'][:10].replace('-', '/')})
    return videos


def from_rss():
    xml = get(RSS)
    videos = []
    for e in re.findall(r'<entry>(.*?)</entry>', xml, re.S)[:N]:
        vid = re.search(r'<yt:videoId>(.*?)</yt:videoId>', e)
        title = re.search(r'<title>(.*?)</title>', e, re.S)
        pub = re.search(r'<published>(.*?)</published>', e)
        if vid and title and pub:
            videos.append({'id': vid.group(1), 'title': html.unescape(title.group(1)).strip(), 'desc': '',
                           'date': pub.group(1)[:10].replace('-', '/')})
    return videos


videos = []
if KEY:
    try:
        videos = from_api()
    except Exception as e:
        print('!! YouTube API が失敗したので RSS を使います:', type(e).__name__, flush=True)
if not videos:
    videos = from_rss()
if not videos:
    sys.exit('動画が取得できませんでした')
js = '// 自動生成: scripts/fetch_youtube.py（YouTube の最新動画。新しいものが先頭）\nwindow.LATEST_VIDEOS=' + json.dumps(videos, ensure_ascii=False, indent=1) + ';\n'
old = open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
if old != js:
    open(OUT, 'w', encoding='utf-8', newline='\n').write(js)
    print('updated', videos[0]['id'])
else:
    print('no change')
