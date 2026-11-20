# lists.json + details.json から ../data.js を生成する
# 使い方: python build_data.py  (tools フォルダで実行)
import json, os, re, hashlib

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
for old, new in [('ニジイロ（現行）', 'ニジイロ2026'), ('新筐体 無印', '無印')]:
    if old in works_raw:
        works_raw[new] = works_raw.pop(old)
# 作品の統合（ユーザー指定）: 米TDM は TDM に、太鼓ミュージックパスは本体（NS2・DF）にまとめる。
# NS2（Switch 版）と DF（PS5 などの版）は別の作品のまま
for src, dst in [('米TDM', 'TDM'), ('NS2MP', 'NS2'), ('DFMP', 'DF')]:
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
    ('CS1', '太鼓の達人 タタコンでドドンがドン', 'PlayStation 2'),
    ('CS2', '太鼓の達人 ドキッ！新曲だらけの春祭り', 'PlayStation 2'),
    ('CS3', '太鼓の達人 あっぱれ三代目', 'PlayStation 2'),
    ('CS4', '太鼓の達人 あつまれ！祭りだ！！四代目', 'PlayStation 2'),
    ('CS5', '太鼓の達人 ゴー！ゴー！五代目', 'PlayStation 2'),
    ('CS6', '太鼓の達人 わいわいハッピー！六代目', 'PlayStation 2'),
    ('CS7', '太鼓の達人 ドカッ！と大盛り七代目', 'PlayStation 2'),
    ('アニメ祭り', '太鼓の達人 アニメ祭り', 'PlayStation 2'),
    ('アニメスペシャル', '太鼓の達人 とびっきり！アニメスペシャル', 'PlayStation 2'),
    ('TDM', '太鼓の達人 TAIKO DRUM MASTER', 'PlayStation 2'),
    ('PSP1', '太鼓の達人 ぽ〜たぶる', 'PlayStation Portable'),
    ('PSP2', '太鼓の達人 ぽ〜たぶる2', 'PlayStation Portable'),
    ('PSPDX', '太鼓の達人 ぽ〜たぶるDX', 'PlayStation Portable'),
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
    ('PS Vita1', '太鼓の達人 Vバージョン', 'PlayStation Vita'),
    ('PS Vita MS', 'アイドルマスター マストソングス 赤盤／青盤', 'PlayStation Vita'),
    ('PS4 1', '太鼓の達人 セッションでドドンがドン！', 'PlayStation 4'),
    ('NS1', '太鼓の達人 Nintendo Switchば〜じょん！', 'Switch'),
    ('NS RPG', '太鼓の達人 ドコどんRPGパック！', 'Switch'),
    ('NS2', '太鼓の達人 ドンダフルフェスティバル', 'Switch'),
    # 複数のハードで出ている作品は、ハードを並べて書く（画面ではそれぞれのハードの中に出る）
    ('Xbox1', '太鼓の達人 The Drum Master!', ['Xbox One', 'Xbox Series X|S', 'Windows']),
    ('DF', '太鼓の達人 ドンダフルフェスティバル', ['PlayStation 5', 'Xbox Series X|S', 'Windows', 'Steam']),
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
    if r['p'] in song_works:
        r['ws'] = sorted(song_works[r['p']])
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
    elif r.get('w') == '新筐体 無印':
        r['w'] = '無印'
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
# 設定画面の BGM: taiko-quiz フォルダ直下の mp3 の一覧（ブラウザはフォルダの中身を調べられないため）
ROOT = os.path.join(HERE, '..')
mp3s = sorted(f for f in os.listdir(ROOT) if f.lower().endswith('.mp3') and os.path.isfile(os.path.join(ROOT, f)))
open(os.path.join(ROOT, 'bgm.js'), 'w', encoding='utf-8').write(
    '// 自動生成: tools/build_data.py（taiko-quiz フォルダ直下の mp3 の一覧）\nwindow.QUIZ_BGM=' + json.dumps(mp3s, ensure_ascii=False) + ';\n')
print('songs', len(out), 'with charts', sum(1 for r in out if 'ch' in r), 'details', len(details))
