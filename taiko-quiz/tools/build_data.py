# lists.json + details.json から ../data.js を生成する
# 使い方: python build_data.py  (tools フォルダで実行)
import json, os, re, hashlib, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
lists = json.load(open(os.path.join(HERE, 'lists.json'), encoding='utf-8'))
dp = os.path.join(HERE, 'details.json')
details = json.load(open(dp, encoding='utf-8')) if os.path.exists(dp) else {}
cp = os.path.join(HERE, 'charts_index.json')
charts_index = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else {}
IMG = 'https://cdn.wikiwiki.jp/to/w/taiko-fumen/'
SEC = {'新筐体収録曲': 0, '難易度・ジャンル別曲数': 0, '新筐体期間限定曲': 0, '新筐体ブラジル版限定曲': 0,
       '新筐体未収録曲': 1, '幻の曲': 2, '旧基準': 3}
# 表示するジャンル名の統一（旧基準の一覧の「J-POP」はポップスにまとめる）。海外の曲の判定には元のジャンル名を使う
# 海外版のジャンルも国内のジャンルにまとめる（ユーザー指定）
GENRE_FIX = {'ボーカロイド™曲': 'ボーカロイド™曲', 'J-POP': 'ポップス', 'Pop': 'ポップス',
             '綜合音樂': 'バラエティ', '華語流行音樂(Pinyin順)': 'バラエティ', '華語流行音樂': 'バラエティ',
             '卡通動畫音樂': 'アニメ', 'Anime/TV': 'アニメ', '日本流行音樂': 'ポップス', 'Músicas Brasileiras': 'ポップス',
             '儿童音乐': 'キッズ', 'Rock': 'バラエティ', '游戏音乐': 'ゲームミュージック'}
known = {'ポップス', 'キッズ', 'アニメ', 'ボーカロイド™曲', 'ゲームミュージック', 'バラエティ', 'クラシック',
         'ナムコオリジナル', 'どうよう'}

# 初出バージョン → 年 の対応表を、年が分かっている曲から作る（裏譜面ページは配信日表がないため）
def ver_keys(ver):
    v = re.sub(r'\(.*?\)|\*\d+', '', ver.split(' / ')[0]).strip()
    keys = [v]
    while re.search(r'[.\d]$', v) and '.' in v:
        v = v.rsplit('.', 1)[0]
        keys.append(v)
    return keys


import collections, statistics
vy = collections.defaultdict(list)
for d in details.values():
    if d.get('ver') and d.get('year'):
        for k in ver_keys(d['ver']):
            vy[k].append(d['year'])
VER_YEAR = {k: int(statistics.median_low(v)) for k, v in vy.items()}


def guess_year(ver):
    for k in ver_keys(ver):
        if k in VER_YEAR:
            return VER_YEAR[k]
    return None


# 初出（初出順/時系列順 ページから parse_debut.py で作成）
dbp = os.path.join(HERE, 'debut.json')
debut = json.load(open(dbp, encoding='utf-8')) if os.path.exists(dbp) else {}
ARCADE_WORKS = {'無印', 'ニジイロ', 'KATSU-DON', 'ソライロ', 'モモイロ', 'キミドリ', 'ムラサキ', 'ホワイト', 'レッド',
                'イエロー', 'ブルー', 'グリーン', 'AC12増'}  # アニメ祭り・アニメスペシャルは家庭用（CS）


def work_label(info):
    """作品名: アーケード初出ならバージョン名、家庭用初出なら機種名"""
    sec, work = info['sec'], info['work']
    sec = {'AC15': '新筐体 無印', 'ニジイロ Ver.': 'ニジイロ2020'}.get(sec, sec).replace(' ver.', '')
    if not work:  # 作品名が分からない（時期だけ分かる）
        return 'AC', sec
    if re.fullmatch(r'AC\d+', work) or work in ARCADE_WORKS:
        return 'AC', sec
    return 'CS', work


