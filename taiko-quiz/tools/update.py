# 曲データの差分更新（GitHub Actions から毎日実行する。手元で実行してもよい）
#
#   1. おに★1〜10の一覧ページを取り直す（新曲・★・BPM・コンボ数の変更）。一覧に無い曲は extra_songs.py で足す
#   2. 初出ページ（AC16）を取り直す
#   3. 今も曲が追加される作品の収録曲を取り直す（未取得の作品があればそれも取る）
#   4. まだ取っていない曲ページ＋取得日が古い曲ページを、上限つきで取る
#   5. 新しい譜面画像をダウンロードして譜面データ（charts/）に変換する
#   6. data.js を作り直す
#
# Wiki は短時間に数回アクセスすると 429 を返すので、どの段階も約20秒に1ページのペースで取る。
# 途中で止まっても、各段階は進んだところまで保存してあり、次の実行で続きから再開する。
#
# 環境変数で調整できる:
#   MAX_FETCH      曲ページを取る上限（既定 150）
#   REFRESH_OLDEST 取り直す古い曲ページの数（既定 30）
#   ACTIVE_WORKS   取り直す作品の表示名（カンマ区切り）
#   SKIP           飛ばす段階（例: "works,debut"）
import json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = [sys.executable, '-I']
SKIP = set(x.strip() for x in os.environ.get('SKIP', '').split(',') if x.strip())
ACTIVE_WORKS = os.environ.get('ACTIVE_WORKS', 'ニジイロ（現行）,NS2,PTB,DF,NS2MP,DFMP')


def run(step, args, env=None):
    if step in SKIP:
        print(f'== {step}: skip', flush=True)
        return True
    print(f'== {step}', flush=True)
    e = dict(os.environ, PYTHONIOENCODING='utf-8', **(env or {}))
    r = subprocess.run(PY + args, cwd=HERE, env=e)
    if r.returncode != 0:
        print(f'!! {step} failed (code {r.returncode})', flush=True)
    return r.returncode == 0


def song_count(path):
    try:
        return len(json.load(open(path, encoding='utf-8')))
    except Exception:
        return 0


ok = True


def page_names():
    # 一覧と、一覧に載っていない曲の追加分に載っている曲名（「(裏譜面)」はまとめる）
    names = set()
    for f in ('lists.json', 'extra_lists.json'):
        try:
            for s in json.load(open(os.path.join(HERE, f), encoding='utf-8')):
                names.add(re.sub(r'\(裏譜面\)$', '', s['page'].split('/', 2)[-1]))
        except Exception:
            pass
    return names


names_before = page_names()

# 1. 一覧（取得に失敗して曲数が大きく減ったら、前の一覧に戻す）
lists = os.path.join(HERE, 'lists.json')
before = song_count(lists)
if os.path.exists(lists):
    shutil.copy(lists, lists + '.bak')
if run('lists', ['scrape_lists.py', os.path.join('cache', 'lists'), 'lists.json'], {'REFRESH': '1'}):
    after = song_count(lists)
    print(f'lists: {before} -> {after}', flush=True)
    if before and after < before * 0.9:
        print('!! 曲数が大きく減ったため、前の一覧に戻します', flush=True)
        shutil.copy(lists + '.bak', lists)
        ok = False
else:
    if os.path.exists(lists + '.bak'):
        shutil.copy(lists + '.bak', lists)
    ok = False
if os.path.exists(lists + '.bak'):
    os.remove(lists + '.bak')

# 1b. 一覧に載っていない曲（作品ページには載っている曲）を足す。取得済みのものは Wiki にアクセスしない
ok &= run('extra', ['extra_songs.py'])

# 2. 初出
ok &= run('debut', ['parse_debut.py'], {'REFRESH': '1'})

# 3. 作品ごとの収録曲
ok &= run('works', ['scrape_works.py'], {'REFRESH_WORKS': ACTIVE_WORKS})

# 4. 曲ページ
ok &= run('songs', ['scrape_songs.py', os.path.join('cache', 'songs'), 'lists.json', 'details.json'],
          {'MAX_FETCH': os.environ.get('MAX_FETCH', '150'), 'REFRESH_OLDEST': os.environ.get('REFRESH_OLDEST', '30')})

# 5. 譜面画像を譜面データ（charts/）に変換する（サイトは Wiki の画像を直接読み込まない）
ok &= run('charts', ['parse_charts.py'], {'MAX_IMG': os.environ.get('MAX_IMG', '300')})

# 6. ナムコオリジナル曲の公式英語名（1 ページだけ。取れなくても前回のものを使うので失敗扱いにしない）
run('en', ['scrape_en.py'])

# 7. data.js
ok &= run('build', ['build_data.py'])

# 8. 新しく増えた曲を、お知らせ（news.js）に足す（最初の実行など、元の一覧が空のときは足さない）
added = sorted(page_names() - names_before) if names_before else []
if added:
    news_js = os.path.join(HERE, '..', 'news.js')
    try:
        src = open(news_js, encoding='utf-8').read()
        head, body = src.split('window.QUIZ_NEWS=', 1)
        news = json.loads(body.rsplit(';', 1)[0])
        shown = '、'.join(added[:8]) + (f' ほか{len(added) - 8}曲' if len(added) > 8 else '')
        shown_en = ', '.join(added[:8]) + (f' and {len(added) - 8} more' if len(added) > 8 else '')
        news.insert(0, {'d': time.strftime('%Y/%m/%d', time.gmtime(time.time() + 9 * 3600)), 't': f'{len(added)}曲を追加しました: {shown}',
                        'en': f'Added {len(added)} song{"s" if len(added) != 1 else ""}: {shown_en}'})  # en: トップページの英語表示用
        open(news_js, 'w', encoding='utf-8', newline='\n').write(head + 'window.QUIZ_NEWS=' + json.dumps(news, ensure_ascii=False, indent=1) + ';\n')
        print('news: +', len(added), flush=True)
    except Exception as e:
        print('!! お知らせの更新に失敗', e, flush=True)

sys.exit(0 if ok else 1)
