# 作品ごとの収録曲（おに譜面）を集めて works.json に保存する
# 作品ページ（作品/○○）と、そのジャンル別ページ（作品/○○/ポップス など）の「収録曲/おに/…」リンクを集める
# 中断しても再実行すればキャッシュから再開する。完了ごとに build_data.py を実行して data.js を更新する
import json, re, sys, time, html, urllib.request, urllib.error, urllib.parse, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache', 'works')
OUT = os.path.join(HERE, 'works.json')
DELAY = float(os.environ.get('DELAY', '20'))
UA = 'Mozilla/5.0 (personal taiko quiz builder)'
os.makedirs(CACHE, exist_ok=True)

# (ページ名, 表示名, 種類) 古い順。海外版は AC11亜・AC12亜・AC16中（新AC中国版）・WM（新ACブラジル版）・TDM・米TDM・PS Vita1亜 だけ含める
# （NS1中国版・3DS2韓国版・新ACアジア版などは含めない。それらの曲は build_data.py で「海外の曲」にまとめる）
WORKS = [(f'作品/AC{i}', f'AC{i}', 'AC') for i in range(1, 12)] + [
    ('作品/AC11亜洲版', 'AC11亜', 'AC'),
    ('作品/AC12', 'AC12', 'AC'), ('作品/AC12増量版', 'AC12増量版', 'AC'), ('作品/AC12亜洲版', 'AC12亜', 'AC'),
    ('作品/AC13', 'AC13', 'AC'), ('作品/AC14', 'AC14', 'AC'),
    ('作品/新AC/Ver7.03まで', '新筐体 無印', 'AC'), ('作品/新AC/KATSU-DON Ver.8.03まで', 'KATSU-DON', 'AC'),
] + [(f'作品/新AC/{v}', v, 'AC') for v in ['ソライロ', 'モモイロ', 'キミドリ', 'ムラサキ', 'ホワイト', 'レッド', 'イエロー', 'ブルー', 'グリーン',
                                           'ニジイロ2020', 'ニジイロ2021', 'ニジイロ2022', 'ニジイロ2023', 'ニジイロ2024', 'ニジイロ2025']] + [
    ('作品/新AC', 'ニジイロ（現行）', 'AC'),
    ('作品/新AC中国版', 'AC16中', 'AC'), ('作品/新ACブラジル版', 'WM', 'AC'),
] + [(f'作品/{c}', c, 'CS') for c in [
    'CS1', 'CS2', 'CS3', 'CS4', 'CS5', 'CS6', 'CS7', 'アニメ祭り', 'アニメスペシャル', 'TDM', 'PSP1', 'PSP2', 'PSPDX', 'DS1', 'DS2', 'DS3', 'Wii1', 'Wii2', 'Wii3', 'Wii4', 'Wii5',
    '3DS1', '3DS2', '3DS3', 'Wii U1', 'Wii U2', 'Wii U3', 'PS Vita1', 'PS Vita MS', 'PS4 1', 'NS1', 'iOS', 'Xbox1',
    'NS RPG', 'RC', 'PTB', 'DF', 'NS2', 'Beena', 'もばいる']] + [
    ('作品/PS Vita1亜洲中文版', 'PS Vita1亜', 'CS'),
    ('作品/北米版TDM', '米TDM', 'CS'),
    # 太鼓ミュージックパス（サブスク）。NS2 と DF で同じページを使い、2列目に「NS」とある曲は Switch 限定（DF には無い）
    ('作品/NS2/太鼓ミュージックパス', 'NS2MP', 'CS'),
    ('作品/NS2/太鼓ミュージックパス', 'DFMP', 'CS'),
]
# ジャンル別ページだけから集める作品（作品ページ本体の「今月の追加曲」などは数えない）
SUBS_ONLY = {'NS2MP', 'DFMP'}
# 行の2列目に「NS」（Switch 限定）とある曲を除く作品
EXCLUDE_NS = {'DFMP'}
# ジャンル別ページを他の作品と共有している作品（DF のバラエティ・クラシックは NS2 のページ）
SHARED_SUBS = {'作品/DF': '作品/NS2'}
# おに譜面が無い作品（AC1 は かんたん〜むずかしい だけ）。どの難易度のリンクでも曲名で拾う
ANY_DIFF = {'AC1'}
GENRES =['ポップス', 'キッズ', 'アニメ', 'ボーカロイド™曲', 'ゲームミュージック', 'バラエティ', 'クラシック', 'ナムコオリジナル', 'どうよう']


def fetch(page, force=False):
    p = os.path.join(CACHE, re.sub(r'[\\/:*?"<>| ]', '_', page) + '.html')
    if os.path.exists(p) and not force:
        return open(p, encoding='utf-8').read(), False
    url = 'https://wikiwiki.jp/taiko-fumen/' + urllib.parse.quote(page)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
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
            print('net error', e, flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 1200)
    open(p, 'w', encoding='utf-8').write(t)
    return t, True


def body(t):
    i = t.find('id="body"')
    j = t.find('運営からのお知らせ', i)
    return t[i:j] if i >= 0 else ''


def oni_links(b, exclude_ns=False, any_diff=False):
    """ページ内の「収録曲/おに/…」リンク。exclude_ns なら、2列目に「NS」とある行（Switch 限定の曲）を除く"""
    if exclude_ns:
        keep = []
        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', b, flags=re.S):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)
            if len(cells) >= 3 and 'NS' in re.sub(r'<[^>]+>', '', cells[1]):
                continue
            keep.append(row)
        b = '\n'.join(keep)
    diff = '(?:おに|むずかしい|ふつう|かんたん)' if any_diff else 'おに'
    return set(html.unescape(m) for m in re.findall(r'title="収録曲/' + diff + r'/([^"]+)"', b))


out = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
out['_meta'] = {'total': len(WORKS)}
# 自動更新用: REFRESH_WORKS に表示名をカンマ区切りで書くと、その作品は取り直す（今も曲が追加される作品向け）
REFRESH = set(x.strip() for x in os.environ.get('REFRESH_WORKS', '').split(',') if x.strip())
for order, (page, label, kind) in enumerate(WORKS):
    force = label in REFRESH
    if label in out and out[label].get('done') and not force:
        out[label]['order'] = order  # 作品を途中に足したときのために、並び順だけは毎回付け直す
        continue
    t, net = fetch(page, force)
    if net:
        time.sleep(DELAY)
    b = body(t)
    songs = set() if label in SUBS_ONLY else oni_links(b, label in EXCLUDE_NS, label in ANY_DIFF)
    # ジャンル別ページ
    subs = []
    prefixes = [page + '/'] + ([SHARED_SUBS[page] + '/'] if page in SHARED_SUBS else [])
    for m in re.findall(r'href="/taiko-fumen/([^"#?]+)"', b):
        name = urllib.parse.unquote(html.unescape(m))
        if any(name.startswith(p) and '/' not in name[len(p):] for p in prefixes) and name.split('/')[-1] in GENRES and name not in subs:
            subs.append(name)
    for sp in subs:
        st, net = fetch(sp, force)
        songs |= oni_links(body(st), label in EXCLUDE_NS, label in ANY_DIFF)
        if net:
            time.sleep(DELAY)
    out[label] = {'kind': kind, 'order': order, 'page': page, 'subs': len(subs), 'songs': sorted(songs), 'done': True}
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print(time.strftime('%H:%M:%S'), label, len(subs), 'subpages', len(songs), 'oni', flush=True)
    subprocess.run([sys.executable, '-I', os.path.join(HERE, 'build_data.py')])
print('done')
