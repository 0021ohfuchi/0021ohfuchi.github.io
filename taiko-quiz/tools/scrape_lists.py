# おに★1〜10 の一覧ページを取得し、曲リストを lists.json に保存する
import json, re, sys, time, html, urllib.request, urllib.parse, os

BASE = 'https://wikiwiki.jp'
CACHE = sys.argv[1] if len(sys.argv) > 1 else 'cache'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'lists.json'
os.makedirs(CACHE, exist_ok=True)
UA = 'Mozilla/5.0 (personal taiko quiz builder)'


def fetch(path, fname):
    p = os.path.join(CACHE, fname)
    # REFRESH=1 のときはキャッシュを使わず取り直す（自動更新で新曲・★の変更を拾うため）
    if os.path.exists(p) and not os.environ.get('REFRESH'):
        return open(p, encoding='utf-8').read()
    url = BASE + path
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    wait = 30
    while True:
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                t = r.read().decode('utf-8')
            break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or wait > 600:
                raise
            print('429, wait', wait, flush=True)
            time.sleep(wait)
            wait *= 2
    open(p, 'w', encoding='utf-8').write(t)
    time.sleep(4)
    return t


def strip(s):
    s = re.sub(r'<br[^>]*>', '/', s)
    s = re.sub(r'<a [^>]*class="note_super[^"]*"[^>]*>.*?</a>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '', s)
    return html.unescape(s).strip()


songs = []
PAGES = [('1-4', '★×1～4', None)] + [(str(l), f'★×{l}', l) for l in range(5, 11)]
for key, pname, plv in PAGES:
    path = '/taiko-fumen/' + urllib.parse.quote(f'収録曲/おに/{pname}')
    t = fetch(path, f'list_oni_{key}.html')
    body = t[t.find('id="body"'):] if 'id="body"' in t else t
    # 見出しと表を順に走査
    section = ''
    lv = plv
    for m in re.finditer(r'<h([2-5])[^>]*>(.*?)</h\1>|<table>(.*?)</table>', body, flags=re.S):
        if m.group(1):
            h = strip(m.group(2))
            if h in ('運営からのお知らせ',) or h.startswith('基本情報'):
                break
            ms = re.match(r'^★×(\d+)$', h)
            if ms:
                lv = int(ms.group(1))
            else:
                section = h
                lv = plv
            continue
        if lv is None:
            continue
        tbl = m.group(3)
        if '最大コンボ数' not in tbl:
            continue
        genre = ''
        pending = {}  # 列番号 -> [セル内容, 残り行数]（rowspan 対応）
        for row in re.findall(r'<tr>(.*?)</tr>', tbl, flags=re.S):
            raw = re.findall(r'<td([^>]*)>(.*?)</td>', row, flags=re.S)
            if len(raw) == 1 and 'colspan' in raw[0][0]:
                if strip(raw[0][1]) and not re.search(r'title="収録曲/おに/', raw[0][1]):
                    genre = strip(raw[0][1])
                    pending = {}
                    continue
            # rowspan を展開して完全な行を作る
            cells, col, it = [], 0, iter(raw)
            while True:
                if col in pending:
                    cells.append(pending[col][0])
                    pending[col][1] -= 1
                    if pending[col][1] <= 0:
                        del pending[col]
                    col += 1
                    continue
                nxt = next(it, None)
                if nxt is None:
                    break
                attr, c = nxt
                m = re.search(r'rowspan="(\d+)"', attr)
                if m and int(m.group(1)) > 1:
                    pending[col] = [c, int(m.group(1)) - 1]
                cells.append(c)
                col += 1
            li = next((i for i, c in enumerate(cells)
                       if re.search(r'title="収録曲/おに/', c)), None)
            if li is None:
                continue
            a = re.search(r'<a href="([^"]+)"[^>]*title="([^"]+)"', cells[li])
            if not a:
                continue
            rest = cells[li + 1:]
            prev = (strip(rest[0]) if rest else '', strip(rest[1]) if len(rest) > 1 else '')
            songs.append({
                'level': lv,
                'section': section,
                'genre': genre,
                'name': strip(cells[li]),
                'href': html.unescape(a.group(1)),
                'page': html.unescape(a.group(2)),
                'bpm': prev[0],
                'combo': prev[1],
            })
    print(pname, len(songs), flush=True)

json.dump(songs, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('total', len(songs))
