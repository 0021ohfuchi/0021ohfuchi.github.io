// 譜面画像（太鼓の達人 譜面とか Wiki 形式）を読み取り、音符データに変換して自前で描き直す
// 画像の規則（幅816px）:
//   1段 = 上32pxのラベル領域（HS=赤 / BPM=青 / 小節番号=黒 の5px文字）+ レーン帯（黒2・白2・明灰2・レーン・明灰2・白2・黒2）
//   レーン: 灰(#808080)=普通 / 水色=玄人 / 赤(#9f6060)=達人。分岐中は複数のレーンが隙間なく縦に並ぶ
//   1拍 = 48px（4/4 の1小節 = 192px）。段の最初の小節線は x=23.5
//   小音符の外径18px、大音符24px（白い縁あり）。左の音符が上に重なる
(function (global) {
  'use strict';
  const PX_PER_BEAT = 48;

  // ラベル文字（5px高）の形 → 文字
  const GLYPHS = {
    '#..#/#..#/####/#..#/#..#': 'H', '.###/#.../.##./...#/###.': 'S',
    '###./#..#/###./#..#/###.': 'B', '###./#..#/###./#.../#...': 'P', '#...#/##.##/#.#.#/#...#/#...#': 'M',
    '####/#..#/#..#/#..#/####': '0', '.#./##./.#./.#./###': '1', '####/...#/####/#.../####': '2',
    '####/...#/.###/...#/####': '3', '..#./#.#./#.#./####/..#.': '4', '####/#.../####/...#/####': '5',
    '###./#.../####/#..#/####': '6', '####/#..#/...#/...#/...#': '7', '####/#..#/####/#..#/####': '8',
    '####/#..#/####/...#/.###': '9', '././././#': '.', '..../..../####/..../....': '-', '.../.../###/.../...': '-'
  };

  // 数字の一部が他の音符に隠れているとき用: 同じ大きさの数字の形と 2画素以内の差なら一番近いものを採用
  function fuzzyDigit(key) {
    let best = null, bestD = 99, second = 99;
    for (const [k, ch] of Object.entries(GLYPHS)) {
      if (!/\d/.test(ch) || k.length !== key.length) continue;
      let dd = 0;
      for (let i = 0; i < k.length; i++) if (k[i] !== key[i]) dd++;
      if (dd < bestD) { second = bestD; bestD = dd; best = ch; } else if (dd < second) second = dd;
    }
    return bestD <= 2 && bestD < second ? best : null;
  }

  function parseFumenImage(img, opt) {
    const dbg = opt && opt.debug ? { notes: [], bars: [], lanes: [] } : null;
    const W = img.naturalWidth || img.width, H = img.naturalHeight || img.height;
    const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
    const g = cv.getContext('2d', { willReadFrequently: true });
    g.drawImage(img, 0, 0);
    const d = g.getImageData(0, 0, W, H).data;
    const P = (x, y) => { const i = (y * W + x) * 4; return [d[i], d[i + 1], d[i + 2]]; };
    const same = (p, q, t) => Math.abs(p[0] - q[0]) <= t && Math.abs(p[1] - q[1]) <= t && Math.abs(p[2] - q[2]) <= t;
    const near = (p, v, t) => same(p, [v, v, v], t);
    const isRing = p => near(p, 176, 6);
    const isWhite = p => p[0] > 235 && p[1] > 235 && p[2] > 235;
    const isBg = p => near(p, 204, 3);
    const cls = p => {
      const [r, g2, b] = p;
      // 連打は (255,239,67)、風船は (255,191,67) くらい。緑の値で分ける
      if (r > 180 && g2 > 215 && r - b > 60) return 'y';             // 連打（黄）
      if (r > 180 && g2 > 120 && g2 <= 215 && b < 110) return 'o';  // 風船（橙）
      if (r > 180 && r - g2 > 90 && r - b > 90) return 'd';          // ドン
      if (b > 180 && b - r > 60) return 'k';                         // カッ
      return '';
    };
    const colorNear = (x, y, dir) => {
      for (let k = 1; k <= 4; k++) { const c = cls(P(x + dir * k, y)); if (c) return c; }
      return '';
    };
    const isDark = p => p[0] + p[1] + p[2] < 330;

    // 1) レーンを探す（x=5 の縦方向で、同じ色が 16〜24px 続く所）
    const X0 = 5;
    const lanes = [];
    for (let y = 0; y < H; y++) {
      const c = P(X0, y);
      let y2 = y; while (y2 + 1 < H && same(P(X0, y2 + 1), c, 2)) y2++;
      const h = y2 - y + 1;
      const sum = c[0] + c[1] + c[2];
      if (h >= 16 && h <= 24 && !isBg(c) && sum > 200 && sum < 520) { // ゴーゴーのピンクなど明るい色は除く
        const type = c[0] - c[2] > 20 ? 'm' : c[2] - c[0] > 20 ? 'e' : 'n';
        lanes.push({ top: y, bottom: y2, cy: Math.round((y + y2) / 2), color: c, type });
      }
      y = y2;
    }
    if (!lanes.length) return { ok: false, reason: 'レーンが見つかりません' };
    const groups = [];
    for (const ln of lanes) {
      const last = groups[groups.length - 1];
      if (last && ln.top - last[last.length - 1].bottom <= 2) last.push(ln);
      else groups.push([ln]);
    }
    const branched = groups.some(gr => gr.length > 1);

    // 1レーン分の音符を読む
    function scanLane(ln) {
      const y = ln.cy;
      const isLane = p => same(p, ln.color, 3);
      const rowNotes = [];
      const cand = [];
      for (let x = 3; x < W - 4; x++) {
        if (!isRing(P(x, y))) continue;
        if (isDark(P(x + 1, y))) {
          const c3 = colorNear(x, y, -1);
          if (c3) { const big = isWhite(P(x - 1, y)); cand.push({ x: x - (big ? 10.5 : 7.5), c: c3, big }); }
        }
        if (isDark(P(x - 1, y))) {
          const c3 = colorNear(x, y, 1);
          if (c3 === 'd' || c3 === 'k') { const big = isWhite(P(x + 1, y)); cand.push({ x: x + (big ? 10.5 : 7.5), c: c3, big }); }
        }
      }
      cand.sort((a, b) => a.x - b.x);
      for (const c of cand) {
        const isEnd = c.c === 'y' || c.c === 'o';
        if (rowNotes.some(n => Math.abs(n.x - c.x) <= 2 && (n.kind === 'end') === isEnd)) continue;
        rowNotes.push({ x: c.x, c: c.c, big: c.big, kind: isEnd ? 'end' : 'note' });
      }
      // 連打・風船の頭（左端の縁: 右隣が明るく、その先が黄/橙）
      for (let x = 1; x < W - 4; x++) {
        if (!isRing(P(x, y))) continue;
        const c3 = cls(P(x + 3, y));
        if (c3 !== 'y' && c3 !== 'o') continue;
        const left = cls(P(x - 1, y));
        if (left === 'y' || left === 'o') continue;
        const big = isWhite(P(x + 1, y));
        rowNotes.push({ x: x + (big ? 10.5 : 7.5), c: c3, big, kind: 'roll' });
      }
      // 黄・橙の帯（連打・風船の胴）を左から探し、頭が見つかっていない帯には頭を足す。帯の色で連打（黄）か風船（橙）かを決める。
      // 風船の頭は左に尻尾があって縁がなく、直前の音符に隠れることもあるので、縁ではなく帯と中の数字で見つける。
      // 段の左端から始まる帯は、頭の数字があれば段の初めにある風船、なければ前の段から続く連打・風船とみなす。
      // （数字や縁で数px途切れるのは許す。通常音符に当たったら帯は終わり）
      const runs = [];
      for (let x = 0, cur = null, gap = 0; x < W; x++) {
        const c = cls(P(x, y));
        if (c === 'y' || c === 'o') {
          if (!cur) { cur = { x0: x, x1: x, y: 0, o: 0 }; runs.push(cur); }
          cur.x1 = x; gap = 0; cur[c]++;
        } else if (cur && (c === 'd' || c === 'k' || ++gap > 4)) { cur = null; gap = 0; }
      }
      for (const rn of runs) {
        if (rn.x1 - rn.x0 < 10) continue; // 段の初めの黄色い線など
        const orange = rn.o > rn.y;
        const end = rowNotes.find(n => n.kind === 'end' && n.x >= rn.x0 && n.x <= rn.x1 + 12);
        if (end) end.c = orange ? 'o' : 'y';
        const head = rowNotes.find(n => n.kind === 'roll' && n.x >= rn.x0 - 14 && n.x <= rn.x0 + 24);
        if (head) { head.c = orange ? 'o' : 'y'; continue; }
        const num = orange ? readNumber(rn.x0, Math.min(rn.x1, rn.x0 + 40), y) : null;
        if (rn.x0 <= 26 && !num) continue; // 前の段から続く連打・風船
        // 音符が上に重なって帯が途切れただけの所に頭を足さないよう、風船は数字があるとき、
        // 連打は帯の終わりがあるか段の右端まで続くときだけ頭を足す
        if (orange ? !num : !(end || rn.x1 >= W - 30)) continue;
        // 風船は中の数字の位置を頭の中心にする（左側が他の音符に隠れていても位置がずれない）
        const hx = num ? num.cx : rn.x0 + (orange ? 11.5 : 9);
        rowNotes.push({ x: hx, c: orange ? 'o' : 'y', big: false, kind: 'roll', count: num ? num.value : undefined });
      }
      // 風船の連打数（頭の中の黒い数字）
      for (const n of rowNotes) {
        if (n.kind === 'roll' && n.c === 'o' && n.count == null) {
          // 縁が一部隠れていると頭の位置がずれるので、少し広く探して数字の中心を頭の位置にする
          const num = readNumber(Math.round(n.x - 14), Math.round(n.x + 8), y);
          if (num) { n.count = num.value; n.x = num.cx; }
        }
      }
      rowNotes.sort((a, b) => a.x - b.x);
      return rowNotes;
    }

    // x0..x1 の範囲で、y 付近にある黒い数字（5px の文字）を読む
    function readNumber(x0, x1, y) {
      const isBlk = p => p[0] < 42 && p[1] < 42 && p[2] < 42; // 数字はほぼ黒。音符の縁（#2e2e2e = 46）は含めない
      const rows = [];
      for (let yy = y - 6; yy <= y + 6; yy++) {
        let h = false; for (let x = x0; x <= x1 && !h; x++) if (isBlk(P(x, yy))) h = true;
        rows.push(h);
      }
      // 5行続く黒の帯を探す
      let ya = -1;
      for (let i = 0; i + 5 <= rows.length; i++) {
        if (rows.slice(i, i + 5).every(Boolean) && !rows[i - 1] && !rows[i + 5]) { ya = y - 6 + i; break; }
      }
      if (ya < 0) return null;
      let text = '', minX = Infinity, maxX = -Infinity;
      const col = xx => { for (let yy = ya; yy < ya + 5; yy++) if (isBlk(P(xx, yy))) return true; return false; };
      for (let x = x0; x <= x1; x++) {
        if (!col(x)) continue;
        let x2 = x; while (x2 + 1 <= x1 && col(x2 + 1)) x2++;
        let key = '';
        for (let yy = ya; yy < ya + 5; yy++) { for (let xx = x; xx <= x2; xx++) key += isBlk(P(xx, yy)) ? '#' : '.'; key += '/'; }
        const ch = GLYPHS[key.slice(0, -1)] || fuzzyDigit(key.slice(0, -1));
        if (!ch || !/\d/.test(ch)) return null;
        text += ch; minX = Math.min(minX, x); maxX = Math.max(maxX, x2);
        x = x2;
      }
      return text ? { value: +text, cx: (minX + maxX + 1) / 2 } : null;
    }

    // ラベル（BPM=青 / HS=赤）を読む
    function readLabels(lineY) {
      const out = [];
      const y0 = Math.max(0, lineY - 30), y1 = lineY - 7;
      for (const [kind, test] of [['bpm', p => p[2] > 180 && p[0] < 90 && p[1] < 90], ['hs', p => p[0] > 180 && p[1] < 90 && p[2] < 90]]) {
        // 色を含む行のまとまりを探す
        const hit = [];
        for (let y = y0; y <= y1; y++) { let h = false; for (let x = 0; x < W && !h; x++) if (test(P(x, y))) h = true; hit.push(h); }
        for (let i = 0; i < hit.length; i++) {
          if (!hit[i]) continue;
          let j = i; while (j + 1 < hit.length && hit[j + 1]) j++;
          const ya = y0 + i, yb = y0 + j;
          i = j;
          if (yb - ya + 1 !== 5) continue;
          // 文字に切り分け
          const glyphs = [];
          for (let x = 0; x < W; x++) {
            const col = xx => { for (let yy = ya; yy <= yb; yy++) if (test(P(xx, yy))) return true; return false; };
            if (!col(x)) continue;
            let x2 = x; while (x2 + 1 < W && col(x2 + 1)) x2++;
            let key = '';
            for (let yy = ya; yy <= yb; yy++) { for (let xx = x; xx <= x2; xx++) key += test(P(xx, yy)) ? '#' : '.'; key += '/'; }
            glyphs.push({ x, x2, ch: GLYPHS[key.slice(0, -1)] || '?' });
            x = x2;
          }
          // 「BPM」「HS」から始まる単位でラベルにまとめる
          let cur = null;
          for (let k = 0; k < glyphs.length; k++) {
            const gl = glyphs[k];
            const startsLabel = (gl.ch === 'B' && glyphs[k + 1] && glyphs[k + 1].ch === 'P') || (gl.ch === 'H' && glyphs[k + 1] && glyphs[k + 1].ch === 'S');
            if (startsLabel || !cur || gl.x - cur.x2 > 6) { cur = { x: gl.x, x2: gl.x2, text: '' }; out.push(Object.assign(cur, { kind })); }
            cur.text += gl.ch; cur.x2 = gl.x2;
          }
        }
      }
      return out.filter(l => !l.text.includes('?') && /^(BPM|HS)-?[\d.]+$/.test(l.text))
        .map(l => ({ kind: l.kind, x: l.x - 1.5, value: l.text.replace(/^(BPM|HS)/, '') }));
    }

    const rows = [];
    for (const gr of groups) {
      const lineY = gr[0].top - 6;  // 小節線の白が描かれる黒線
      // 2) 小節線
      const bars = [];
      if (lineY >= 0) {
        for (let x = 0; x < W; x++) {
          if (isWhite(P(x, lineY))) { bars.push(x + 0.5); while (x + 1 < W && isWhite(P(x + 1, lineY))) x++; }
        }
      }
      let laneEnd = W - 1;
      while (laneEnd > 0 && isBg(P(laneEnd, gr[0].top + 1))) laneEnd--;
      // 白い小節線がない段もあるので、小節番号の位置とレーン右端からも補う
      const snap = x => 23.5 + Math.round((x - 23.5) / 12) * 12;
      const addBar = x => { if (!bars.some(b => Math.abs(b - x) < 6)) bars.push(x); };
      const isBlack = p => p[0] < 40 && p[1] < 40 && p[2] < 40;
      const y1 = Math.max(0, lineY - 6), y2 = Math.max(0, lineY - 2);
      let clusterEnd = -99;
      for (let x = 0; x < W; x++) {
        let hit = false;
        for (let yy = y1; yy <= y2 && !hit; yy++) if (isBlack(P(x, yy))) hit = true;
        if (!hit) continue;
        if (x - clusterEnd > 6) addBar(snap(x - 2));
        clusterEnd = x;
      }
      if (laneEnd > 40) addBar(snap(laneEnd + 1 - 24));
      bars.sort((a, b) => a - b);
      // ゴーゴータイム（ラベル領域のピンク）
      const gogo = [];
      const gy = lineY - 1;
      if (gy > 0) {
        for (let x = 0; x <= laneEnd; x++) {
          const p = P(x, gy);
          if (!(p[0] > 240 && Math.abs(p[1] - 192) < 8 && Math.abs(p[2] - 192) < 8)) continue;
          let x2 = x; while (x2 + 1 <= laneEnd) { const q = P(x2 + 1, gy); if (q[0] > 240 && (Math.abs(q[1] - 192) < 8 || isWhite(q) || q[1] < 60)) x2++; else break; }
          gogo.push([x, x2 + 1]);
          x = x2;
        }
      }
      const ri = rows.length;
      const laneData = gr.map(l => ({ type: l.type, top: l.top, bottom: l.bottom, notes: scanLane(l).map(n => Object.assign(n, { row: ri })) }));
      rows.push({ lineY, top: gr[0].top, bottom: gr[gr.length - 1].bottom, bars, laneEnd, gogo, lanes: laneData, labels: lineY > 30 ? readLabels(lineY) : [] });
      if (dbg) {
        dbg.lanes.push(...gr);
        bars.forEach(b => dbg.bars.push({ x: b, y: gr[0].top }));
      }
    }

    // 達人譜面のレーン: 赤いレーン（なければ音符が一番多いレーン）
    const masterLane = r => r.lanes.find(l => l.type === 'm') ||
      r.lanes.reduce((a, b) => (b.notes.filter(n => n.kind === 'note').length > a.notes.filter(n => n.kind === 'note').length ? b : a));
    let notes = [];
    for (const r of rows) notes = notes.concat(masterLane(r).notes);
    if (dbg) for (const r of rows) for (const l of r.lanes) for (const n of l.notes) dbg.notes.push({ x: n.x, y: Math.round((l.top + l.bottom) / 2), kind: n.kind });

    // 4) 小節と拍に変換
    const measures = [];
    rows.forEach((r, ri) => {
      for (let i = 0; i + 1 < r.bars.length; i++) {
        const x0 = r.bars[i], x1 = r.bars[i + 1];
        measures.push({ row: ri, x0, x1, beats: Math.round((x1 - x0) / PX_PER_BEAT * 48) / 48 });
      }
    });
    if (!measures.length) return { ok: false, reason: '小節線が見つかりません' };
    let acc = 0;
    for (const m of measures) { m.start = acc; acc += m.beats; }
    const findMeasure = (row, x) => {
      let best = null;
      for (const m of measures) {
        if (m.row !== row) continue;
        if (x >= m.x0 - 6 && x < m.x1 - 6) return m;
        if (!best || Math.abs(x - m.x0) < Math.abs(x - best.x0)) best = m;
      }
      return best;
    };
    const beatOf = (row, x) => { const m = findMeasure(row, x); return m ? m.start + Math.round((x - m.x0) / PX_PER_BEAT * 48) / 48 : null; };
    const events = [];
    for (const n of notes) {
      const b = beatOf(n.row, n.x);
      if (b !== null) events.push({ beat: b, kind: n.kind, c: n.c, big: n.big, count: n.count });
    }
    events.sort((a, b) => a.beat - b.beat || (a.kind === 'end') - (b.kind === 'end'));
    const out = [];
    let open = null;
    for (const e of events) {
      if (e.kind === 'roll') { open = { beat: e.beat, type: e.c === 'o' ? 'balloon' : (e.big ? 'ROLL' : 'roll'), end: null }; if (e.count) open.count = e.count; out.push(open); }
      else if (e.kind === 'end') { if (open && open.end == null) { open.end = e.beat; open = null; } }
      else out.push({ beat: e.beat, type: (e.c === 'd' ? 'don' : 'ka') + (e.big ? 'B' : '') });
    }
    for (const o of out) if (o.end === null) o.end = o.beat + 1;
    // BPM・HS の変化（拍の位置つき）
    const changes = [];
    rows.forEach((r, ri) => r.labels.forEach(l => { const b = beatOf(ri, l.x); if (b !== null) changes.push({ beat: b, kind: l.kind, value: l.value }); }));
    changes.sort((a, b) => a.beat - b.beat);
    const combo = out.filter(o => /^(don|ka)/.test(o.type)).length;
    // レーンの種類ごとの音符数（普通=灰 / 玄人=青 / 達人=赤）。その種類のレーンが無い段は灰色（無ければ最初）のレーンで数える。
    // 分岐譜面のほか、「玄人のレーン＝2P 用譜面」のように別譜面を並べた画像でも、灰色のレーンだけの数で確認できるようにする
    const laneOf = (r, t) => r.lanes.find(l => l.type === t) || r.lanes.find(l => l.type === 'n') || r.lanes[0];
    const combos = [...new Set(['n', 'e', 'm'].map(t => rows.reduce((a, r, ri) =>
      a + laneOf(r, t).notes.filter(n => n.kind === 'note' && beatOf(ri, n.x) !== null).length, 0)).concat([combo]))];
    return {
      ok: true, width: W, rows, measures: measures.map(m => ({ start: m.start, beats: m.beats })),
      notes: out, changes, combo, combos, totalBeats: acc, branched, debug: dbg
    };
  }

  function loadFumen(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => { try { resolve(parseFumenImage(img)); } catch (e) { reject(e); } };
      img.onerror = () => reject(new Error('画像を読み込めません'));
      img.src = url;
    });
  }

  // ---------- 描画 ----------
  // 元画像と同じ配置・大きさの関係で、自前のデザインで描く（画像の座標をそのまま縮小して使う）
  const LANE_COLORS = { n: '#8c8c8c', e: '#5fa6c4', m: '#c0716b' };
  // opt.maxW / opt.maxH: 表示できる幅と高さ（CSS px）。譜面全体がこの中に収まるよう、
  // 段を 1〜4 列に段組みして一番大きく表示できる配置と倍率を選ぶ
  function renderFumen(canvas, fumen, opt) {
    opt = opt || {};
    const dpr = window.devicePixelRatio || 1;
    const rows = fumen.rows;
    const W = fumen.width, GAP = 28;
    const blocks = rows.map(r => ({ r, y0: r.lineY - 34, h: r.bottom + 10 - (r.lineY - 34) }));
    const maxW = opt.maxW || canvas.parentElement.clientWidth || W;
    const maxH = opt.maxH || Infinity;
    // 列への割り振り（上から順に、各列の高さがなるべくそろうように）
    const split = c => {
      const total = blocks.reduce((a, b) => a + b.h, 0);
      const cols = [[]]; let hcur = 0;
      for (const b of blocks) {
        if (hcur > 0 && hcur + b.h / 2 > total / c * cols.length && cols.length < c) { cols.push([]); }
        cols[cols.length - 1].push(b);
        hcur += b.h;
      }
      return cols;
    };
    // opt.cols: 列数を固定する（スマホの縦画面では 1 列で幅いっぱいに描き、縦にスクロールして見る）
    let best = null;
    for (let c = opt.cols || 1; c <= (opt.cols || 4); c++) {
      const cols = split(c);
      const colH = Math.max(...cols.map(col => col.reduce((a, b) => a + b.h, 0)));
      const wTot = cols.length * W + (cols.length - 1) * GAP;
      const s = Math.min(maxW / wTot, maxH / colH, 1.25);
      if (!best || s > best.s + 0.01) best = { s, cols, colH, wTot };
    }
    const MIN_S = 0.42; // これより小さくすると見づらいので、その場合はスクロールで見る
    const s = Math.max(best.s, Math.min(MIN_S, maxW / best.wTot));
    const cssW = best.wTot * s, cssH = best.colH * s;
    canvas.style.width = cssW + 'px'; canvas.style.height = cssH + 'px';
    canvas.width = Math.round(cssW * dpr); canvas.height = Math.round(cssH * dpr);
    const g = canvas.getContext('2d');
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.fillStyle = '#fffaf0'; g.fillRect(0, 0, canvas.width, canvas.height);

    // 小節番号の通し番号
    let num = 0;
    const numStart = new Map();
    for (const r of rows) { numStart.set(r, num); num += Math.max(0, r.bars.length - 1); }

    best.cols.forEach((col, ci) => {
      let cy0 = 0;
      for (const b of col) {
        const ox = ci * (W + GAP), oy = cy0 - b.y0;
        g.setTransform(dpr * s, 0, 0, dpr * s, dpr * s * ox, dpr * s * oy);
        drawRow(g, b.r, numStart.get(b.r), opt);
        cy0 += b.h;
      }
    });
    return { height: cssH, width: cssW, scale: s, cols: best.cols.length };
  }

  function drawRow(g, r, numStart, opt) {
    opt = opt || {};
    const bandTop = r.lineY, bandBot = r.bottom + 7;
    // ゴーゴータイム
    g.fillStyle = '#ffd0d6';
    for (const [a, b] of r.gogo) g.fillRect(a, r.lineY - 32, b - a, 32);
    // レーン帯
    g.fillStyle = '#3a2a1e'; g.fillRect(0, bandTop, r.laneEnd + 1, bandBot - bandTop + 1);
    g.fillStyle = '#ffffff'; g.fillRect(0, bandTop + 2, r.laneEnd + 1, bandBot - bandTop - 3);
    for (const l of r.lanes) { g.fillStyle = LANE_COLORS[l.type]; g.fillRect(0, l.top, r.laneEnd + 1, l.bottom - l.top + 1); }
    // 小節線と拍の目印
    for (let i = 0; i < r.bars.length; i++) {
      const x = r.bars[i];
      const next = r.bars[i + 1];
      if (next) {
        g.fillStyle = 'rgba(255,255,255,.28)';
        for (let bx = x + PX_PER_BEAT; bx < next - 2; bx += PX_PER_BEAT) g.fillRect(bx - 1, r.top, 2, r.bottom - r.top + 1);
      }
      g.fillStyle = '#ffffff'; g.fillRect(x - 1, r.lineY - 10, 2, r.bottom - r.lineY + 10);
    }
    // BPM・HS（元画像と同じ位置: BPM は小節番号の上、HS はさらに上）
    g.font = 'bold 7.5px "M PLUS Rounded 1c", sans-serif'; g.textBaseline = 'alphabetic';
    for (const lb of r.labels) {
      if (lb.kind === 'bpm' && opt.hideBpm) continue; // 出題中に BPM を伏せているときは描かない
      if (lb.kind === 'bpm') { g.fillStyle = '#1f5fd6'; g.fillText('BPM' + lb.value, lb.x + 1.5, r.lineY - 8); }
      else { g.fillStyle = '#e0352b'; g.fillText('HS' + lb.value, lb.x + 1.5, r.lineY - 15); }
    }
    // 小節番号
    g.fillStyle = '#5a4636';
    for (let i = 0; i + 1 < r.bars.length; i++) g.fillText(String(numStart + i + 1), r.bars[i] + 2.5, r.lineY - 1.5);
    // 音符（レーンごと。連打の帯 → 音符を右から描いて左が上になるように）
    for (const l of r.lanes) {
      const cy = (l.top + l.bottom) / 2 + 0.5;
      const items = l.notes;
      let openRoll = null;
      const segs = [];
      for (const n of items) {
        if (n.kind === 'roll') openRoll = n;
        else if (n.kind === 'end') { segs.push({ x0: openRoll ? openRoll.x : r.bars[0] || 23.5, x1: n.x, c: openRoll ? openRoll.c : n.c, big: openRoll ? openRoll.big : n.big, head: !!openRoll, count: openRoll && openRoll.count }); openRoll = null; }
      }
      if (openRoll) segs.push({ x0: openRoll.x, x1: r.laneEnd, c: openRoll.c, big: openRoll.big, head: true, open: true, count: openRoll.count });
      for (const sg of segs) {
        const rad = sg.big ? 12 : 9;
        const balloon = sg.c === 'o';
        const col = balloon ? '#ffc04d' : '#ffd43b';
        g.fillStyle = '#3a2a1e';
        roundRect(g, sg.x0 - rad, cy - rad, sg.x1 - sg.x0 + 2 * rad, 2 * rad, rad); g.fill();
        g.fillStyle = col;
        roundRect(g, sg.x0 - rad + 1.5, cy - rad + 1.5, sg.x1 - sg.x0 + 2 * rad - 3, 2 * rad - 3, rad - 1.5); g.fill();
        if (sg.head) {
          if (balloon) drawBalloon(g, sg.x0, cy, rad, sg.count);
          else drawNote(g, sg.x0, cy, rad, col);
        }
      }
      const ns = items.filter(n => n.kind === 'note');
      for (let i = ns.length - 1; i >= 0; i--) {
        const n = ns[i];
        drawNote(g, n.x, cy, n.big ? 12 : 9, n.c === 'd' ? '#ff4b3e' : '#2fb8e8');
      }
    }
  }
  // マットな音符: 濃い縁 + 白い縁 + 単色（小音符の白い縁は細め）
  function drawNote(g, x, y, r, col) {
    const rim = r >= 12 ? 1.5 : 0.9;
    g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fillStyle = '#3a2a1e'; g.fill();
    g.beginPath(); g.arc(x, y, r - 1.5, 0, Math.PI * 2); g.fillStyle = '#ffffff'; g.fill();
    g.beginPath(); g.arc(x, y, r - 1.5 - rim, 0, Math.PI * 2); g.fillStyle = col; g.fill();
  }
  // 風船音符: 左に結び目のついた、橙色の丸い風船
  // 大きさは通常音符と同じ（外径 r）
  function drawBalloon(g, x, y, r, count) {
    // 結び目（左向きの小さな三角）
    g.beginPath(); g.moveTo(x - r + 1.5, y); g.lineTo(x - r - 4, y - 3.5); g.lineTo(x - r - 4, y + 3.5); g.closePath();
    g.fillStyle = '#3a2a1e'; g.fill();
    g.beginPath(); g.moveTo(x - r + 0.5, y); g.lineTo(x - r - 2.6, y - 2); g.lineTo(x - r - 2.6, y + 2); g.closePath();
    g.fillStyle = '#ff8a1f'; g.fill();
    // 風船本体（通常音符と同じ作り: 濃い縁 + 白い縁 + 橙）
    drawNote(g, x, y, r, '#ff8a1f');
    // 連打数（小さく）
    if (count) {
      const s = String(count);
      g.font = `800 ${s.length > 2 ? 5 : 6.5}px "M PLUS Rounded 1c", sans-serif`;
      g.textAlign = 'center'; g.textBaseline = 'middle';
      g.lineWidth = 1.4; g.strokeStyle = '#3a2a1e'; g.strokeText(s, x, y + 0.5);
      g.fillStyle = '#ffffff'; g.fillText(s, x, y + 0.5);
      g.textAlign = 'start'; g.textBaseline = 'alphabetic';
    }
  }
  function roundRect(g, x, y, w, h, r) {
    r = Math.max(0, Math.min(r, h / 2, w / 2));
    g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
  }

  // ---------- 保存済みの譜面データ（charts/<id>.js）を読み込む ----------
  // 譜面画像の読み取りはデータ作成時（tools/parse_charts.py）に済ませてあり、
  // クイズは Wiki の画像を読み込まずにこのデータだけで描く
  const chartWaiters = {};
  global.__chart = (id, data) => { const w = chartWaiters[id]; if (w) { w.resolve(expand(data)); } };
  function loadChart(id, base) {
    if (chartWaiters[id]) return chartWaiters[id].promise;
    let resolve, reject;
    const promise = new Promise((a, b) => { resolve = a; reject = b; });
    chartWaiters[id] = { promise, resolve };
    const s = document.createElement('script');
    s.src = (base || 'charts/') + id + '.js';
    s.onerror = () => { delete chartWaiters[id]; reject(new Error('譜面データを読み込めません')); };
    document.head.appendChild(s);
    return promise;
  }
  // 小さく保存した形 → renderFumen が使う形
  function expand(c) {
    const KIND = { d: ['note', 'd'], k: ['note', 'k'], r: ['roll', 'y'], o: ['roll', 'o'], e: ['end', 'y'], E: ['end', 'o'] };
    return {
      ok: true, width: c.w,
      rows: c.rows.map(r => ({
        lineY: r.l, top: r.t, bottom: r.b, laneEnd: r.e, bars: r.bars, gogo: r.g,
        labels: r.lb.map(([k, x, v]) => ({ kind: k === 'B' ? 'bpm' : 'hs', x, value: v })),
        lanes: r.ln.map(([type, top, bottom, notes]) => ({
          type, top, bottom,
          notes: notes.map(a => ({ x: a[0], kind: KIND[a[1]][0], c: KIND[a[1]][1], big: !!a[2], count: a[3] }))
        }))
      }))
    };
  }

  // 画像そのものの誤りを手直しする（tools/chart_fixes.json）。fix.remove: [{bar: 小節番号, c: 'd'|'k', n: 何個目か}]
  // 読み取り結果 f の音符を消し、音符数（combo / combos）も消した数だけ減らす
  function applyFix(f, fix) {
    if (!f || !f.ok || !fix || !fix.remove) return f;
    let num = 0, removed = 0;
    const where = []; // 小節番号 → [段, 左端x, 右端x]
    for (const r of f.rows) { for (let i = 0; i + 1 < r.bars.length; i++) where[++num] = [r, r.bars[i], r.bars[i + 1]]; }
    for (const rm of fix.remove) {
      const w = where[rm.bar]; if (!w) continue;
      const [r, x0, x1] = w;
      for (const l of r.lanes) {
        const hits = l.notes.filter(n => n.kind === 'note' && n.c === rm.c && n.x >= x0 - 6 && n.x < x1 - 6).sort((a, b) => a.x - b.x);
        const t = hits[(rm.n || 1) - 1];
        if (t) { l.notes.splice(l.notes.indexOf(t), 1); removed = 1; }
      }
      if (removed) { f.combo -= 1; if (f.combos) f.combos = f.combos.map(c => c - 1); removed = 0; }
    }
    return f;
  }

  global.FumenParse = { parseFumenImage, loadFumen, renderFumen, loadChart, applyFix };
})(window);