# 作品ごとの収録曲（scrape_works.py で作成）→ 譜面ページ名 → 作品番号の一覧
wp = os.path.join(HERE, 'works.json')
works_raw = json.load(open(wp, encoding='utf-8')) if os.path.exists(wp) else {}
WORKS_TOTAL = (works_raw.pop('_meta', None) or {}).get('total', 75)
WORKS_DONE = sum(1 for v in works_raw.values() if v.get('done'))  # 取得済みの作品数（下で作品をまとめ直す前に数える）
# 表示名の変更（取得のときの名前は scrape_works.py・update.py の ACTIVE_WORKS と合わせて元のまま）
for old, new in [('ニジイロ（現行）', 'ニジイロ2026')]:
    if old in works_raw:
        works_raw[new] = works_raw.pop(old)
# 作品の統合（ユーザー指定）: 米TDM は TDM に、太鼓ミュージックパスは本体（NS2・DF）にまとめる。
# NS2（Switch 版）と DF（PS5 などの版）は別の作品のまま
# ミュージックパスでしか遊べない曲は覚えておく（出題設定で「ミュージックパスを含める」を外したときに除くため）
MP_ONLY = {}
for src, dst in [('米TDM', 'TDM'), ('NS2MP', 'NS2'), ('DFMP', 'DF')]:
    if src in works_raw and dst in works_raw and src.endswith('MP'):
        MP_ONLY[dst] = set(works_raw[src]['songs']) - set(works_raw[dst]['songs'])
    if src in works_raw and dst in works_raw:
        works_raw[dst]['songs'] = sorted(set(works_raw[dst]['songs']) | set(works_raw.pop(src)['songs']))
# 新AC中国版（AC16中）は「ニジイロ（中国版限定）」として、中国版にしか無い曲だけを入れる（ユーザー指定。国内版と共通の曲は入れない）
CN_ONLY = ['拔蘿蔔', '捕魚歌', '兩隻老虎', '郷下老鼠', '小毛驢', '王老先生有塊地', '技神闇鬼', '技神闇鬼(裏譜面)', 'LUMINΔ']
if 'AC16中' in works_raw:
    cn = works_raw.pop('AC16中')
    cn['songs'] = [p for p in cn['songs'] if p in CN_ONLY]
    works_raw['中国版限定'] = cn
    # AC11亜・AC12亜・PS Vita1亜（亜洲版）にしか収録されていない曲も「中国版限定」に移す（ユーザー指定）
    ASIA = {'AC11亜', 'AC12亜', 'PS Vita1亜'}
    in_works = {}
    for name, v in works_raw.items():
        for p in v['songs']:
            in_works.setdefault(p, set()).add(name)
    move = sorted(p for p, ws in in_works.items() if ws and ws <= ASIA)
    for name in ASIA & set(works_raw):
        works_raw[name]['songs'] = [p for p in works_raw[name]['songs'] if p not in move]
    cn['songs'] = sorted(set(cn['songs']) | set(move))
    # 残った曲がすべてほかの作品でも遊べる亜洲版の作品は、選ぶ意味がないので作品ごと消す
    for name in sorted(ASIA & set(works_raw)):
        rest = works_raw[name]['songs']
        if all(in_works.get(p, set()) - ASIA for p in rest):
            del works_raw[name]
# 新ACブラジル版（WM）も「ブラジル版限定」として、ブラジル版にしか無い2曲だけを入れる（ユーザー指定）
BR_ONLY = ['Escatumbararibê', 'Hoje é Domingo']
if 'WM' in works_raw:
    br = works_raw.pop('WM')
    br['songs'] = [p for p in br['songs'] if p in BR_ONLY]
    works_raw['ブラジル版限定'] = br
