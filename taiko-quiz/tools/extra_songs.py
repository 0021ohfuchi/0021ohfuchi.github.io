# おに★の一覧ページに載っていないが、作品ページには載っている曲を、曲ページから直接取って lists.json に足す。
# 取得結果は extra_lists.json に保存し、次からは Wiki にアクセスせずに足し直す
# （scrape_lists.py が lists.json を作り直しても、update.py がこれを続けて実行するので消えない）。
# 曲ページの中身（譜面画像・読みなど）は、ふだんどおり scrape_songs.py が details.json に入れる。
#
# 使い方: python extra_songs.py      曲を足すときは EXTRA に曲ページ名（収録曲/おに/ より後ろ）を書く
import json, os, re, sys, time, html, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scrape_songs  # fetch() と text()（曲ページのキャッシュは scrape_songs.py と共通）

HERE = os.path.dirname(os.path.abspath(__file__))
LISTS = os.path.join(HERE, 'lists.json')
OUT = os.path.join(HERE, 'extra_lists.json')
DELAY = float(os.environ.get('DELAY', '20'))

GENRES = ['ポップス', 'キッズ', 'アニメ', 'ボーカロイド™曲', 'ゲームミュージック', 'バラエティ', 'クラシック', 'ナムコオリジナル', 'どうよう']
EXTRA = [
    'Timing ～タイミング～',
    'ガッチャマンの歌',
    'DiSCOVER THE FUTURE',
    'たのしい太鼓道場(裏譜面)',
    'ルパン三世',
]


def parse_entry(t, name):
    """曲ページの詳細表から、一覧と同じ形の項目（★・ジャンル・BPM・最大コンボ数）を作る"""
    i = t.find('id="body"')
    body = t[i:t.find('運営からのお知らせ', i)] if i >= 0 else ''
    m = re.search(r'<tbody>(.*?)</tbody>', body, flags=re.S)
    if not m:
        return None
    tb = m.group(1)
    cells = re.findall(r'<td[^>]*>(.*?)</td>', tb, flags=re.S)
    # ジャンル: ジャンル名だけのセル（「アニメ(メイン)」のようなカッコ書きは外す）。複数あれば最初のもの
    genre = None
    for c in cells:
        g = re.sub(r'[(（].*?[)）]', '', scrape_songs.text(c)).replace(' ', '')
        if g in GENRES:
            genre = g
            break
    lv = re.search(r'★×(\d+)', tb)
    if not (genre and lv):
        return None
    # 最大コンボ数: 最初の★のセルの次のセル（分岐譜面などで数が複数あれば最初の数）
    combo = ''
    for k, c in enumerate(cells):
        if '★×' in c and k + 1 < len(cells):
            nums = re.findall(r'\d+', scrape_songs.text(re.sub(r'<br[^>]*>', ' ', cells[k + 1])))
            combo = nums[0] if nums else ''
            break
    bpm = re.search(r'BPMは\s*約?\s*([0-9.]+(?:\s*[-～~]\s*[0-9.]+)?)', scrape_songs.text(body))
    page = '収録曲/おに/' + name
    return {
        'level': int(lv.group(1)),
        'section': '新筐体未収録曲',
        'genre': genre,
        'name': name,
        'href': '/taiko-fumen/' + urllib.parse.quote(page),
        'page': page,
        'bpm': re.sub(r'\s+', '', bpm.group(1)).replace('～', '-').replace('~', '-') if bpm else '',
        'combo': combo,
    }


extra = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
for name in EXTRA:
    if name in extra:
        continue
    href = '/taiko-fumen/' + urllib.parse.quote('収録曲/おに/' + name)
    t, net = scrape_songs.fetch(href)
    e = parse_entry(t, name)
    print(name, '->', e if e else '読み取れませんでした', flush=True)
    if e:
        extra[name] = e
    if net:
        time.sleep(DELAY)
json.dump(extra, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# lists.json に無いものだけ足す
lists = json.load(open(LISTS, encoding='utf-8'))
pages = set(s['page'] for s in lists)
add = [e for e in extra.values() if e['page'] not in pages]
if add:
    lists += add
    json.dump(lists, open(LISTS, 'w', encoding='utf-8'), ensure_ascii=False)
print('added to lists.json:', len(add))
