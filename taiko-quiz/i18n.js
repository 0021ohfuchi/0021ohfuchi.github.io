// 日本語 / 英語の切り替え。英語のときは、画面に出る日本語の文言を辞書と決まった形（正規表現）で置き換える。
// 曲名・読み・入力した答えは置き換えない（英語の曲名の一覧が無いため）。
// 切り替えたらページを読み込み直す（日本語に戻すときに元の文言を覚えておかなくて済むように）。
(function(){
  const KEY = 'taikoQuiz.lang';
  let lang = 'ja';
  try{ lang = JSON.parse(localStorage.getItem(KEY)) || 'ja'; }catch(e){}
  // URL に ?lang=en / ?lang=ja が付いていればそちらを使い、覚えておく（英語版のリンクを人に送れるように）
  const q = (location.search.match(/[?&]lang=(ja|en)(?:&|$)/) || [])[1];
  if(q){ lang = q; try{ localStorage.setItem(KEY, JSON.stringify(q)); }catch(e){} }
  window.LANG = lang === 'en' ? 'en' : 'ja';
  window.setLang = l=>{ try{ localStorage.setItem(KEY, JSON.stringify(l)); }catch(e){}
    const u = new URL(location.href); u.searchParams.delete('lang'); location.replace(u.href); };

  const D = {
    // 見出し・共通
    '太鼓の達人 曲名当てクイズ': 'Taiko no Tatsujin Song Quiz',
    'トップへ': 'Home', 'あそびかた': 'How to play', '閉じる': 'Close',
    'すべて': 'All', 'クリア': 'Clear', '不明': 'Unknown', 'その他': 'Other',
    '日本語と英語を切り替え': 'Switch language (Japanese / English)',
    // 出題設定
    '出題設定': 'Quiz settings', '★の数': 'Stars', 'ジャンル': 'Genre', '収録作品': 'Included in', '問題数': 'Questions',
    'サウンド': 'Sound', '難易度': 'Difficulty', '難易度の違い': 'About difficulties',
    '選んだ作品のどれかに収録されている譜面から出題します。': 'Questions come from charts included in any of the selected games.',
    '5問': '5', '10問': '10', '20問': '20', '30問': '30', '50問': '50', '100問': '100',
    'かんたん': 'Easy', 'ふつう': 'Normal', 'むずかしい': 'Hard', 'おに': 'Extreme',
    '4つの中から正解の曲名を選ぶ。4択はランダム': 'Pick the right title from 4 choices. Choices are random',
    '4つの中から正解の曲名を選ぶ。4択は似た曲から': 'Pick the right title from 4 choices. Choices are similar songs',
    '曲名を入力して答える': 'Type the song title', '曲名を入力して答える。': 'Type the song title.',
    '曲名を入力して答える。1問3分の制限時間、曲の情報が隠される（3つまで開ける）': 'Type the song title. 3 minutes per question; song info is hidden (you can reveal up to 3)',
    'スタート！': 'Start!', '譜面検索': 'Chart search',
    '曲名・読み・作品名・アーティスト・作曲者・アニメ名などから譜面を探して、譜面・難易度・BPM・最大コンボ数・ジャンル・収録作品を見られます':
      'Find charts by title, reading, game, artist, composer, anime and more, and see the chart, stars, BPM, max combo, genre and games',
    'BGM': 'BGM', '効果音': 'Sound effects', '音源': 'Song audio',
    '設定画面・出題中に流れる曲': 'Music played on the settings and quiz screens',
    '正解・不正解の音': 'Sounds for correct / wrong answers',
    '正解・あきらめた後に、その曲を YouTube で流す': 'Play the song on YouTube after you answer or give up',
    '音源：YouTubeに公式音源がある場合、正解表示時にYouTubeが再生されます': 'Song audio: if an official audio is on YouTube, it plays when the answer is shown',
    '♪ 画面をタップするとBGMが流れます': '♪ Tap the screen to play BGM',
    // ジャンル
    'ポップス': 'Pop', 'キッズ': 'Kids', 'アニメ': 'Anime', 'ボーカロイド™曲': 'VOCALOID™ Music', 'ゲームミュージック': 'Game Music',
    'バラエティ': 'Variety', 'クラシック': 'Classical', 'ナムコオリジナル': 'NAMCO Original', 'どうよう': 'Nursery Rhymes',
    // 作品のまとまり・ハード
    '海外': 'Overseas', '海外の曲': 'Overseas songs', 'スマートフォン': 'Smartphone',
    'AC1～AC14（旧筐体）': 'AC1–AC14 (old cabinet)', 'AC15（新筐体）': 'AC15 (new cabinet)', 'AC16（ニジイロ）': 'AC16 (Nijiiro)', 'AC その他': 'AC other',
    '新筐体 無印': 'New cabinet (original)', 'ソライロ': 'Sorairo', 'モモイロ': 'Momoiro', 'キミドリ': 'Kimidori', 'ムラサキ': 'Murasaki',
    'ホワイト': 'White', 'レッド': 'Red', 'イエロー': 'Yellow', 'ブルー': 'Blue', 'グリーン': 'Green',
    '中国版限定': 'China only', 'AC12増量版': 'AC12 Extended', 'アニメ祭り': 'Anime Matsuri', 'アニメスペシャル': 'Anime Special', 'ブラジル版限定': 'Brazil only', 'もばいる': 'Mobile',
    '太鼓の達人 タタコンでドドンがドン': 'Taiko no Tatsujin: Tatacon de Dodon ga Don',
    '太鼓の達人 ドキッ！新曲だらけの春祭り': 'Taiko no Tatsujin: Doki! Shinkyoku Darake no Haru Matsuri',
    '太鼓の達人 あっぱれ三代目': 'Taiko no Tatsujin: Appare Sandaime',
    '太鼓の達人 あつまれ！祭りだ！！四代目': 'Taiko no Tatsujin: Atsumare! Matsuri da!! Yondaime',
    '太鼓の達人 ゴー！ゴー！五代目': 'Taiko no Tatsujin: Go! Go! Godaime',
    '太鼓の達人 わいわいハッピー！六代目': 'Taiko no Tatsujin: Waiwai Happy! Rokudaime',
    '太鼓の達人 ドカッ！と大盛り七代目': 'Taiko no Tatsujin: Doka! to Oomori Nanadaime',
    '太鼓の達人 アニメ祭り': 'Taiko no Tatsujin: Anime Matsuri',
    '太鼓の達人 とびっきり！アニメスペシャル': 'Taiko no Tatsujin: Tobikkiri! Anime Special',
    '太鼓の達人 TAIKO DRUM MASTER': 'Taiko: Drum Master',
    '太鼓の達人 ぽ〜たぶる': 'Taiko no Tatsujin Portable', '太鼓の達人 ぽ〜たぶる2': 'Taiko no Tatsujin Portable 2', '太鼓の達人 ぽ〜たぶるDX': 'Taiko no Tatsujin Portable DX',
    '太鼓の達人DS タッチでドコドン！': 'Taiko no Tatsujin DS: Touch de Dokodon!',
    '太鼓の達人DS 七つの島の大冒険': 'Taiko no Tatsujin DS: Nanatsu no Shima no Daibouken',
    '太鼓の達人DS ドロロン！ヨーカイ大決戦！！': 'Taiko no Tatsujin DS: Dororon! Yokai Daikessen!!',
    '太鼓の達人Wii': 'Taiko no Tatsujin Wii',
    '太鼓の達人Wii ドドーンと2代目！': 'Taiko no Tatsujin Wii: Dodoon to Nidaime!',
    '太鼓の達人Wii みんなでパーティ☆3代目！': 'Taiko no Tatsujin Wii: Minna de Party☆Sandaime!',
    '太鼓の達人Wii 決定版': 'Taiko no Tatsujin Wii: Ketteiban',
    '太鼓の達人Wii 超ごうか版': 'Taiko no Tatsujin Wii: Chou Goukaban',
    '太鼓の達人 ちびドラゴンと不思議なオーブ': 'Taiko no Tatsujin: Chibi Dragon to Fushigi na Orb',
    '太鼓の達人 どんとかつの時空大冒険': 'Taiko no Tatsujin: Don to Katsu no Jikuu Daibouken',
    '太鼓の達人 ドコドン！ミステリーアドベンチャー': 'Taiko no Tatsujin: Dokodon! Mystery Adventure',
    '太鼓の達人 Wii Uば〜じょん！': 'Taiko no Tatsujin: Wii U Version!',
    '太鼓の達人 特盛り！': 'Taiko no Tatsujin: Tokumori!',
    '太鼓の達人 あつめて★ともだち大作戦！': 'Taiko no Tatsujin: Atsumete★Tomodachi Daisakusen!',
    '太鼓の達人 Vバージョン': 'Taiko no Tatsujin: V Version',
    'アイドルマスター マストソングス 赤盤／青盤': 'THE IDOLM@STER MUST SONGS (Red / Blue)',
    '太鼓の達人 セッションでドドンがドン！': 'Taiko no Tatsujin: Drum Session!',
    '太鼓の達人 Nintendo Switchば〜じょん！': "Taiko no Tatsujin: Drum 'n' Fun!",
    '太鼓の達人 ドコどんRPGパック！': 'Taiko no Tatsujin: Rhythmic Adventure Pack',
    '太鼓の達人 ドンダフルフェスティバル（スイッチ版）': 'Taiko no Tatsujin: Rhythm Festival (Switch)',
    '太鼓の達人 ドンダフルフェスティバル': 'Taiko no Tatsujin: Rhythm Festival',
    '太鼓の達人 The Drum Master!': 'Taiko no Tatsujin: The Drum Master!',
    '太鼓の達人プラス': 'Taiko no Tatsujin Plus',
    '太鼓の達人 RHYTHM CONNECT': 'Taiko no Tatsujin: RHYTHM CONNECT',
    '太鼓の達人 Pop Tap Beat': 'Taiko no Tatsujin Pop Tap Beat',
    // 出題中
    '曲名を入力（Enterで回答）': 'Type the song title (Enter to answer)',
    '回答する': 'Answer', 'あきらめる': 'Give up', 'タップで表示': 'Tap to show', '開けません': 'No reveals left',
    'BPM': 'BPM', '最大コンボ数': 'Max combo', '初出年': 'Debut',
    '譜面を読み込み中…': 'Loading chart…', '正解！': 'Correct!', 'ざんねん…': 'Too bad…', '時間切れ…': "Time's up…",
    'Wikiで見る': 'View on Wiki', '結果を見る': 'See results', '次の問題へ': 'Next question', 'ここで終了': 'Finish here',
    // 結果
    '結果発表': 'Results', 'すべて（海外の曲を含む）': 'All (incl. overseas)', '問正解！': 'correct!', '称号': 'RANK', '1問あたり': 'Per question',
    '全問\n正解': 'PERFECT!', '達人級': 'MASTER', '名人級': 'EXPERT', '玄人級': 'SKILLED', '修行中': 'TRAINEE', '正解率': 'Accuracy', '合計時間': 'Total time', '正解': 'Correct', '不正解': 'Wrong', '時間切れ': "Time's up",
    '結果をシェア': 'Share your result',
    '結果をシェアするときの画像には、曲名が表示されません（20問まで表示）': 'Song titles are not shown in the shared result image (shown up to 20 questions)',
    '共有メニューで X を選んでください（結果の画像が添付されます）': 'Choose X in the share menu (the result image will be attached)', 'X（旧Twitter）でシェア': 'Share on X', 'Threads でシェア': 'Share on Threads',
    'Instagram でシェア': 'Share on Instagram', 'ほかのアプリでシェア': 'Share with another app',
    '同じ設定でもう一度': 'Play again', 'トップに戻る': 'Back to top',
    '結果の画像をコピーしました。投稿画面で貼り付け（Ctrl+V）してください': 'Result image copied. Paste it (Ctrl+V) into your post',
    '結果の画像を保存しました。投稿画面で画像を添付してください': 'Result image saved. Attach it to your post',
    '結果の画像を保存しました。Instagram で画像を選んでください': 'Result image saved. Select it in Instagram',
    // 確認
    'クイズを中断してトップに戻りますか？': 'Quit the quiz and go back to the top?',
    'あきらめて答えを見ますか？': 'Give up and see the answer?',
    'ここで終了して結果を見ますか？': 'Finish here and see the results?',
    // 譜面検索
    '曲名・読み・作品名・作曲者・アニメ名など（例: ゆうがお、AC14、コナン）': 'Title, reading, game, composer, anime… (e.g. AC14, Conan)',
    '作品': 'Game', '並び順': 'Sort', '名前順': 'Name', '★が多い順': 'Stars (high → low)', '★が少ない順': 'Stars (low → high)',
    'ジャンル順': 'Genre', '作品順': 'Game', '絞り込みと並び順を元に戻す': 'Reset filters and sort', 'リセット': 'Reset',
    '見つかりませんでした': 'No results', '曲の情報を読み込み中です…': 'Loading song info…',
    '検索結果の一覧に戻る（Esc）': 'Back to the results (Esc)', '← 検索結果に戻る': '← Back to results',
    '収録作品:': 'Included in:', '不明（取得中の可能性があります）': 'Unknown (may still be loading)', '収録作品不明': 'Unknown game',
    '（旧基準）': ' (old)',
    'この譜面のデータはまだ作成していないため（またはうまく読み取れなかったため）、譜面を表示できません。「Wikiで見る」から確認してください。':
      'This chart could not be shown (not created yet, or it could not be read). Please check it via "View on Wiki".',
    'この譜面はうまく読み取れませんでした。「Wikiで見る」から確認してください。': 'This chart could not be read. Please check it via "View on Wiki".',
    // 曲の再生
    'ドラッグで移動できます': 'Drag to move', '別の動画にする': 'Use another video', '別の動画': 'Other video', 'YouTubeで開く': 'Open on YouTube',
    '閉じる（この問題ではもう流しません）': 'Close (won’t play again for this question)', '曲の再生': 'Song player',
    'まもなく再生します…': 'Starting soon…',
    // あそびかた
    '出題設定で ★の数・ジャンル・収録作品・問題数・難易度を選び、「スタート！」を押します': 'Choose stars, genres, games, number of questions and difficulty in the settings, then press "Start!"',
    'おに譜面と、★の数・BPM・最大コンボ数・ジャンル・初出年・収録作品を手がかりに、どの曲か当てましょう': 'Guess the song from its Extreme (Oni) chart and hints: stars, BPM, max combo, genre, debut and games',
    'かんたん・ふつう: 4つの中から曲名を選ぶ（ふつうは似た曲が並びます）': 'Easy / Normal: pick the title from 4 choices (Normal shows similar songs)',
    'むずかしい: 曲名を入力して答える': 'Hard: type the song title',
    'おに: 曲名を入力。1問3分の制限時間があり、曲の情報が隠されています（タップで3つまで開けられます）': 'Extreme: type the title. 3 minutes per question, and the song info is hidden (tap to reveal up to 3)',
    '答えられるのは1問につき1回です。わからないときは「あきらめる」で答えを見られます': 'You get one answer per question. If you don’t know, press "Give up" to see the answer',
    '曲名の入力では、ひらがな・カタカナ、英字の大文字・小文字、記号の有無は区別しません。(裏譜面) などのカッコ書きは不要です。入力中は曲名の候補が出ます': 'When typing, hiragana/katakana, upper/lower case and symbols don’t matter, and you can leave out notes in brackets like (裏譜面). Suggestions appear as you type (titles are in Japanese)',
    '譜面は枠の中でスクロールでき、スマホでは2本指で拡大できます': 'Scroll the chart inside its frame; on phones you can pinch to zoom',
    '正解・あきらめた後は、YouTube に公式音源がある曲なら左下で流れます（「サウンド」で BGM・効果音・音源を切り替えられます）': 'After answering or giving up, the song plays at the bottom left if official audio is on YouTube (turn BGM, sound effects and song audio on/off in "Sound")',
    '最後に結果発表。マスを押すと問題ごとの答え・使ったヒント・回答時間が見られ、X・Threads・Instagram などでシェアできます': 'At the end you get your results. Tap a square to see the answer, hints used and time for that question, and share on X, Threads, Instagram and more',
    '「譜面検索」では、曲名・読み・作品名・アーティスト・作曲者・アニメ名などから譜面を探して、譜面・情報・収録作品を見られます': '"Chart search" lets you find charts by title, reading, game, artist, composer, anime and more, and see the chart, info and games',
    '難易度': 'Difficulty',
    'このコンテンツはファンメイドコンテンツです。ファンメイドコンテンツポリシー（': 'This is fan-made content, created under the Fan-Made Content Policy (',
    '）のもと制作されています。': ').',
    '曲データ・譜面の出典:': 'Song data and charts:',
    'バグ報告はこちら：X': 'Bug reports: X', '／ YouTube': '/ YouTube',
    '曲データ（data.js）を読み込めませんでした。そのため作品・譜面が表示されません。ダウンロードしたファイルを直接開くと読み込めないことがあります（特にスマホ）。公開ページ（GitHub Pages など）か、パソコンの start_server.bat から開いてください。':
      'Could not load the song data (data.js). Open the published page, or start_server.bat on a PC.',
  };
  // 決まった形の文言（数が入るもの）
  const fmtT = s=>s.replace(/(\d+)分(\d+)秒/g, '$1m $2s').replace(/([\d.]+)秒/g, '$1s');
  const R = [
    [/^正解 (\d+) \/ (\d+)$/, 'Correct $1 / $2'],
    [/^第(\d+)問 \/ (\d+)$/, 'Q$1 / $2'],
    [/^第(\d+)問$/, 'Q$1'],
    [/^問(\d+)$/, 'Q$1'],
    [/^残り (\d+:\d\d)$/, '$1 left'],
    [/^開ける情報 残り(\d+)$/, 'Reveals left: $1'],
    [/^出題候補: (\d+) 譜面$/, 'Charts in the pool: $1'],
    [/^(\d+) \/ (\d+) 問正解$/, '$1 / $2 correct'],
    [/^回答時間 (.+)$/, (m, t)=>'Time ' + fmtT(t)],
    [/^[\d.]+秒$|^\d+分\d+秒$/, m=>fmtT(m)],
    [/^初出 (.+)$/, (m, d)=>'Debut ' + d.replace(/年$/, '')],
    [/^(\d{4})年$/, '$1'],
    [/^約([\d.]+)(-.*)?$|^[\d.]+-約[\d.]+$/, m=>m.replace(/約/g, '~')],
    [/^♪ 再生中: (.+)$/, '♪ Now playing: $1'],
    [/^(\d+)作品・おに (\d+)譜面$/, '$1 games · Oni: $2 charts'],
    [/^(.*?)おに (\d+)譜面$/, (m, a, n)=>(a.trim() ? tr(a.trim()) + ' · ' : '') + 'Oni: ' + n + ' charts'],
    [/^ほか(\d+)作品$/, '+$1 more'],
    [/^(.+) ほか(\d+)作品$/, (m, a, n)=>tr(a) + ' +' + n + ' more'],
    [/^(\d+) 譜面$/, '$1 charts'],
    [/^ほか (\d+) 件（もっと詳しく入力ください）$/, '$1 more (type more to narrow down)'],
    [/^ほか (\d+) 件（さらに絞り込んでください）$/, '$1 more (narrow down further)'],
    [/^ほか (\d+) 件$/, '$1 more'],
    [/^(.+) ほか(\d+)$/, (m, a, n)=>tr(a) + ' +' + n],
    [/^作品「(.+)」の収録譜面: (\d+) 譜面$/, (m, w, n)=>'Charts in ' + w.split('」「').map(tr).join(', ') + ': ' + n],
    [/^アーティスト・作曲者・アニメ名などで見つかった譜面: (\d+) 譜面$/, 'Found by artist, composer, anime, etc.: $1 charts'],
    [/^曲名・読み・作品名・アーティスト・作曲者・アニメ名などを入力するか、★・ジャンル・作品で絞り込んでください（全 (\d+) 譜面）$/,
      'Type a title, reading, game, artist, composer, anime… or filter by stars, genre and game ($1 charts)'],
    [/^(表譜面|裏譜面|双打) (★×\d+)(（旧基準）)?$/, (m, a, b, c)=>({'表譜面':'Front','裏譜面':'Ura','双打':'Double'}[a]) + ' ' + b + (c ? ' (old)' : '')],
    [/^(★×\d+)（旧基準）$/, '$1 (old)'],
    [/^(.+)\(裏譜面\)$/, '$1 (Ura)'],
    [/^♪ (.+)（(自動生成音源|公式音源|動画)）$/, (m, n, k)=>'♪ ' + n + ' (' + ({'自動生成音源':'auto-generated audio','公式音源':'official audio','動画':'video'}[k]) + ')'],
    [/^結果の画像をコピーしました。(.+) で貼り付けてください$/, 'Result image copied. Paste it in $1'],
    [/^ニジイロ(\d{4})$/, 'Nijiiro $1'],
    [/^（作品ごとの収録曲を取得中です: (\d+)\/(\d+) 作品。まだ表示されていない作品は、取得が終わると追加されます）$/, '(Loading songs per game: $1/$2)'],
  ];
  const JP = /[぀-ヿ㐀-鿿]/;
  function tr(s){
    if(!s || !JP.test(s)) return s;
    const k = s.trim();
    if(Object.prototype.hasOwnProperty.call(D, k)) return s.replace(k, D[k]);
    for(const [re, rep] of R){ if(re.test(k)) return s.replace(k, k.replace(re, rep)); }
    // 「A ・ B ・ C」「A・B」は区切って 1 つずつ
    if(k.includes(' ・ ')) return s.replace(k, k.split(' ・ ').map(x=>tr(x)).join(' · '));
    if(k.includes('・')){ const parts = k.split('・'), out = parts.map(x=>tr(x)); if(out.some((x, i)=>x!==parts[i])) return s.replace(k, out.join(' · ')); }
    return s;
  }
  window.tr = s=>window.LANG==='en' ? tr(s) : s;
  if(window.LANG !== 'en') return;

  document.documentElement.lang = 'en';
  // 曲名・入力した答えなどは置き換えない
  const SKIP = '.choices, .sugg, .sd-head .title, .result-row .title, .sd-head .muted, .qdetail .t, .wrongs, .ans-name, input, textarea, script, style, #endDetail .t';
  const ATTRS = ['placeholder', 'title', 'aria-label', 'label'];
  function skip(el){ return el && el.closest && el.closest(SKIP); }
  function walk(root){
    if(root.nodeType === 3){ if(!skip(root.parentElement)){ const v = tr(root.nodeValue); if(v !== root.nodeValue) root.nodeValue = v; } return; }
    if(root.nodeType !== 1) return;
    if(skip(root) && !/^(INPUT|TEXTAREA)$/.test(root.tagName)) return; // 入力欄は案内文（placeholder）だけ置き換える
    for(const a of ATTRS){ const v = root.getAttribute(a); if(v && JP.test(v)){ const t = tr(v); if(t !== v) root.setAttribute(a, t); } }
    for(const c of root.childNodes) walk(c);
  }
  const mo = new MutationObserver(list=>{
    for(const m of list){
      if(m.type === 'childList') m.addedNodes.forEach(walk);
      else if(m.type === 'characterData') walk(m.target);
      else if(m.type === 'attributes') walk(m.target);
    }
  });
  mo.observe(document.documentElement, {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS});
  const t0 = document.title; document.title = tr(t0);
  const nativeConfirm = window.confirm.bind(window);
  window.confirm = m=>nativeConfirm(tr(m));
  document.addEventListener('DOMContentLoaded', ()=>walk(document.body));
})();