# 家庭用（CS）の作品: ハードごとに、この順で並べる。画面には正式名称を出す（ユーザー指定）。
# アニメ祭り・アニメスペシャルは家庭用として扱う
CS_INFO = [  # (略称, 正式名称, ハード)
    ('CS1', '太鼓の達人 タタコンでドドンがドン', 'PS2'),
    ('CS2', '太鼓の達人 ドキッ！新曲だらけの春祭り', 'PS2'),
    ('CS3', '太鼓の達人 あっぱれ三代目', 'PS2'),
    ('CS4', '太鼓の達人 あつまれ！祭りだ！！四代目', 'PS2'),
    ('CS5', '太鼓の達人 ゴー！ゴー！五代目', 'PS2'),
    ('CS6', '太鼓の達人 わいわいハッピー！六代目', 'PS2'),
    ('CS7', '太鼓の達人 ドカッ！と大盛り七代目', 'PS2'),
    ('アニメ祭り', '太鼓の達人 アニメ祭り', 'PS2'),
    ('アニメスペシャル', '太鼓の達人 とびっきり！アニメスペシャル', 'PS2'),
    ('TDM', '太鼓の達人 TAIKO DRUM MASTER', 'PS2'),
    ('PSP1', '太鼓の達人 ぽ〜たぶる', 'PSP'),
    ('PSP2', '太鼓の達人 ぽ〜たぶる2', 'PSP'),
    ('PSPDX', '太鼓の達人 ぽ〜たぶるDX', 'PSP'),
    ('DS1', '太鼓の達人DS タッチでドコドン！', 'DS'),
    ('DS2', '太鼓の達人DS 七つの島の大冒険', 'DS'),
    ('DS3', '太鼓の達人DS ドロロン！ヨーカイ大決戦！！', 'DS'),
    ('Wii1', '太鼓の達人Wii', 'Wii'),
    ('Wii2', '太鼓の達人Wii ドドーンと2代目！', 'Wii'),
    ('Wii3', '太鼓の達人Wii みんなでパーティ☆3代目！', 'Wii'),
    ('Wii4', '太鼓の達人Wii 決定版', 'Wii'),
    ('Wii5', '太鼓の達人Wii 超ごうか版', 'Wii'),
    ('3DS1', '太鼓の達人 ちびドラゴンと不思議なオーブ', '3DS'),
    ('3DS2', '太鼓の達人 どんとかつの時空大冒険', '3DS'),
    ('3DS3', '太鼓の達人 ドコドン！ミステリーアドベンチャー', '3DS'),
    ('Wii U1', '太鼓の達人 Wii Uば〜じょん！', 'Wii U'),
    ('Wii U2', '太鼓の達人 特盛り！', 'Wii U'),
    ('Wii U3', '太鼓の達人 あつめて★ともだち大作戦！', 'Wii U'),
    ('PS Vita1', '太鼓の達人 Vバージョン', 'PS Vita'),
    ('PS Vita MS', 'アイドルマスター マストソングス 赤盤／青盤', 'PS Vita'),
    ('PS4 1', '太鼓の達人 セッションでドドンがドン！', 'PS4'),
    ('NS1', '太鼓の達人 Nintendo Switchば〜じょん！', 'Switch'),
    ('NS RPG', '太鼓の達人 ドコどんRPGパック！', 'Switch'),
    ('NS2', '太鼓の達人 ドンダフルフェスティバル（スイッチ版）', 'Switch'),
    # 複数のハードで出ている作品は、ハードを並べて書く（画面ではそれぞれのハードの中に出る）
    ('Xbox1', '太鼓の達人 The Drum Master!', ['Xbox One', 'Xbox Series X|S', 'Windows']),
    ('DF', '太鼓の達人 ドンダフルフェスティバル', ['PS5', 'Xbox Series X|S', 'Windows', 'Steam']),
    ('iOS', '太鼓の達人プラス', 'スマートフォン'),
    ('RC', '太鼓の達人 RHYTHM CONNECT', 'スマートフォン'),
    ('PTB', '太鼓の達人 Pop Tap Beat', 'スマートフォン'),
    ('Beena', 'Beena', 'その他'),
    ('もばいる', 'もばいる', 'その他'),
]
CS_ORDER = [c[0] for c in CS_INFO]
CS_LABEL = {c[0]: c[1] for c in CS_INFO}
CS_HW = {c[0]: (c[2] if isinstance(c[2], list) else [c[2]]) for c in CS_INFO}  # 作品 → ハードの一覧
for i, name in enumerate(CS_ORDER):
    if name in works_raw:
        works_raw[name]['kind'] = 'CS'
        works_raw[name]['order'] = 1000 + i
for name, v in works_raw.items():   # 一覧にない CS 作品は最後に
    if v['kind'] == 'CS' and name not in CS_ORDER:
        v['order'] = 2000 + v['order']
