# lists.json の各曲ページを取得し、譜面画像・読み・初出・平均密度を details.json に保存する
# 使い方: python scrape_songs.py <cacheDir> <lists.json> <details.json>
# Wiki に負荷をかけないよう 1 ページごとに数秒待つ。中断しても再実行すればキャッシュから再開する。
import json, re, sys, time, html, urllib.request, urllib.error, urllib.parse, os, hashlib

BASE = 'https://wikiwiki.jp'
# extra_songs.py から parse() などを使えるよう、取り込まれたときは引数を読まない
if __name__ == '__main__':
    CACHE, LISTS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
else:
    CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache', 'songs')
# Wiki は短時間に数回アクセスすると 429 を返すため、約20秒に1ページのペースで取得する
DELAY = float(os.environ.get('DELAY', '20'))


def save_and_build():
    json.dump(details, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    import subprocess
    subprocess.run([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_data.py')])
os.makedirs(CACHE, exist_ok=True)
UA = 'Mozilla/5.0 (personal taiko quiz builder)'


def fetch(href, force=False):
    fname = hashlib.md5(href.encode()).hexdigest() + '.html'
    p = os.path.join(CACHE, fname)
    if os.path.exists(p) and not force:
        return open(p, encoding='utf-8').read(), False
    req = urllib.request.Request(BASE + href, headers={'User-Agent': UA})
    wait = 60
    while True:
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                t = r.read().decode('utf-8')
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                t = ''
                break
            if e.code not in (429, 500, 502, 503, 504) or wait > 1200:
                raise
            print('429, wait', wait, flush=True)
            time.sleep(wait)
            wait *= 2
        except urllib.error.URLError as e:
            print('net error', e, 'wait', wait, flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 1200)
    open(p, 'w', encoding='utf-8').write(t)
    return t, True


def text(s):
    s = re.sub(r'<a [^>]*class="note_super[^"]*"[^>]*>.*?</a>', '', s, flags=re.S)
    s = re.sub(r'<rp>.*?</rp>', '', s, flags=re.S)
    s = re.sub(r'<br[^>]*>', '', s)
    s = re.sub(r'<[^>]+>', '', s)
    return html.unescape(s).strip()


# 曲の情報（アーティスト・作詞・作曲・主題歌など）。曲検索で作曲者やアニメ名から探せるようにする
# 曲ページ冒頭の箇条書きと「その他」節のうち、曲そのものについての文だけを取り出す（譜面・配信の話は除く）
KW = re.compile(r'アーティスト|歌手|作詞|作曲|編曲|歌唱|ボーカル|歌は|主題歌|テーマ|挿入歌|オープニング|エンディング|OP|ED|BGM|原曲|CM|映画|アニメ|ゲーム|ドラマ|番組|楽曲|曲である|使用|担当|作者|提供|リミックス|アレンジ|名義')
NG = re.compile(r'配信され|配信開始|収録され|削除|復活|期間|譜面|コンボ|小節|連打|風船|音符|ゴーゴー|スコア|段位|課題曲|難易度|★|BPM|HS|分岐|クリア')
def _txt(s):
    s = re.sub(r'<a [^>]*class="note_super[^"]*"[^>]*>.*?</a>', '', s, flags=re.S)
    s = re.sub(r'<rp>.*?</rp>|<rt>.*?</rt>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()
def _items(seg):
    seg = re.sub(r'<div class="lazy-dom-placeholder".*?loading\.\.\.', '', seg, flags=re.S)
    seg = re.sub(r'<div class="fold-container.*', '', seg, flags=re.S)
    # 入れ子の li は外側の li の中身から切り離して、それぞれ 1 行にする
    seg = re.sub(r'<(ul|ol)[^>]*>', '\n', seg); seg = re.sub(r'</(ul|ol)>', '\n', seg)
    out = []
    for part in re.split(r'<li[^>]*>|</li>|\n', seg):
        x = _txt(part)
        if x and x.endswith('。') and '<' not in x: out.append(x)
    return out
def parse_meta(t):
    lines = []
    i = t.find('<div id="content">')
    if i < 0: return lines
    j = t.find('<h3', i)
    intro = _items(t[i:j]) if j > 0 else []
    lines += [x for x in intro if len(x) <= 120]
    m = re.search(r'<h3[^>]*>\s*その他.*?</h3>(.*?)(?=<h3|運営からのお知らせ|<div id="comment)', t[j:], flags=re.S)
    if m:
        for x in _items(m.group(1)):
            if KW.search(x) and not NG.search(x) and len(x) <= 140: lines.append(x)
    seen = []; [seen.append(x) for x in lines if x not in seen]
    return seen[:8]


# 今の AC（ニジイロ）では 1 曲が複数のジャンルに入っていることがある。詳細表では「キッズ(メイン)」「アニメ」のように
# メインのジャンルとほかのジャンルが同じ行に並ぶ。最後の「(メイン)」の行で有効なジャンルを、メインを先頭にして返す
GENRE_NAMES = {'ポップス', 'キッズ', 'アニメ', 'ボーカロイド™曲', 'ゲームミュージック', 'バラエティ', 'クラシック', 'ナムコオリジナル', 'どうよう'}
def parse_genres(t):
    i = t.find('id="h3_content_1_0"')
    j = t.find('</table>', i)
    if i < 0 or j < 0:
        return []
    rows = re.findall(r'<tr>(.*?)</tr>', t[i:j], flags=re.S)
    cells = []  # (行番号, 何行続くか, ジャンル, メインか)
    for k, tr in enumerate(rows):
        for attr, c in re.findall(r'<td([^>]*background-color[^>]*)>(.*?)</td>', tr, flags=re.S):
            x = re.sub(r'\s+', '', html.unescape(re.sub(r'<[^>]+>', '', c)))
            main = '(メイン)' in x
            x = re.sub(r'\(メイン\)|\*\d+$', '', x).replace('J-POP', 'ポップス')
            if x in GENRE_NAMES:
                rs = re.search(r'rowspan="(\d+)"', attr)
                cells.append((k, int(rs.group(1)) if rs else 1, x, main))
    mains = [c for c in cells if c[3]]
    if not mains:
        return []
    last = mains[-1][0]
    rows_main = {c[0] for c in mains}
    out = [mains[-1][2]]
    for k, span, g, main in cells:
        # (メイン) のある行（またはそこから下に続くセル）で、最後の (メイン) の行まで届いているもの
        if k <= last and k + span - 1 >= last and (k in rows_main or span > 1 and any(r in rows_main for r in range(k, k + span))) and g not in out:
            out.append(g)
    return out if len(out) > 1 else []

def parse(t):
    d = {}
    i = t.find('id="body"')
    j = t.find('運営からのお知らせ', i)
    body = t[i:j] if i >= 0 else ''
    if not body:
        return d
    # 読み: 詳細表タイトルの ruby
    m = re.search(r'<th colspan="\d+"[^>]*>(.*?)</th>', body, flags=re.S)
    if m and '<ruby>' in m.group(1):
        y = re.sub(r'<ruby>.*?<rt>(.*?)</rt>.*?</ruby>', r'\1', m.group(1), flags=re.S)
        d['yomi'] = text(y)
    # 初出バージョン: 詳細表 tbody 1行目の先頭セル
    m = re.search(r'<tbody><tr>(.*?)</tr>', body, flags=re.S)
    if m:
        cells = re.findall(r'<td([^>]*)>(.*?)</td>', m.group(1), flags=re.S)
        vs = []
        for attr, c in cells[:2]:
            if 'background-color' in attr:  # ジャンル列に達した
                break
            v = text(re.sub(r'<br[^>]*>', ' / ', c))
            if v:
                vs.append(v)
        if vs:
            d['ver'] = ' / '.join(vs)[:60]
    # 初出年: 「その他」節の配信日などの日付のうち最も古い年
    k = body.find('name ="other"')
    seg = body[k:body.find('name ="comment"', k)] if k >= 0 else ''
    years = [int(y) for y in re.findall(r'((?:19|20)\d\d)/\d{1,2}/\d{1,2}', seg)]
    if years:
        d['year'] = min(years)
    m = re.search(r'平均密度[^0-9]{0,30}?約?\s*([0-9.]+)\s*打/秒', text(body))
    if m:
        d['density'] = m.group(1)
    m = re.search(r'連打秒数[^0-9]{0,20}?約?\s*([0-9.]+)\s*秒', text(body))
    if m:
        d['roll'] = m.group(1)
    def find_imgs(part):
        imgs = []
        for src, hgt in re.findall(r'<img src="(https://cdn\.wikiwiki\.jp/to/w/taiko-fumen/[^"]+?/::ref/[^"?]+)[^>]*?height="(\d+)"', part):
            src = html.unescape(src)
            if '%3AHeader' in src or src in imgs or int(hgt) < 300:
                continue
            if not re.search(r'\.(png|jpe?g|gif)$', src, re.I):
                continue
            imgs.append(src)
        return imgs
    # 「譜面」見出し(name="score")以降の画像だけを使う。解説中の拡大図などは除外
    k = body.find('name ="score"')
    imgs = find_imgs(body[k:body.find('main-contents-bottom', k)]) if k >= 0 else []
    if not imgs and k < 0:
        imgs = find_imgs(body)[:1]
    d['imgs'] = imgs
    # 曲を流すための YouTube 動画（折りたたみの見出しで種類を判断し、曲だけが流れるものを優先）
    def rank(label):
        if '自動生成' in label:
            return 0
        if '公式音源' in label or label.startswith('MV'):
            return 1
        if 'オート動画' in label:
            return 2
        if 'プレイ動画' in label:
            return 3
        return 9
    vids = []
    for lab, content in re.findall(r'<div class="fold-summary[^"]*">(.*?)</div>\s*<div class="fold-content[^"]*">(.*?)</div>\s*</div>', body, flags=re.S):
        m = re.search(r'youtube(?:-nocookie)?\.com/embed/([\w-]{11})', html.unescape(content))
        if not m:
            continue
        lab = text(lab)
        if '閲覧注意' in lab or '2人用' in lab:
            continue
        r = rank(lab)
        if r < 9 and m.group(1) not in [v[1] for v in vids]:
            vids.append((r, m.group(1)))
    vids.sort(key=lambda v: v[0])
    if vids:
        d['yt'] = [[r, i] for r, i in vids[:3]]
    meta = parse_meta(t)
    if meta:
        d['meta'] = meta
    genres = parse_genres(t)
    if genres:
        d['genres'] = genres
    return d


def main():
    global details
    songs = json.load(open(LISTS, encoding='utf-8'))
    order ={'新筐体収録曲': 0, '難易度・ジャンル別曲数': 0, '新筐体期間限定曲': 1, '新筐体ブラジル版限定曲': 1,
             '新筐体未収録曲': 2, '幻の曲': 3}
    hrefs = []
    for s in sorted(songs, key=lambda s: (order.get(s['section'], 9), -s['level'])):
        if s['href'] not in hrefs:
            hrefs.append(s['href'])
    details = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    # 自動更新用の設定（環境変数）
    #   MAX_FETCH      : この回で Wiki から取得するページ数の上限（既定: 無制限）
    #   REFRESH_OLDEST : 取得日が古い順に、取得し直すページ数（Wiki 側の修正を取り込むため。既定: 0）
    MAX_FETCH = int(os.environ.get('MAX_FETCH', '0')) or None
    REFRESH_OLDEST = int(os.environ.get('REFRESH_OLDEST', '0'))
    todo = [h for h in hrefs if not (h in details and details[h].get('_v') == 6)]
    # キャッシュ済みのページ（extra_songs.py が先に取った曲など）は Wiki にアクセスせずに済むので先に読む
    cached = lambda h: os.path.exists(os.path.join(CACHE, hashlib.md5(h.encode()).hexdigest() + '.html'))
    todo.sort(key=lambda h: not cached(h))
    refresh = []
    if REFRESH_OLDEST:
        done = [h for h in hrefs if h in details and details[h].get('_v') == 6]
        done.sort(key=lambda h: details[h].get('ft', ''))
        refresh = done[:REFRESH_OLDEST]
    print('new/unparsed', len(todo), 'refresh', len(refresh), flush=True)
    n = fetched = 0
    for k, h in enumerate(todo + refresh):
        if MAX_FETCH is not None and fetched >= MAX_FETCH:
            print('reached MAX_FETCH', MAX_FETCH, flush=True)
            break
        t, net = fetch(h, force=h in refresh)
        d = parse(t)
        d['_v'] = 6
        if net:
            d['ft'] = time.strftime('%Y-%m-%d')
        else:
            old = details.get(h, {}).get('ft')
            p = os.path.join(CACHE, hashlib.md5(h.encode()).hexdigest() + '.html')
            d['ft'] = old or time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(p)))
        details[h] = d
        n += 1
        if net:
            fetched += 1
        if n % 10 == 0:
            save_and_build()
            print(time.strftime('%H:%M:%S'), f'{k + 1}/{len(todo) + len(refresh)}', flush=True)
        if net:
            time.sleep(DELAY)
    save_and_build()
    print('done', len(details), 'fetched', fetched)


if __name__ == '__main__':
    main()
