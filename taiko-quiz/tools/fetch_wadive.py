# WADIVE RECORD のオフボーカル音源（バンダイナムコ公式の配布ページ）から、まだ無い mp3 を taiko-quiz フォルダ直下に取り込む。
#   https://taiko-ch.net/wadiverecord/download/
# ページの各曲のリンクは <a href="files/songNN.mp3" download="曲名"> の形なので、
# 曲名（download 属性）＋ ".mp3" のファイル名が既に無ければダウンロードする。
# 既にあるファイルは上書きしない・消さない。取り込んだ mp3 は build_data.py が bgm.js に載せる（設定画面の BGM）。
#
# 失敗しても他の処理を止めないよう、例外は表示して終了コード 0 で返す。
import html, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
PAGE = 'https://taiko-ch.net/wadiverecord/download/'
UA = 'Mozilla/5.0 (compatible; taiko-quiz-updater)'
DELAY = float(os.environ.get('DELAY', '2'))
BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get('Content-Type', '')


def entries(page_html):
    # <a href="files/songNN.mp3" download="曲名">（属性の順番は前後しても拾えるように、タグごとに読む）
    out = []
    for tag in re.findall(r'<a\b[^>]*\bdownload="[^"]*"[^>]*>', page_html):
        href = re.search(r'href="([^"]+\.mp3)"', tag)
        name = re.search(r'download="([^"]+)"', tag)
        if href and name:
            out.append((href.group(1), html.unescape(name.group(1)).strip()))
    return out


def main():
    try:
        page, _ = get(PAGE)
    except Exception as e:
        print(f'!! ページを取得できませんでした: {e}', flush=True)
        return 0
    items = entries(page.decode('utf-8', errors='replace'))
    print(f'WADIVE RECORD: {len(items)} 曲', flush=True)
    added = 0
    for href, name in items:
        fname = BAD.sub('', name) + '.mp3'
        os.makedirs(os.path.join(ROOT, 'BGM'), exist_ok=True)
        dest = os.path.join(ROOT, 'BGM', fname)
        if os.path.exists(dest):
            continue
        url = PAGE + href
        try:
            data, ctype = get(url)
        except Exception as e:
            print(f'!! {fname}: ダウンロード失敗 {e}', flush=True)
            continue
        # HTML などが返ってきた場合は保存しない（mp3 は ID3 タグか frame sync で始まる）
        if 'audio' not in ctype and not (data[:3] == b'ID3' or data[:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf2')):
            print(f'!! {fname}: mp3 ではない内容（{ctype}）なので保存しません', flush=True)
            continue
        tmp = dest + '.part'
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, dest)
        added += 1
        print(f'追加: {fname}（{len(data) // 1024} KB）', flush=True)
        time.sleep(DELAY)
    print(f'追加 {added} 曲', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