WORK_LIST = sorted(({'name': k, 'kind': v['kind'], 'order': v['order']} for k, v in works_raw.items()), key=lambda w: w['order'])
# 海外版でしか遊べない曲（北米版・アジア版・中国版・ブラジル版などの曲）は「海外の曲」という作品にまとめる
OVERSEAS_WORK = '海外の曲'
WORK_LIST.append({'name': OVERSEAS_WORK, 'kind': 'OS', 'order': 9999})
WORK_INDEX = {w['name']: i for i, w in enumerate(WORK_LIST)}
song_works = {}
for name, v in works_raw.items():
    for p in v['songs']:
        song_works.setdefault(p, set()).add(WORK_INDEX[name])

# 国内のジャンル名。国内のどの作品にも収録されていない曲のうち、ジャンル名がこれ以外のもの
# （Pop・Rock・華語流行音樂・綜合音樂・中国版の J-POP など）と、ブラジル版限定曲を海外の曲とみなす
# （「J-POP」は旧基準の一覧では国内の昔の曲にも使われているが、それらは国内の作品に収録されているので対象外になる）
JP_GENRES = {'ポップス', 'キッズ', 'アニメ', 'ボーカロイド™曲', 'ボーカロイド曲', 'ゲームミュージック', 'バラエティ',
             'クラシック', 'ナムコオリジナル', 'どうよう'}
OVERSEAS_SECTIONS = {'新筐体ブラジル版限定曲'}
# 旧基準の一覧にしか載っていない譜面（新基準の★が無い昔の曲）。旧基準でも出題する
NEW_STD_PAGES = set(s['page'] for s in lists if s['section'] != '旧基準')

# 曲を流す YouTube 動画（裏譜面ページに無ければ表譜面のものを使う）
# 流すのは曲だけの音源（0=自動生成音源, 1=公式音源/MV）のみ。オート動画・プレイ動画（2, 3）は使わない
fxp = os.path.join(HERE, 'chart_fixes.json')
CHART_FIXES = json.load(open(fxp, encoding='utf-8')) if os.path.exists(fxp) else {}
yt_by_page = {}
for s in lists:
    d = details.get(s['href'], {})
    vids = [v for v in d.get('yt', []) if v[0] <= 1]
    if vids:
        yt_by_page.setdefault(s['page'].split('/', 2)[-1], vids)

# 英語名とローマ字（英語表示と、英語名・ローマ字でも答えられるようにするため）
#   e : 公式の英語名（ナムコオリジナル曲。tools/en_names.json、scrape_en.py で取得）
#   ro: 曲名のローマ字（読みがあれば読みから、無ければ曲名から pykakasi で作る。読みの推定なので誤りもある）
#       複数あるときは「|」で区切る
_enp = os.path.join(HERE, 'en_names.json')
EN_NAMES = json.load(open(_enp, encoding='utf-8')) if os.path.exists(_enp) else {}
def _enkey(s):
    s = unicodedata.normalize('NFKC', s).lower()
    return re.sub(r'[\W_]', '', s)  # 記号・空白を除いて比べる
EN_BY_KEY = {}
for _jp, _en in EN_NAMES.items():
    EN_BY_KEY.setdefault(_enkey(_jp), _en)
try:
    import pykakasi
    _kks = pykakasi.kakasi()
except Exception:  # 入っていなければローマ字は作らない（前の data.js の値も使わない）
    _kks = None
