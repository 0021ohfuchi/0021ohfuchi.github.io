# 譜面画像を一度だけダウンロードし、fumen-parse.js（ヘッドレス Chrome）で譜面データに変換して ../charts/<id>.js に保存する。
# クイズはこの譜面データを読み込むので、遊ぶ人のブラウザが Wiki の画像を直接読み込むことはない
# （WIKIWIKI の利用ルールで、他サイトからの画像の直接参照は禁止されているため）。
#
# 使い方: python parse_charts.py
#   MAX_IMG   : この回でダウンロードする画像の上限（既定: 無制限）
#   IMG_DELAY : 画像を1枚ダウンロードするごとに待つ秒数（既定: 3）
#   CHROME    : Chrome の実行ファイル（既定: 自動で探す）
import json, os, re, sys, time, hashlib, shutil, subprocess, urllib.request, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMG_DIR = os.path.join(HERE, 'cache', 'img')
OUT_DIR = os.path.join(ROOT, 'charts')
INDEX = os.path.join(HERE, 'charts_index.json')
UA = 'Mozilla/5.0 (personal taiko quiz builder)'
MAX_IMG = int(os.environ.get('MAX_IMG', '0')) or None
IMG_DELAY = float(os.environ.get('IMG_DELAY', '3'))
BATCH = 40
RETRY_FAILED = os.environ.get('RETRY_FAILED') == '1'
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)


def chart_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]


def find_chrome():
    c = os.environ.get('CHROME')
    if c:
        return c
    for p in [r'C:\Program Files\Google\Chrome\Application\chrome.exe',
              r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
              r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe']:
        if os.path.exists(p):
            return p
    for name in ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']:
        p = shutil.which(name)
        if p:
            return p
    sys.exit('Chrome が見つかりません。環境変数 CHROME で指定してください')


def download(url, path):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    wait = 30
    while True:
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            if e.code not in (429, 500, 502, 503, 504) or wait > 1200:
                raise
            print('429, wait', wait, flush=True)
            time.sleep(wait)
            wait *= 2
    open(path, 'wb').write(data)
    return True


def load_json(name, default):
    p = os.path.join(HERE, name)
    for _ in range(5):        # scrape_songs.py が書き込み中のことがあるので、少し待って読み直す
        try:
            return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default
        except (json.JSONDecodeError, OSError):
            time.sleep(2)
    return default


def save_index(index):
    tmp = INDEX + '.tmp'
    json.dump(index, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    os.replace(tmp, INDEX)


def build():
    subprocess.run([sys.executable, '-I', os.path.join(HERE, 'build_data.py')])


def find_jobs(index):
    lists = load_json('lists.json', [])
    details = load_json('details.json', {})
    # 譜面ページごとの、正しい最大コンボ数（読み取り結果の確認用）
    combos = {}
    for s in lists:
        for x in re.split(r'[・/()（）]', s['combo']):
            x = re.sub(r'\D', '', x)
            if x:
                combos.setdefault(s['href'], set()).add(x)
    jobs, seen = [], set()
    for href, d in details.items():
        if not d.get('imgs'):
            continue
        url = d['imgs'][0]
        cid = chart_id(url)
        # 読み取り済み（成功・失敗とも。画像が変わればIDも変わる）。RETRY_FAILED=1 なら、失敗したものは読み直す
        # （読み取り処理を直したとき用。画像はキャッシュにあるので Wiki にはアクセスしない）
        done = cid in index and (index[cid].get('ok') or not RETRY_FAILED or index[cid].get('reason') == '404')
        if done or cid in seen:
            continue
        seen.add(cid)
        jobs.append({'id': cid, 'url': url, 'combos': sorted(combos.get(href, []))})
    return jobs


def convert(batch, index, chrome, harness):
    """ヘッドレス Chrome で読み取り、charts/<id>.js を書く。成功数を返す"""
    jobs_js = 'window.CHART_JOBS=' + json.dumps(
        [{'id': j['id'], 'file': 'cache/img/' + j['id'] + '.png', 'combos': j['combos']} for j in batch]) + ';'
    open(os.path.join(HERE, 'cache', 'chart_jobs.js'), 'w', encoding='utf-8').write(jobs_js)
    args = [chrome, '--headless=new', '--disable-gpu', '--allow-file-access-from-files',
            '--virtual-time-budget=600000', '--dump-dom', harness]
    if sys.platform.startswith('linux'):
        args.insert(1, '--no-sandbox')
    r = subprocess.run(args, capture_output=True, timeout=900)
    out = r.stdout.decode('utf-8', 'replace')
    m = re.search(r'@@BEGIN@@(.*?)@@END@@', out, flags=re.S)
    if not m:
        print('!! harness failed', r.stderr.decode('utf-8', 'replace')[-500:], flush=True)
        return 0
    import html as _html
    n = 0
    for res in json.loads(_html.unescape(m.group(1))):
        if res.get('ok'):
            js = 'window.__chart&&window.__chart(%s,%s);\n' % (json.dumps(res['id']), json.dumps(res['chart'], separators=(',', ':')))
            open(os.path.join(OUT_DIR, res['id'] + '.js'), 'w', encoding='utf-8').write(js)
            index[res['id']] = {'ok': True, 'combo': res['combo']}
            n += 1
        else:
            index[res['id']] = {'ok': False, 'combo': res.get('combo'), 'reason': res.get('reason', 'combo mismatch')}
    return n


def run_once(chrome, harness, budget):
    """未変換の譜面を BATCH 枚ずつ「ダウンロード → 変換 → data.js 更新」する。ダウンロード枚数を返す"""
    index = load_json('charts_index.json', {})
    jobs = find_jobs(index)
    print('charts to parse', len(jobs), flush=True)
    downloaded = 0
    for b in range(0, len(jobs), BATCH):
        ready = []
        for j in jobs[b:b + BATCH]:
            p = os.path.join(IMG_DIR, j['id'] + '.png')
            if not os.path.exists(p):
                if budget is not None and downloaded >= budget:
                    continue
                ok = download(j['url'], p)
                downloaded += 1
                time.sleep(IMG_DELAY)
                if not ok:
                    index[j['id']] = {'ok': False, 'reason': '404'}
                    continue
            ready.append(j)
        if ready:
            n = convert(ready, index, chrome, harness)
            save_index(index)
            build()
            print(f'{time.strftime("%H:%M:%S")} parsed {min(b + BATCH, len(jobs))}/{len(jobs)}  ok {n}/{len(ready)}  '
                  f'total ok {sum(1 for v in index.values() if v.get("ok"))}', flush=True)
        if budget is not None and downloaded >= budget:
            break
    save_index(index)
    return downloaded


chrome = find_chrome()
harness = 'file:///' + os.path.join(HERE, 'chart_harness.html').replace('\\', '/').lstrip('/')
# WATCH=秒: 終わったあとも、その間隔で details.json を見直して新しい譜面を変換し続ける
# （scrape_songs.py と並べて動かす用。曲ページの取得が終わって新しい譜面が無くなったら止まる）
WATCH = int(os.environ.get('WATCH', '0'))
while True:
    run_once(chrome, harness, MAX_IMG)
    if not WATCH:
        break
    # details.json が30分以上更新されていなければ、曲ページの取得は止まったとみなして終わる
    if time.time() - os.path.getmtime(os.path.join(HERE, 'details.json')) > 1800:
        break
    time.sleep(WATCH)
print('done. charts ok', sum(1 for v in load_json('charts_index.json', {}).values() if v.get('ok')))
