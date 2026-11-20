# 初出順/時系列順 の各ページ（cache/lists/debut_*.html）から、おに譜面ごとの初出日・作品を debut.json に保存する
# ページがキャッシュに無ければ取得する。REFRESH=1 のときは、今も曲が追加されるページ（AC16）を取り直す
import json, re, html, glob, os, time, urllib.request, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
UA = 'Mozilla/5.0 (personal taiko quiz builder)'
DEBUT_PAGES = [  # (ページ名, キャッシュのファイル名, 新曲が追加されるか)
    ('AC1～AC6', 'debut_AC1-AC6.html', False),
    ('AC7～AC14', 'debut_AC7-AC14.html', False),
    ('AC15/無印～ムラサキ', 'debut_AC15-無印-ムラサキ.html', False),
    ('AC15/ホワイト～グリーン', 'debut_AC15-ホワイト-グリーン.html', False),
    ('AC16/2020～2023', 'debut_AC16-2020-2023.html', False),
    ('AC16', 'debut_AC16.html', True),
]


def fetch_page(name, path):
    url = 'https://wikiwiki.jp/taiko-fumen/' + urllib.parse.quote('収録曲/初出順/時系列順/' + name)
    wait = 60
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=30) as r:
                t = r.read().decode('utf-8')
            break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or wait > 1200:
                raise
            print('429, wait', wait, flush=True)
            time.sleep(wait)
            wait *= 2
    open(path, 'w', encoding='utf-8').write(t)
    time.sleep(float(os.environ.get('DELAY', '20')))


os.makedirs(os.path.join(HERE, 'cache', 'lists'), exist_ok=True)
for name, fn, active in DEBUT_PAGES:
    p = os.path.join(HERE, 'cache', 'lists', fn)
    if not os.path.exists(p) or (active and os.environ.get('REFRESH')):
        print('fetch debut page', name, flush=True)
        fetch_page(name, p)


def strip(s):
    s = re.sub(r'<a [^>]*class="note_super[^"]*"[^>]*>.*?</a>', '', s, flags=re.S)
    s = re.sub(r'<br[^>]*>', ' ', s)
    s = re.sub(r'<[^>]+>', '', s)
    return html.unescape(s).strip()


out = {}
combos = {}
by_date = {}   # 日付 → その日に追加された行の作品（脚注の日付から作品を引くため）
later = {}     # 脚注に書かれた、後から追加された譜面の日付
for f in sorted(glob.glob(os.path.join(HERE, 'cache', 'lists', 'debut_*.html'))):
    t = open(f, encoding='utf-8').read()
    b = t[t.find('id="body"'):]
    b = b[:b.find('運営からのお知らせ')]
    for tbl in re.findall(r'<table>.*?</table>', b, flags=re.S):
        if '曲名' not in tbl:
            continue
        section = ''
        pending = {}
        for row in re.findall(r'<tr>(.*?)</tr>', tbl, flags=re.S):
            raw = re.findall(r'<td([^>]*)>(.*?)</td>', row, flags=re.S)
            if len(raw) == 1:
                section = strip(raw[0][1])
                pending = {}
                continue
            # rowspan / colspan を展開
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
                span = int((re.search(r'colspan="(\d+)"', attr) or [0, 1])[1])
                rs = int((re.search(r'rowspan="(\d+)"', attr) or [0, 1])[1])
                for k in range(span):
                    if rs > 1:
                        pending[col] = [c, rs - 1]
                    cells.append(c)
                    col += 1
            # 脚注のツールチップは解析対象から外す（後で別に読む）
            plain = [re.sub(r'data-tooltip-content="[^"]*"', '', c) for c in cells]
            oni = [html.unescape(m) for c in plain for m in re.findall(r'title="収録曲/おに/([^"]+)"', c)]
            texts = [strip(c) for c in plain]
            date = next((x for x in texts if re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}', x)), '')
            work = texts[0] if texts and not re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}', texts[0]) else ''
            sec = re.sub(r'\(.*?\)|（.*?）', '', section).replace('稼働', '').strip()
            if date and work:
                by_date.setdefault(date, {'date': date, 'sec': sec, 'work': work})
            # 脚注「○○(裏譜面)は 2022/9/22」: 表と別の日に追加された譜面
            for c in cells:
                for tip in re.findall(r'data-tooltip-content="([^"]*)"', c):
                    tip = html.unescape(tip)
                    for name, d in re.findall(r'title="収録曲/おに/([^"]+)"[^<]*>[^<]*</a>\s*は\s*<strong>(\d{4}/\d{1,2}/\d{1,2})</strong>', tip):
                        later.setdefault(html.unescape(name), d)
            if not oni:
                continue
            combos[(sec, work)] = combos.get((sec, work), 0) + 1
            for name in oni:
                if name not in out:
                    out[name] = {'date': date, 'sec': sec, 'work': work}

def dkey(d):
    y, m, dd = d.split('/')
    return (int(y), int(m), int(dd))


dates_sorted = sorted(by_date, key=dkey)
for name, d in later.items():
    if name in out and out[name]['date'] == d:
        continue
    info = by_date.get(d)
    if not info:
        # 同じ日の行がなければ、その日以前で一番近い行の時期（バージョン）だけ使う
        prev = [x for x in dates_sorted if dkey(x) <= dkey(d)]
        if prev:
            info = {'sec': by_date[prev[-1]]['sec'], 'work': ''}
    out[name] = {'date': d, 'sec': info['sec'] if info else '', 'work': info['work'] if info else '', 'later': True}

json.dump(out, open(os.path.join(HERE, 'debut.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
with open(os.path.join(HERE, 'debut_combos.txt'), 'w', encoding='utf-8') as o:
    for k, v in combos.items():
        print(k, v, file=o)
print('oni charts', len(out))