_JP = re.compile('[぀-ヿ㐀-鿿]')
_fxp = os.path.join(HERE, 'romaji_fix.json')
ROMAJI_FIX = {k: v for k, v in (json.load(open(_fxp, encoding='utf-8')) if os.path.exists(_fxp) else {}).items() if not k.startswith('_')}
def _romaji(s):
    # 「･･･」「…」は読まない（pykakasi が前の読みを繰り返してしまう）。文の終わりや記号の前の小さい「っ」も読まない（さっ！→ sa!）
    s = re.sub(r'[･・]{2,}|…+', ' ', s)
    s = re.sub(r'[っッ](?=$|[^぀-ヿー])', '', s)
    s = s.replace('ドラえもん', 'ドラエモン')  # pykakasi が「ドラ えもん」と分けてしまう
    s = s.replace('％', '%')
    parts = []
    for x in _kks.convert(s):
        o = x['orig'].strip()
        if not o:
            continue
        if o == 'は':
            h = 'wa'   # 助詞の「は」「へ」（1 文字だけで切り出されたとき）
        elif o == 'へ':
            h = 'e'
        elif len(o) > 1 and o[0] == 'を' and _JP.search(o[1:]):
            h = 'wo ' + _kks.convert(o[1:])[0]['hepburn'] if len(_kks.convert(o[1:])) == 1 else 'wo ' + ''.join(y['hepburn'] for y in _kks.convert(o[1:]))
        elif re.fullmatch(r'[㐀-鿿]+の', o):
            h = ''.join(y['hepburn'] for y in _kks.convert(o[:-1])) + ' no'   # 「上の」→ ue no
        else:
            h = x['hepburn'] if _JP.search(o) else o
        if h.strip():
            parts.append(h.strip())
    t = ' '.join(parts)
    t = unicodedata.normalize('NFKC', t).replace('〜', '~')
    t = re.sub(r'\s+([!?,.、。~)\]）・])', r'\1', t)   # 記号の前の空白を詰める
    t = re.sub(r'([(\[（~])\s+', r'\1', t)
    t = t.replace('、', ', ').replace('。', '.').replace('・', ' ')
    t = re.sub(r'(\S)~(?=[A-Za-z])', r'\1 ~', t)  # 副題の始まりの ~ の前は空けて区切る
    return re.sub(r'\s+', ' ', t).strip()
def _canon(s):
    s = re.sub(r'[^a-z0-9]', '', s.lower())
    for a, b in (('shi', 'si'), ('chi', 'ti'), ('tsu', 'tu'), ('fu', 'hu'), ('ji', 'zi'), ('sh', 'sy'), ('ch', 'ty'), ('j', 'zy')):
        s = s.replace(a, b)
    s = re.sub(r'm(?=[bmp])', 'n', s).replace('ha', 'wa').replace('wo', 'o').replace('he', 'e')
    s = re.sub(r'([bdfghkmnprstvwyz])\1+', r'\1', s).replace('ou', 'o').replace('ei', 'e')
    return re.sub(r'([aiueo])\1+', r'\1', s)
def add_en(r):
    base = re.sub(r'\(裏譜面\)$', '', re.sub(r'^【双打】\s*', '', r['n'])).strip()
    plain = re.sub(r'[(（][^()（）]*[)）]', '', base).strip() or base
    en = EN_BY_KEY.get(_enkey(base)) or EN_BY_KEY.get(_enkey(plain))
    if not en:
        # 英語名の表では副題付きのことがある（例: 季曲 ～Seasons of Asia～）。曲名＋区切り（空白・～・-・(）で始まる行が 1 つだけならそれを使う
        cands = [e for j, e in EN_NAMES.items() if any(j.startswith(x) and len(j) > len(x) and j[len(x)] in ' 　～〜-‐(（「"' for x in {base, plain})]
        if len(set(cands)) == 1:
            en = cands[0]
    if en and _enkey(en) != _enkey(base):
        r['e'] = en
    if _kks and _JP.search(plain):
        ros = []
        y = re.sub(r'[(（][^()（）]*[)）]', '', r.get('y', '')).strip()
        # 読みに副題が付いていることがある（例: ほうかんのくげつ はしょう「なげきのひめ」）ので、最初の区切りまでも使う
        y0 = re.split(r'[\s「『～〜]', y)[0] if y else ''
        # 1 つ目は英語表示にも使う: 手直しの表 → 曲名から作ったもの（読みと同じなら単語の区切りがあるので見やすい）→ 読みから作ったもの
        t_ro = _romaji(plain)
        y_ros = [_romaji(x) for x in ([y] if y else []) + ([y0] if y0 and y0 != y else [])]
        first = ROMAJI_FIX.get(base) or ROMAJI_FIX.get(plain)
        if not first:
            first = t_ro if not y_ros or any(_canon(t_ro) == _canon(x) for x in y_ros) else y_ros[0]
            if base != plain and not ROMAJI_FIX.get(plain):
                first = _romaji(base)  # カッコ書き（例: (ウェディング編)）も英語表示に残す
        for ro in [first] + y_ros + [t_ro]:
            if ro and ro not in ros:
                ros.append(ro)
        if ros:
            r['ro'] = '|'.join(ros)
    elif _kks and _JP.search(base):
        # 英字の曲名にカッコ書きの日本語が付いている曲（例: Butterfly(倖田來未)）は、カッコの中もローマ字にして英語表示に使う
        r['ro'] = ROMAJI_FIX.get(base) or _romaji(base)

