# ナムコオリジナル曲の公式英語名を取得して en_names.json（日本語の曲名 → 英語名）に保存する
# 出典: 太鼓の達人 wiki「収録曲/ナムコオリジナル/英語」（ユーザー指定のページ。NS2/DF・PTB・RC などの公式表記）
# 1 ページだけ取得する。取れなかったときは前回の en_names.json をそのまま使う。
import html, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'en_names.json')
URL = ('https://wikiwiki.jp/he8_hw2jo/%E5%8F%8E%E9%8C%B2%E6%9B%B2/%E3%83%8A%E3%83%A0%E3%82%B3%E3%82%AA%E3%83%AA'
       '%E3%82%B8%E3%83%8A%E3%83%AB/%E8%8B%B1%E8%AA%9E/%E3%83%86%E3%82%B9%E3%83%88')
UA = 'Mozilla/5.0 (personal taiko quiz builder)'


def cell_text(c):
    c = re.sub(r'<a [^>]*class="note_super[^"]*"[^>]*>.*?</a>', '', c, flags=re.S)
    c = re.sub(r'<br[^>]*>', ' ', c)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', c))).strip()


def parse(t):
    out = {}
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', t, flags=re.S):
        cells = [cell_text(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, flags=re.S)]
        if len(cells) < 2:
            continue
        jp, en = cells[0], cells[1]
        # 見出し行（曲名・五十音・アルファベット）や、英語名が不明・補足だけの行は使わない
        if not jp or not en or jp in ('曲名', '曲名(五十音順)') or len(jp) == 1 and len(en) == 1:
            continue
        if en.startswith('(') or '不明' in en or not re.search(r'[A-Za-z0-9]', en):
            continue
        out.setdefault(jp, en)
    return out


def main():
    try:
        with urllib.request.urlopen(urllib.request.Request(URL, headers={'User-Agent': UA}), timeout=60) as r:
            t = r.read().decode('utf-8')
    except Exception as e:
        print('en: fetch failed, keep previous', e)
        return
    names = parse(t)
    if len(names) < 100:  # ページの作りが変わったなど。前のデータを残す
        print('en: too few rows, keep previous', len(names))
        return
    json.dump(names, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=0, sort_keys=True)
    print('en names', len(names))


if __name__ == '__main__':
    main()
