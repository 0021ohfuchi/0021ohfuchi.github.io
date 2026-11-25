// オンライン対戦（部屋コードで友達と対戦）。Firebase Realtime Database に部屋の状態を置き、全員がその変化を受け取る。
// 送り合うのは「出題する譜面の番号・いま何問目か・各自の回答（正誤と時間）」だけで、譜面は各自が手元の charts を読む。
// index.html の後に読み込む（game・cfg・nextQ などは index.html のものをそのまま使う）。
(function(){
'use strict';

/* ▼ Firebase コンソール（プロジェクトの設定 → マイアプリ → ウェブアプリ）に出る firebaseConfig を、null の代わりに貼る。
     この値は公開してよいもの。安全はデータベースのルール（tools/firebase_rules.json）で守る。 */
const FIREBASE_CONFIG = {
  apiKey: 'AIzaSyD2LkLanGGF8AGDbzZHPpk4ljdpwJ1qxG8',
  authDomain: 'taiko-quiz.firebaseapp.com',
  databaseURL: 'https://taiko-quiz-default-rtdb.asia-southeast1.firebasedatabase.app',
  projectId: 'taiko-quiz',
  storageBucket: 'taiko-quiz.firebasestorage.app',
  messagingSenderId: '498823626147',
  appId: '1:498823626147:web:5dd04d91daf73acfb5ee16',
};

const SDK = 'https://www.gstatic.com/firebasejs/10.14.1/';
// 手元での動作確認用: http://localhost:8000/?mock=1 で開くと、Firebase の代わりにこのブラウザの中だけで部屋を作る（タブ同士で対戦できる）
const MOCK = /[?&]mock=1(&|$)/.test(location.search) && /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
const MAX_PLAYERS = 8, MAX_Q = 100;
const GRACE = 1500;            // 制限時間を過ぎてから答えを出すまでの猶予(ms)。通信の遅れで回答が届くのを待つ
const CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // 見間違えやすい I・O・0・1 は使わない
const LIMITS = [30, 60, 90, 120, 180];
// ランダムマッチ: 決まった出題設定（おに・★8〜10・全ジャンル・海外以外の全作品・10問・1問60秒）で対戦する。
// 曲の情報と譜面は、オンライン対戦ではいつも時間が経つと少しずつ表示される（index.html の autoReveal・chartFrac）
const PUB_COUNT = 10, PUB_WAIT = 10000, PUB_STALE = 10*60*1000, PUB_MERGE = 3000;
const PUB_CFG = ()=>({lv: [8, 9, 10], genre: GENRES.map(g=>g[0]), mp: true,
  worksOff: [...new Set(WORKS.filter(w=>w.kind === 'OS').map(wkey).concat(['海外の曲']))]});
const PUB_MODE = 'oni', pubLimit = ()=>60;

/* ---------- 通信（Firebase / 手元確認用） ---------- */
function fbNet(){
  let db = null, uid = null, offset = 0;
  const load = f=>new Promise((ok, ng)=>{ const s = document.createElement('script'); s.src = SDK + f; s.onload = ok; s.onerror = ()=>ng(new Error('load ' + f)); document.head.append(s); });
  return {
    async init(){
      if(db) return uid;
      if(!window.firebase){ await load('firebase-app-compat.js'); await Promise.all([load('firebase-auth-compat.js'), load('firebase-database-compat.js')]); }
      if(!firebase.apps.length) firebase.initializeApp(FIREBASE_CONFIG);
      uid = (await firebase.auth().signInAnonymously()).user.uid; // 名前の登録なしで、ブラウザごとの番号だけをもらう
      const d = firebase.database();
      d.ref('.info/serverTimeOffset').on('value', s=>{ offset = s.val() || 0; });
      db = d;
      return uid;
    },
    now: ()=>Date.now() + offset, // サーバーの時計（全員で同じ時刻を使う）
    TS: ()=>firebase.database.ServerValue.TIMESTAMP,
    get: p=>db.ref(p).get().then(s=>s.val()),
    set: (p, v)=>db.ref(p).set(v),
    update: (p, v)=>db.ref(p).update(v),
    on(p, cb){ const r = db.ref(p), f = r.on('value', s=>cb(s.val()), ()=>cb(null)); return ()=>r.off('value', f); },
    onConnect(cb){ const r = db.ref('.info/connected'), f = r.on('value', s=>{ if(s.val()) cb(); }); return ()=>r.off('value', f); },
    onDisc: (p, v)=>db.ref(p).onDisconnect().set(v),
    offDisc: p=>db.ref(p).onDisconnect().cancel(),
  };
}
function mockNet(){
  // 値は「パス → 値」の 1 件ずつ localStorage に置く（タブごとに書いた所だけを変えるので、ほかのタブの書き込みを消さない）
  const PRE = 'taikoQuiz.mdb:';
  const uid = (location.search.match(/[?&]uid=(\w+)/) || [])[1] || (sessionStorage.mockUid = sessionStorage.mockUid || 'u' + Math.random().toString(36).slice(2, 8));
  const subs = new Set(), disc = new Map();
  const read = ()=>{ const o = {};
    for(let i = 0; i < localStorage.length; i++){ const k = localStorage.key(i); if(k && k.startsWith(PRE)) put(o, k.slice(PRE.length), JSON.parse(localStorage.getItem(k))); }
    return o; };
  const at = (o, p)=>{ for(const k of p.split('/')){ if(o == null || typeof o !== 'object') return null; o = o[k]; } return o == null ? null : o; };
  const put = (o, p, v)=>{ const ks = p.split('/'), last = ks.pop(); let x = o; for(const k of ks){ if(x[k] == null || typeof x[k] !== 'object') x[k] = {}; x = x[k]; } if(v == null) delete x[last]; else x[last] = v; };
  const res = v=>v && typeof v === 'object' ? (v['.sv'] ? Date.now() : Array.isArray(v) ? v.map(res) : Object.fromEntries(Object.entries(v).filter(e=>e[1] != null).map(([k, x])=>[k, res(x)]))) : v;
  const store1 = (p, v)=>{
    const ks = []; for(let i = 0; i < localStorage.length; i++) ks.push(localStorage.key(i));
    for(const k of ks){ if(!k || !k.startsWith(PRE)) continue; const q = k.slice(PRE.length); if(q === p || q.startsWith(p + '/') || p.startsWith(q + '/')) localStorage.removeItem(k); }
    const walk = (q, x)=>{ if(x == null) return; if(typeof x === 'object' && !Array.isArray(x)){ for(const k in x) walk(q + '/' + k, x[k]); } else localStorage.setItem(PRE + q, JSON.stringify(x)); };
    walk(p, v);
  };
  const fire = ()=>{ const o = read(); [...subs].forEach(s=>{ if(subs.has(s)) s.cb(at(o, s.p)); }); };
  let pend = 0; const fireSoon = ()=>{ if(!pend) pend = setTimeout(()=>{ pend = 0; fire(); }, 0); };
  // 書き終えたら最後に版の番号を変える。ほかのタブはその通知で読み直す（書きかけの状態を読まないように）
  const bump = ()=>localStorage.setItem('taikoQuiz.mdbv', String(Math.random()));
  const write = fn=>{ fn(); bump(); fireSoon(); return Promise.resolve(); };
  addEventListener('storage', e=>{ if(!e.key || e.key === 'taikoQuiz.mdbv') fireSoon(); });
  addEventListener('pagehide', ()=>{ if(!disc.size) return; disc.forEach((v, p)=>store1(p, v)); bump(); });
  return {
    init: ()=>Promise.resolve(uid), now: ()=>Date.now(), TS: ()=>({'.sv': 'timestamp'}),
    get: p=>Promise.resolve(at(read(), p)),
    set: (p, v)=>write(()=>store1(p, res(v))),
    update: (p, v)=>write(()=>{ for(const k in v) store1(p + '/' + k, res(v[k])); }),
    on(p, cb){ const s = {p, cb}; subs.add(s); setTimeout(()=>{ if(subs.has(s)) cb(at(read(), p)); }, 0); return ()=>subs.delete(s); },
    onConnect(cb){ setTimeout(cb, 0); return ()=>{}; },
    onDisc: (p, v)=>{ disc.set(p, v); return Promise.resolve(); },
    offDisc: p=>{ disc.delete(p); return Promise.resolve(); },
  };
}

/* ---------- 状態 ---------- */
const ENABLED = !!FIREBASE_CONFIG || MOCK;
const net = MOCK ? mockNet() : fbNet();
let uid = null;
let code = null;      // 入っている部屋のコード（入っていなければ null）
let room = null;      // 部屋の最新の状態
let unsub = [];
let shownKey = '';    // いま画面に出している「回・問題番号・段階」
let rowHost = null;   // 答えの行を、ホスト用のボタン付きで描いたかどうか
let away = false;     // ホストがロビーから出題設定を変えに行っている間
let forcing = false;  // 答えが出た時点で未回答だった人を「時間切れ」にしている間（この回答は送らない）
let busy = false;
const O = window.ONL = {get code(){ return code; }, enabled: ENABLED};

const path = p=>'rooms/' + code + (p ? '/' + p : '');
const players = r=>(r && r.players) || {};
const onlineUids = r=>Object.keys(players(r)).filter(u=>players(r)[u].on).sort((a, b)=>(players(r)[a].joined - players(r)[b].joined) || (a < b ? -1 : 1));
const isHost = ()=>!!room && room.host === uid;
const ansOf = (r, qi)=>(r.ans && r.ans['q' + qi]) || {};
const limitMs = r=>(r.limit || 60) * 1000;
// 得点: 正解で 100 点 ＋ 早さのボーナス（すぐ答えるほど多く、制限時間いっぱいで 0。最大 100 点）
const pointOf = (a, lim)=>a && a.ok ? 100 + Math.round(100 * Math.max(0, 1 - (a.ms || 0) / lim)) : 0;
const BY_ID = new Map(DATA.map(r=>[r.ch, r]));
const nameHTML = n=>`<span class="onl-name">${esc(n || '？')}</span>`;

function msg(t){ $('onlMsg').textContent = t || ''; }
function fail(e){ console.error(e); msg('通信できませんでした。少し待ってからもう一度お試しください'); }
// 同じ部屋・同じ問題なら、全員に同じ 4 択が出るようにする乱数
function seeded(str){
  let h = 1779033703 ^ str.length;
  for(let i = 0; i < str.length; i++){ h = Math.imul(h ^ str.charCodeAt(i), 3432918353); h = h << 13 | h >>> 19; }
  let a = h >>> 0;
  return ()=>{ a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
O.rng = ()=>seeded(code + ':' + (room && room.round) + ':' + (game ? game.pos : 0));
O.elapsed = ()=>room && room.qt ? Math.max(0, net.now() - room.qt) : 0; // いまの問題が出てからの時間(ms)

/* ---------- 部屋を作る・入る・出る ---------- */
function getName(){
  const n = $('onlName').value.trim().slice(0, 12);
  if(!n){ msg('名前を入力してください'); $('onlName').focus(); return ''; }
  store.set('onlName', n);
  return n;
}
function uniquePool(){ // 同じ曲（表・裏など）は 1 回の対戦で 1 度だけ
  const seen = new Set(), list = [];
  for(const r of pool()){ const k = keyOf(baseName(r)); if(seen.has(k)) continue; seen.add(k); list.push(r); }
  return list;
}
// cfg の一部を一時的に差し替えて fn を呼ぶ（ランダムマッチの決まった出題設定で pool() や要約を作るため）
function withCfg(over, fn){ const keep = {}; for(const k in over){ keep[k] = cfg[k]; cfg[k] = over[k]; } try{ return fn(); }finally{ Object.assign(cfg, keep); } }
// 出題設定はホストのトップ画面のものを使う（ランダムマッチは決まった設定）。ロビーに出すために部屋にも書いておく
function pubSet(mode){ return withCfg(PUB_CFG(), ()=>({mode, count: PUB_COUNT, n: uniquePool().length, sum: settingsSummary()})); }
function hostSet(){
  if(room && room.pub) return pubSet(room.pub);
  return {mode: MODES[cfg.mode] ? cfg.mode : 'hard', count: Math.min(cfg.count || MAX_Q, MAX_Q), n: uniquePool().length, sum: settingsSummary()};
}
function hostPool(){ return room && room.pub ? withCfg(PUB_CFG(), uniquePool) : uniquePool(); }
function randCode(){ const a = new Uint32Array(6); crypto.getRandomValues(a); return [...a].map(x=>CODE_CHARS[x % CODE_CHARS.length]).join(''); }

// 部屋を作る。pub に難易度を渡すとランダムマッチの待ち部屋になる
async function makeRoom(name, pub){
  let c = '';
  for(let i = 0; i < 6; i++){ c = randCode(); if(await net.get('rooms/' + c + '/host') == null) break; c = ''; }
  if(!c) throw new Error('code');
  const lim = +store.get('onlLimit', 60);
  const r = {host: uid, created: net.TS(), state: 'lobby', round: 0, limit: pub ? pubLimit(pub) : LIMITS.includes(lim) ? lim : 60,
    set: pub ? pubSet(pub) : hostSet(), players: {[uid]: {name, joined: net.TS(), on: true}}};
  if(pub) r.pub = pub;
  await net.set('rooms/' + c, r);
  if(pub) await pubEntry(c, pub, 1, await net.get('rooms/' + c + '/created')); // 一覧の時刻は部屋を作った時刻と同じにする
  return c;
}
async function create(){
  if(busy) return; const name = getName(); if(!name) return;
  busy = true; msg('部屋を作っています…');
  try{ uid = await net.init(); enter(await makeRoom(name)); }catch(e){ fail(e); }
  busy = false;
}

/* ---------- ランダムマッチ ---------- */
// 待ち部屋の一覧（lobby/<難易度>/<部屋コード> = {n: 人数, t: 作った時刻}）。部屋を作った人（ホスト）だけが書く
const pubPath = (mode, c)=>'lobby/' + mode + '/' + c;
let pubReg = '';   // onDisconnect で消すように登録した一覧の場所
let pubN = -1;     // 一覧に書いた人数
async function pubEntry(c, mode, n, t){
  const p = pubPath(mode, c);
  await net.set(p, {n, t});
  if(pubReg !== p){ pubReg = p; net.onDisc(p, null); } // 回線が切れたら一覧から消す
  pubN = n;
}
function pubRemove(){
  if(!pubReg) return;
  const p = pubReg; pubReg = ''; pubN = -1;
  net.offDisc(p); net.set(p, null).catch(()=>{});
}
// 入れる待ち部屋を古い順に
async function pubFind(mode, except){
  const L = await net.get('lobby/' + mode) || {}, now = net.now();
  return Object.keys(L).filter(c=>c !== except && L[c] && L[c].n < MAX_PLAYERS && now - (L[c].t || 0) < PUB_STALE)
    .sort((a, b)=>(L[a].t - L[b].t) || (a < b ? -1 : 1)).map(c=>({c, t: L[c].t}));
}
async function pubJoin(c, name){
  const r = await net.get('rooms/' + c);
  if(!r || !r.pub || r.state !== 'lobby' || onlineUids(r).length >= MAX_PLAYERS) return false;
  await net.update('rooms/' + c + '/players/' + uid, {name, on: true, joined: net.TS()});
  enter(c);
  return true;
}
async function randomMatch(mode){
  if(busy) return; const name = getName(); if(!name) return;
  mode = PUB_MODE;
  busy = true; msg('対戦相手を探しています…');
  try{
    uid = await net.init();
    let ok = false;
    for(const x of (await pubFind(mode)).slice(0, 5)) if(ok = await pubJoin(x.c, name)) break;
    if(!ok) enter(await makeRoom(name, mode));
  }catch(e){ fail(e); }
  busy = false;
}
// 1人で待っているホストは、もっと前からある待ち部屋を見つけたらそちらに移る（同時に探し始めた2人が別々に待ち続けないように）
let mergeAt = 0, merging = false;
async function pubMerge(){
  if(merging || net.now() < mergeAt) return;
  mergeAt = net.now() + PUB_MERGE;
  const mode = room.pub, mine = code, t0 = room.created;
  merging = true;
  try{
    const older = (await pubFind(mode, mine)).filter(x=>x.t < t0 || (x.t === t0 && x.c < mine));
    if(!older.length || code !== mine || !room || room.state !== 'lobby' || onlineUids(room).length > 1) return;
    const name = (players(room)[uid] || {}).name || store.get('onlName', '');
    pubRemove();
    closeRoom();
    net.set('rooms/' + mine, null).catch(()=>{}); // 自分しかいない部屋は消す
    for(const x of older.slice(0, 5)) if(await pubJoin(x.c, name)) return;
    enter(await makeRoom(name, mode)); // 入れなかったら、また待ち部屋を作る
  }catch(e){ console.error(e); }
  finally{ merging = false; }
}
// ホストの仕事（ロビー）: 一覧の人数を合わせ、2人以上そろったら少し待って自動で始める
function pubHost(){
  const on = onlineUids(room).length;
  if(pubN !== on || !pubReg) pubEntry(code, room.pub, on, room.created).catch(()=>{});
  if(on < 2){ if(room.startAt) net.update(path(), {startAt: null}).catch(()=>{}); pubMerge(); return; }
  if(!room.startAt){ room.startAt = net.now() + PUB_WAIT; net.update(path(), {startAt: room.startAt}).catch(()=>{}); return; }
  if(on >= MAX_PLAYERS || net.now() >= room.startAt) start();
}
function pubWaitText(){
  if(!room || !room.pub || room.state !== 'lobby') return;
  const left = room.startAt ? Math.max(0, Math.ceil((room.startAt - net.now()) / 1000)) : -1;
  $('onlWaitHost').textContent = left >= 0 ? `まもなく開始します（${left}秒）` : '対戦相手を探しています…';
}
async function join(c){
  if(busy) return;
  c = String(c || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if(c.length !== 6){ msg('部屋コード（6文字）を入力してください'); $('onlCode').focus(); return; }
  const name = getName(); if(!name) return;
  busy = true; msg('部屋に入っています…');
  try{
    uid = await net.init();
    const r = await net.get('rooms/' + c);
    if(!r || !r.host){ msg('この部屋コードの部屋は見つかりませんでした'); busy = false; return; }
    const me = players(r)[uid];
    if(!me && onlineUids(r).length >= MAX_PLAYERS){ msg(`この部屋は満員です（最大${MAX_PLAYERS}人）`); busy = false; return; }
    await net.update('rooms/' + c + '/players/' + uid, me ? {name, on: true} : {name, on: true, joined: net.TS()});
    enter(c);
  }catch(e){ fail(e); }
  busy = false;
}
function setUrl(c){ try{ const u = new URL(location.href); if(c) u.searchParams.set('room', c); else u.searchParams.delete('room'); history.replaceState(null, '', u.href); }catch(e){} }
function enter(c){
  code = c; room = null; shownKey = ''; rowHost = null; away = false; msg('');
  setUrl(c); // 読み込み直しても同じ部屋に戻れるように、URL に部屋コードを付けておく
  const me = path('players/' + uid);
  unsub.push(net.on(path(), onRoom));
  // 回線が切れたら「いない」ことにし、つながり直したら戻す
  unsub.push(net.onConnect(()=>{ if(!code) return; net.onDisc(me + '/on', false); net.update(me, {on: true}).catch(()=>{}); }));
  unsub.push((t=>()=>clearInterval(t))(setInterval(hostCheck, 500)));
}
function closeRoom(){ // この画面側の後片付け（部屋そのものは残る）
  pubRemove();
  unsub.forEach(f=>f()); unsub = [];
  code = null; room = null; shownKey = ''; away = false;
  setUrl('');
  $('onlStrip').classList.add('hidden'); $('onlBanner').classList.add('hidden');
  if(game && game.online){ stopSong(); stopTimer(); game = null; $('hdrStat').textContent = ''; }
}
O.leave = function(){
  if(code){ const me = path('players/' + uid); net.offDisc(me + '/on'); net.update(me, {on: false}).catch(()=>{}); }
  closeRoom();
  renderSetup(); show('scSetup');
};

/* ---------- 部屋の変化を受け取る ---------- */
function onRoom(r){
  if(!code) return;
  if(!r || !r.host){ closeRoom(); renderSetup(); show('scSetup'); alert('部屋がなくなりました'); return; }
  room = r;
  // ホストがいなくなったら、残っている人のうち最初に入った人がホストを引き継ぐ
  const on = onlineUids(r);
  if(!(players(r)[r.host] || {}).on && on[0] === uid && r.host !== uid) net.set(path('host'), uid).catch(()=>{});
  if(r.state === 'lobby'){
    shownKey = '';
    if(game && game.online && !game.ended){ stopSong(); stopTimer(); game = null; $('hdrStat').textContent = ''; }
    $('onlStrip').classList.add('hidden');
    renderLobby();
    if(!away) showLobby();
  }else{
    away = false;
    if(r.state === 'play' && !(r.qi >= 0)) return; // 書きかけの状態は無視する
    if(!ensureGame(r)) return;
    if(r.state === 'play') syncPlay(r); else syncEnd(r);
  }
}
function showLobby(){
  $('onlEntry').classList.add('hidden'); $('onlLobby').classList.remove('hidden');
  if($('scOnline').classList.contains('hidden')) show('scOnline');
}
// この回の対戦の出題リストを、手元の曲データから組み立てる
function ensureGame(r){
  if(game && game.online && game.online.round === r.round) return true;
  const list = (r.list || []).map(id=>BY_ID.get(id));
  if(!list.length || list.some(x=>!x)){
    // ホストより手元の曲データが古い。読み込み直せば新しいデータになる（URL の部屋コードで同じ部屋に戻る）
    let n = 0; try{ n = +sessionStorage.getItem('taikoQuiz.onlReload') || 0; sessionStorage.setItem('taikoQuiz.onlReload', n + 1); }catch(e){}
    if(n < 2) location.reload(); else { O.leave(); alert('曲データが合わないため、この部屋に参加できませんでした。時間をおいてページを読み込み直してください'); }
    return false;
  }
  stopSong(); stopTimer();
  game = {list, pos: -1, target: list.length, all: false, history: [], ended: false, mode: MODES[r.mode] ? r.mode : 'hard', sum: r.sum || (r.set && r.set.sum) || [],
    online: {round: r.round, limit: limitMs(r)}};
  shownKey = '';
  return true;
}
// 途中から入った・読み込み直したときに、それまでの問題の結果を埋める（答えていない問題は不正解）
function syncHistory(n){
  const h = game.history; h.length = Math.min(h.length, n);
  while(h.length < n){ const a = ansOf(room, h.length)[uid]; h.push({r: game.list[h.length], ok: !!(a && a.ok), ms: a ? a.ms : game.online.limit, shown: [], timeout: !a || !!a.to}); }
}
function syncPlay(r){
  const key = r.round + ':' + r.qi + ':' + r.phase;
  if(key !== shownKey){
    const sameQ = shownKey === r.round + ':' + r.qi + ':q';
    shownKey = key;
    if(r.phase === 'q') showQ(r.qi);
    else { if(!sameQ) showQ(r.qi); reveal(r.qi); }
  }else if(r.phase === 'q') waitingRow();
  else if(rowHost !== isHost()) revealRow(r.qi); // 途中でホストを引き継いだら、進めるボタンを出す
  renderStrip();
  hostCheck();
}
function showQ(qi){
  $('onlStrip').classList.remove('hidden'); renderStrip(); // 譜面の高さを決める前に出しておく
  if($('scQuiz').classList.contains('hidden')) show('scQuiz');
  syncHistory(qi);
  game.pos = qi - 1;
  nextQ();
  const a = ansOf(room, qi)[uid];
  if(a){ // もう答えてある（読み込み直したとき）
    game.q.done = true; stopTimer();
    game.history.push({r: game.q.r, ok: !!a.ok, ms: a.ms, shown: [...game.q.shown], timeout: !!a.to});
    $('answerArea').classList.add('hidden'); updateStat(); waitingRow();
  }
}
// index.html の finishQ から呼ばれる: 自分の回答を送り、全員の回答（または時間切れ）を待つ
O.answered = function(ok, ngText){
  const q = game.q, qi = game.pos, h = game.history[game.history.length - 1];
  $('answerArea').classList.add('hidden');
  updateStat();
  if(!forcing && code && room && room.state === 'play' && room.qi === qi && !ansOf(room, qi)[uid]){
    const a = {ok: !!ok, ms: Math.round(h.ms)};
    if(ngText) a.to = true; // 時間切れ
    else if(!ok && q.lastAns) a.a = String(q.lastAns).slice(0, 60); // 間違えた答え（答えが出たときに全員に見せる）
    net.set(path('ans/q' + qi + '/' + uid), a).catch(()=>{});
  }
  if(!forcing) waitingRow();
};
function waitingRow(){
  if(!game || !game.q || !game.q.done || !room || room.phase !== 'q') return;
  const h = game.history[game.pos]; if(!h) return;
  const on = onlineUids(room), a = ansOf(room, room.qi), n = on.filter(u=>a[u] || u === uid).length;
  const ra = $('resultArea'); ra.classList.remove('hidden');
  ra.innerHTML = `<div class="result-row"><span class="mark ${h.ok ? 'ok' : 'ng'}" style="animation:none">${h.ok ? '正解！' : h.timeout ? '時間切れ…' : 'ざんねん…'}</span>` +
    `<span class="onl-wait"><span>ほかの人の回答を待っています…</span> <span>（${n}/${on.length}）</span></span></div>`;
}
// 答えを全員に出す
function reveal(qi){
  const q = game.q;
  if(!q.done){ forcing = true; try{ finishQ(false, '時間切れ…'); }finally{ forcing = false; } }
  playSong(q.r); revealInfo();
  $('answerArea').classList.add('hidden');
  revealRow(qi);
}
function revealRow(qi){
  const r = game.q.r, h = game.history[qi] || {}, host = rowHost = isHost(), last = qi >= game.list.length - 1;
  const pt = pointOf(ansOf(room, qi)[uid], limitMs(room));
  const ra = $('resultArea'); ra.classList.remove('hidden');
  ra.innerHTML = `<div class="result-row">
      <span class="mark ${h.ok ? 'ok' : 'ng'}">${h.ok ? '正解！' : h.timeout ? '時間切れ…' : 'ざんねん…'}</span>${h.ok ? `<span class="onl-pt">+${pt}点</span>` : ''}
      <span class="title">${esc(dispSong(r.n, r))}</span>
      <a href="${wikiUrl(r)}" target="_blank" rel="noopener">Wikiで見る</a>
      <span class="sp"></span>` +
      (host ? `<button class="primary" id="nextBtn">${last ? '結果を見る' : '次の問題へ'}</button>${last ? '' : '<button id="endNowBtn">ここで終了</button>'}`
            : '<span class="onl-wait">ホストが次へ進むのを待っています…</span>') + '</div>';
  if(!host) return;
  $('nextBtn').onclick = ()=>advance(qi, last);
  if(!last) $('endNowBtn').onclick = ()=>{ if(confirm('ここで対戦を終了して、全員で結果を見ますか？')) advance(qi, true); };
  setTimeout(()=>{ const b = $('nextBtn'); if(b) b.focus({preventScroll: true}); }, 30);
}
function advance(qi, end){
  if(!isHost() || room.state !== 'play' || room.qi !== qi || room.phase !== 'a') return;
  net.update(path(), end ? {state: 'end', n: qi + 1} : {qi: qi + 1, phase: 'q', qt: net.TS()}).catch(()=>{});
}
// ホストの仕事: 全員が答えたか、制限時間を過ぎたら、答えを出す段階に進める
function hostCheck(){
  if(code && room && room.pub && room.state === 'lobby'){ pubWaitText(); if(isHost()) pubHost(); return; }
  if(!code || !isHost() || room.state !== 'play' || room.phase !== 'q' || !room.qt) return;
  const on = onlineUids(room), a = ansOf(room, room.qi);
  if((on.length && on.every(u=>a[u])) || net.now() > room.qt + limitMs(room) + GRACE){
    const qi = room.qi; room.phase = 'a'; // 続けて何度も送らないよう、先に手元を進めておく
    net.update(path(), {phase: 'a'}).then(()=>{ if(room && room.qi === qi && shownKey.endsWith(':q')) onRoom(room); }).catch(()=>{});
  }
}
// 得点表: この回に答えた人と、いま部屋にいる人
function scores(r){
  const ps = players(r), lim = limitMs(r), m = {};
  for(const u in ps) if(ps[u].on) m[u] = {u, name: ps[u].name, on: true, score: 0, ok: 0};
  const upto = r.state === 'play' ? r.qi : (r.n || 0) - 1;
  for(let k = 0; k <= upto; k++){
    const a = ansOf(r, k);
    for(const u in a){ const e = m[u] = m[u] || {u, name: (ps[u] || {}).name, on: false, score: 0, ok: 0}; e.score += pointOf(a[u], lim); if(a[u].ok) e.ok++; }
  }
  const list = Object.values(m).sort((x, y)=>y.score - x.score || y.ok - x.ok || ((ps[x.u] || {}).joined || 0) - ((ps[y.u] || {}).joined || 0));
  list.forEach((e, i)=>{ e.rank = i && list[i-1].score === e.score ? list[i-1].rank : i + 1; });
  return list;
}
function renderStrip(){
  if(!room || room.state !== 'play') return;
  const a = ansOf(room, room.qi), lim = limitMs(room), shown = room.phase === 'a';
  $('onlStrip').innerHTML = scores(room).map(e=>{
    const x = a[e.u];
    const st = shown ? (x && x.ok ? `<span class="st ok">○ +${pointOf(x, lim)}</span>` : `<span class="st ng">×${x && x.a ? ` <span class="onl-ansx">${esc(x.a)}</span>` : ''}</span>`)
                     : (x ? '<span class="st done" title="回答済み">✔</span>' : '<span class="st think" title="考え中">…</span>');
    return `<span class="onl-chip${e.u === uid ? ' me' : ''}${e.on ? '' : ' off'}"><b class="rk">${e.rank}</b>${nameHTML(e.name)}<span class="sc">${e.score}</span>${st}</span>`;
  }).join('');
}
function syncEnd(r){
  if(game.ended && shownKey === r.round + ':end') return;
  shownKey = r.round + ':end';
  $('onlStrip').classList.add('hidden');
  if(game.q && !game.q.done){ forcing = true; try{ finishQ(false, '時間切れ…'); }finally{ forcing = false; } }
  syncHistory(r.n || 0);
  endGame();
}
// 結果画面（index.html の endGame から呼ばれる）: 順位表を出す
O.renderEnd = function(){
  if(!room) return;
  const list = scores(room), host = isHost();
  $('onlRank').innerHTML = list.map(e=>`<div class="onl-rrow${e.u === uid ? ' me' : ''}${e.rank === 1 ? ' top' : ''}"><b class="rk">${e.rank}</b>${nameHTML(e.name)}` +
    `<span class="ok"><span>正解</span> ${e.ok}</span><span class="sc">${e.score}<small>点</small></span></div>`).join('');
  // ランダムマッチは部屋に戻らず、それぞれが次の相手を探す
  $('onlAgain').classList.toggle('hidden', !host || !!room.pub);
  $('onlEndNote').classList.toggle('hidden', host || !!room.pub);
  $('onlRematch').classList.toggle('hidden', !room.pub);
};

/* ---------- ロビー ---------- */
function renderLobby(){
  const r = room, ps = players(r), on = onlineUids(r), host = isHost(), s = r.set || {};
  const pub = !!r.pub;
  $('onlCodeShow').textContent = code;
  $('onlCodeBox').classList.toggle('hidden', pub);
  $('onlLobbyTitle').textContent = pub ? 'ランダムマッチ' : '対戦ロビー';
  $('onlCount').textContent = `参加者（${on.length}/${MAX_PLAYERS}）`;
  $('onlPlayers').innerHTML = on.map(u=>`<span class="onl-chip${u === uid ? ' me' : ''}">${nameHTML(ps[u].name)}${u === r.host ? '<span class="tag">ホスト</span>' : ''}${u === uid ? '<span class="tag you">あなた</span>' : ''}</span>`).join('');
  const mode = MODES[s.mode] || MODES.hard;
  $('onlSet').innerHTML = `<span><i>難易度</i><b class="mode-tag ${mode.cls}">${mode.name}</b></span><span><i>問題数</i><span>${Math.min(s.count || 0, s.n || 0)}問</span></span>` +
    (host ? '' : `<span><i>制限時間</i><span>${r.limit}秒</span></span>`) +
    (s.sum || []).map(([k, v])=>`<span><i>${esc(k)}</i><span>${esc(v)}</span></span>`).join('');
  $('onlHost').classList.toggle('hidden', !host || pub);
  $('onlStart').classList.toggle('hidden', !host || pub);
  $('onlStart').disabled = !(s.n > 0);
  $('onlWaitHost').classList.toggle('hidden', host && !pub);
  if(pub) pubWaitText(); else $('onlWaitHost').textContent = 'ホストがスタートするのを待っています…';
  $('onlNoPool').classList.toggle('hidden', !host || s.n > 0);
  if(host) $('onlLimit').value = String(r.limit);
  // ホストを引き継いだときは、自分の出題設定を出しておく
  if(host && !away && JSON.stringify(s) !== JSON.stringify(hostSet())) net.update(path(), {set: hostSet()}).catch(()=>{});
}
function start(){
  if(!isHost() || room.state !== 'lobby') return;
  const s = hostSet(), list = shuffle(hostPool()).slice(0, s.count).map(r=>r.ch);
  if(room.pub) pubRemove(); // 始まったら待ち部屋の一覧から消す
  if(!list.length) return;
  net.update(path(), {state: 'play', round: (room.round || 0) + 1, list, mode: s.mode, sum: s.sum, set: s, qi: 0, phase: 'q', qt: net.TS(), ans: null, n: null, startAt: null}).catch(fail);
}

/* ---------- 画面 ---------- */
O.open = function(){
  if(code){ away = false; if(room && room.state === 'lobby'){ net.update(path(), {set: hostSet()}).catch(()=>{}); showLobby(); } return; }
  $('onlEntry').classList.remove('hidden'); $('onlLobby').classList.add('hidden');
  if(!$('onlName').value) $('onlName').value = store.get('onlName', '');
  msg('');
  show('scOnline');
};
// 画面が切り替わるたびに index.html の show から呼ばれる: 部屋に入ったまま設定・検索を見ているときは、上に帯を出す
O.onShow = function(id){
  const bar = !!code && (id === 'scSetup' || id === 'scSearch');
  $('onlBanner').classList.toggle('hidden', !bar);
  if(bar) $('onlBannerText').textContent = `部屋 ${code} に参加中`;
};
// 部屋に入っているときにトップへ戻ろうとした: 確認して部屋を出る（index.html の homeBtn から呼ばれる）
O.confirmLeave = function(){
  if(!confirm('部屋を出てトップに戻りますか？')) return false;
  O.leave(); return true;
};

$('onlBox').classList.toggle('hidden', !ENABLED);
$('onlBtn').onclick = O.open;
$('onlBack').onclick = ()=>{ renderSetup(); show('scSetup'); };
$('onlCreate').onclick = create;
$('onlRandom').onclick = ()=>randomMatch(PUB_MODE);
$('onlRematch').onclick = ()=>{ const m = room && room.pub; O.leave(); O.open(); randomMatch(m); };
$('onlJoin').onclick = ()=>join($('onlCode').value);
$('onlCode').addEventListener('keydown', e=>{ if(e.key === 'Enter' && !e.isComposing) join($('onlCode').value); });
$('onlCode').addEventListener('input', ()=>{ const v = $('onlCode').value.toUpperCase().replace(/[^A-Z0-9]/g, ''); if(v !== $('onlCode').value) $('onlCode').value = v; });
$('onlLeave').onclick = ()=>O.confirmLeave();
$('onlStart').onclick = start;
$('onlEdit').onclick = ()=>{ away = true; renderSetup(); show('scSetup'); };
$('onlBannerBack').onclick = O.open;
$('onlLimit').innerHTML = LIMITS.map(s=>`<option value="${s}">${s}秒</option>`).join('');
$('onlLimit').onchange = ()=>{ const v = +$('onlLimit').value; store.set('onlLimit', v); if(isHost() && room.state === 'lobby') net.update(path(), {limit: v}).catch(()=>{}); };
$('onlAgain').onclick = ()=>{ if(isHost() && room.state === 'end') net.update(path(), {state: 'lobby', set: hostSet()}).catch(()=>{}); };
$('onlCopy').onclick = async ()=>{
  const u = new URL(location.href); u.search = ''; u.hash = ''; u.searchParams.set('room', code);
  const b = $('onlCopy'), t = b.textContent;
  try{ await navigator.clipboard.writeText(u.href); b.textContent = 'コピーしました'; }catch(e){ prompt('このリンクを友達に送ってください', u.href); return; }
  setTimeout(()=>{ b.textContent = t; }, 1600);
};

// 招待リンク（?room=XXXXXX）で開いたとき: 名前を覚えていればそのまま入り、なければ名前を聞く
(function(){
  const c = ((location.search.match(/[?&]room=([A-Za-z0-9]{6})(&|$)/) || [])[1] || '').toUpperCase();
  if(!c || !ENABLED) return;
  O.open();
  $('onlCode').value = c;
  if($('onlName').value) join(c); else { msg('名前を入力して「参加する」を押してください'); $('onlName').focus(); }
})();
})();