# シリーズもの（例: 「Seasons of Asia」シリーズ第4弾、Roseシリーズ第3弾）。曲ページの説明から取り出し、ふつうの 4 択で優先して出す
# 裏譜面・双打のページには書かれていないことが多いので、表のページ（カッコ書きを除いた名前）のシリーズも使う
_SERIES_RE = re.compile(r'(?:「([^」]+)」|([A-Za-z0-9ぁ-んァ-ヶー一-龯!！?？\-]{2,20}?))シリーズ(?:の)?第(\d+)弾')
_series_by_page = {}
for s in lists:
    for line in details.get(s['href'], {}).get('meta', []):
        m = _SERIES_RE.search(line)
        if m:
            _series_by_page[s['page'].split('/', 2)[-1]] = m.group(1) or m.group(2)
            break
def _page_base(pg):
    return re.sub(r'\(裏譜面\)$', '', re.sub(r'^【双打】\s*', '', pg)).strip()
def series_of(pg):
    return _series_by_page.get(pg) or _series_by_page.get(_page_base(pg))

out = []
for s in lists:
    d = details.get(s['href'], {})
    g = s['genre']
    r = {
        'n': s['name'],
        'p': s['page'].split('/', 2)[-1],
        'lv': s['level'],
        's': SEC.get(s['section'], 4),
        'g': GENRE_FIX.get(g, g),
        'bpm': s['bpm'],
        'c': s['combo'].replace('/', '・'),
    }
    fx = CHART_FIXES.get(r['p'])
    if fx and fx.get('combo'):
        r['c'] = str(fx['combo'])  # 一覧の最大コンボ数の誤りを手直し（chart_fixes.json）
    if s['section'] == '旧基準' and s['page'] not in NEW_STD_PAGES:
        r['o1'] = 1  # 旧基準にしか無い譜面（出題する）
    for k_src, k_dst in (('yomi', 'y'), ('ver', 'v'), ('year', 'yr'), ('density', 'd'), ('roll', 'r')):
        if d.get(k_src):
            r[k_dst] = d[k_src]
    db = debut.get(r['p'])  # 裏譜面は表と初出が違うことがあるので、表の情報では代用しない
    if db:
        if db.get('date'):
            r['yr'] = int(db['date'][:4])
            r['dt'] = db['date']
            r.pop('yg', None)
        kind, label = work_label(db)
        r['w'] = label
        r['wk'] = kind
    yt = yt_by_page.get(r['p']) or yt_by_page.get(re.sub(r'\(裏譜面\)$', '', r['p']))
    if yt:
        r['yt'] = [i for _, i in yt]
        r['ytk'] = yt[0][0]  # 0=自動生成音源 1=公式音源/MV
    wkey = r['p']
    if r['n'].startswith('【双打】'):
        # 双打譜面は裏譜面などでページ名が通常の譜面と同じになる。作品ごとの収録曲には「【双打】○○」の名前で載っているので、
        # その名前で引く（裏譜面は「【双打】○○」の収録作品で代用。載っていなければ通常の譜面の作品を使わず作品なし扱い）
        nk = lambda t: unicodedata.normalize('NFKC', t).replace(' ', '')  # Ⅱ と II などの表記ゆれを吸収
        sw_norm = {nk(k): k for k in song_works if k.startswith('【双打】')}
        wkey = next((sw_norm[nk(k)] for k in (r['n'], re.sub(r'\(裏譜面\)$', '', r['n'])) if nk(k) in sw_norm), None)
    if wkey in song_works:
        r['ws'] = sorted(song_works[wkey])
        mp = [WORK_INDEX[w] for w, ps in MP_ONLY.items() if wkey in ps and WORK_INDEX.get(w) in r['ws']]
        if mp:
            r['mp'] = mp  # この作品ではミュージックパスの曲
    elif s['section'] in OVERSEAS_SECTIONS or g not in JP_GENRES:
        r['ws'] = [WORK_INDEX[OVERSEAS_WORK]]         # 海外の曲
    elif r.get('w') in WORK_INDEX:
        r['ws'] = [WORK_INDEX[r['w']]]                 # 幻の曲など、作品ページに無い曲は初出の作品に入れる
    if 'yr' not in r and d.get('ver'):
        gy = guess_year(d['ver'])
        if gy:
            r['yr'] = gy
            r['yg'] = 1  # 推定値
    # 譜面データ（parse_charts.py で作成済みのもの）。画像の URL は data.js に入れない（直接参照しないため）
    if d.get('imgs'):
        k = int((fx or {}).get('img', 1)) - 1  # 使う譜面画像（chart_fixes.json の img。parse_charts.py と同じ）
        cid = hashlib.md5(d['imgs'][k if 0 <= k < len(d['imgs']) else 0].encode()).hexdigest()[:12]
        if charts_index.get(cid, {}).get('ok'):
            r['ch'] = cid
    if r.get('w') in CS_LABEL:
        r['w'] = CS_LABEL[r['w']]  # 初出作品も家庭用は正式名称で出す
    # 今の AC で複数のジャンルに入っている曲は、そのジャンルを全部（一覧のジャンルを先頭に）
    if d.get('genres'):
        gs = [r['g']] + [x for x in d['genres'] if x != r['g']]
        if len(gs) > 1:
            r['gs'] = gs
    sr = series_of(r['p'])
    if sr:
        r['sr'] = sr
    add_en(r)
    out.append(r)

js = '// 自動生成: tools/build_data.py\n// 出典: 太鼓の達人 譜面とか Wiki (https://wikiwiki.jp/taiko-fumen/)\n'
# 作品: name=画面に出す名前（CS は正式名称）、short=略称（検索で略称でも探せるように）、hw=ハード（CS をハードごとに分けて並べる）
js += 'window.QUIZ_WORKS=' + json.dumps([dict({'name': CS_LABEL.get(w['name'], w['name']), 'kind': w['kind']},
                                              **({'short': w['name'], 'hw': CS_HW.get(w['name'], ['その他'])} if w['kind'] == 'CS' else {}))
                                         for w in WORK_LIST], ensure_ascii=False) + ';\n'
js += 'window.QUIZ_WORKS_TOTAL=' + str(WORKS_TOTAL) + ';\n'
js += 'window.QUIZ_WORKS_DONE=' + str(WORKS_DONE) + ';\n'
js += 'window.QUIZ_DATA=' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\n'
open(os.path.join(HERE, '..', 'data.js'), 'w', encoding='utf-8').write(js)
# 曲検索用の曲の情報（アーティスト・作詞・作曲・主題歌など）。曲ページ名 → 文の一覧。出題には使わない
meta = {}
for s in lists:
    m = details.get(s['href'], {}).get('meta')
    if m:
        meta.setdefault(s['page'].split('/', 2)[-1], m)
open(os.path.join(HERE, '..', 'meta.js'), 'w', encoding='utf-8').write(
    '// 自動生成: tools/build_data.py（曲検索用の曲の情報）\n// 出典: 太鼓の達人 譜面とか Wiki (https://wikiwiki.jp/taiko-fumen/)\nwindow.QUIZ_META='
    + json.dumps(meta, ensure_ascii=False, separators=(',', ':')) + ';\n')
# 設定画面の BGM: taiko-quiz/BGM フォルダの mp3 の一覧（ブラウザはフォルダの中身を調べられないため）
ROOT = os.path.join(HERE, '..')
BGM_DIR = os.path.join(ROOT, 'BGM')
os.makedirs(BGM_DIR, exist_ok=True)
mp3s = sorted(f for f in os.listdir(BGM_DIR) if f.lower().endswith('.mp3') and os.path.isfile(os.path.join(BGM_DIR, f)))
open(os.path.join(ROOT, 'bgm.js'), 'w', encoding='utf-8').write(
    '// 自動生成: tools/build_data.py（BGM フォルダの mp3 の一覧。ファイル名のみ）\nwindow.QUIZ_BGM=' + json.dumps(mp3s, ensure_ascii=False) + ';\n')
print('songs', len(out), 'with charts', sum(1 for r in out if 'ch' in r), 'details', len(details))
