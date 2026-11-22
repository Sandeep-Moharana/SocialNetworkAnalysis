/* Social Network Analysis dashboard.
 * Shows the results in window.SNA_DATA (written by jobs/06_export_dashboard.py).
 * Plain JavaScript, no libraries: open index.html directly, no server or internet needed.
 *
 *   1 Overview          stat tiles + friend-count chart
 *   2 Network graph     every user and friendship on a canvas (pan, zoom, hover, select)
 *   3 Influencers       top lists + friends-vs-PageRank scatter
 *   4 Communities       sizes chart + table, highlight a community in the graph
 *   5 Recommendations   suggestions for any user + "why" diagram (mutual friends)
 *   6 How it works      pipeline, cluster, timings
 */
(function () {
  "use strict";
  const D = window.SNA_DATA;
  const $ = (id) => document.getElementById(id);

  // ---------- theme (works even without data) ----------
  try { const t = localStorage.getItem("sna-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) { /* private mode */ }
  $("theme-btn").addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("sna-theme", root.dataset.theme); } catch (e) { /* ignore */ }
    refreshPalette(); renderTab(currentTab); drawGraph();
  });

  if (!D) { $("nodata").hidden = false; document.querySelector("nav.tabs").hidden = true; return; }

  // =====================================================================
  // Data preparation
  // =====================================================================
  const U = D.users, N = U.id.length, E = D.edges;
  const index = new Map(U.id.map((id, i) => [id, i]));          // user id -> array position
  const nbrs = Array.from({ length: N }, () => []);             // friends of each user (positions)
  for (let k = 0; k < E.length; k += 2) { nbrs[E[k]].push(E[k + 1]); nbrs[E[k + 1]].push(E[k]); }

  const byDesc = (key) => [...Array(N).keys()].sort((a, b) => U[key][b] - U[key][a] || U.id[a] - U.id[b]);
  const prOrder = byDesc("pagerank"), degOrder = byDesc("degree");
  const prRank = new Int32Array(N), degRank = new Int32Array(N);
  prOrder.forEach((i, r) => (prRank[i] = r + 1));
  degOrder.forEach((i, r) => (degRank[i] = r + 1));

  const comms = D.communities;                                   // largest first
  const commInfo = new Map(comms.map((c, r) => [c.community, Object.assign({ rank: r + 1 }, c)]));
  const TOP_COLORED = 8;                                         // categorical palette has 8 slots
  const commSlot = new Map(comms.slice(0, TOP_COLORED).map((c, s) => [c.community, s]));
  const members = new Map();
  U.community.forEach((c, i) => { if (!members.has(c)) members.set(c, []); members.get(c).push(i); });

  const S = D.stats, CS = D.community_summary;
  const fmt = (n, d = 0) => Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (x, d = 1) => fmt(100 * x, d) + "%";

  // ---------- colors: read from CSS tokens, so light/dark switch in one place ----------
  let pal = {};
  function refreshPalette() {
    const cs = getComputedStyle(document.documentElement);
    const v = (n) => cs.getPropertyValue(n).trim();
    pal = {
      slots: [1, 2, 3, 4, 5, 6, 7, 8].map((k) => v("--s" + k)),
      other: v("--other"), ramp: [1, 2, 3, 4, 5, 6].map((k) => v("--q" + k)),
      ink: v("--ink"), ink2: v("--ink-2"), muted: v("--muted"), surface: v("--surface"),
      accent: v("--accent"), grid: v("--grid"), edgeAlpha: parseFloat(v("--edge-alpha")) || 0.1,
    };
  }
  refreshPalette();
  const commColor = (c) => (commSlot.has(c) ? pal.slots[commSlot.get(c)] : pal.other);
  const prStep = (i) => Math.min(5, Math.floor((6 * (N - prRank[i])) / N));   // 0..5, 6 equal shares of users
  const swatch = (color) => `<i class="swatch" style="background:${color}"></i>`;
  const userLink = (id) => `<a href="#" class="userlink" data-user="${id}">${id}</a>`;

  // ---------- tooltip ----------
  const tip = $("tip");
  function showTip(html, ev) {
    tip.innerHTML = html; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - 14;
    if (y + r.height > innerHeight - 8) y = ev.clientY - r.height - 14;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  const hideTip = () => (tip.hidden = true);
  const row = (k, v) => `<div class="t-row"><span>${k}</span><span>${v}</span></div>`;
  function userTip(i) {
    const c = U.community[i];
    return `<b>User ${U.id[i]}</b>` + row("Friends", `${fmt(U.degree[i])} (#${degRank[i]})`) +
      row("PageRank", `${fmt(U.pagerank[i], 2)} (#${prRank[i]})`) +
      row("Community", `${swatch(commColor(c))} ${c} · ${fmt(commInfo.get(c).size)} members`);
  }

  // =====================================================================
  // Tabs (the URL hash remembers the tab: index.html#graph)
  // =====================================================================
  const tabs = ["overview", "graph", "influencers", "communities", "recs", "how"];
  let currentTab = null;
  function showTab(name) {
    if (!tabs.includes(name)) name = "overview";
    currentTab = name;
    document.querySelectorAll("nav.tabs button").forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === name));
    tabs.forEach((t) => ($("page-" + t).hidden = t !== name));
    if (location.hash.slice(1) !== name) history.replaceState(null, "", "#" + name);
    hideTip(); renderTab(name);
  }
  document.querySelectorAll("nav.tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  function renderTab(name) {
    ({ overview: renderOverview, graph: () => { resizeGraph(); renderPanel(); },
       influencers: renderInfluencers, communities: renderCommunities, recs: renderRecs, how: renderHow }[name] || (() => {}))();
  }
  // Any "user id" link anywhere: open that user in the graph.
  document.addEventListener("click", (ev) => {
    const a = ev.target.closest("[data-user]");
    if (!a) return;
    ev.preventDefault();
    const i = index.get(Number(a.dataset.user));
    if (i !== undefined) { focusUser(i, true); showTab("graph"); }
  });
  let resizeTimer;
  addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => renderTab(currentTab), 120); });

  $("subtitle").textContent = `SNAP ego-Facebook · computed with HDFS + Spark + GraphFrames · exported ${D.generated}`;

  // =====================================================================
  // Small SVG chart helpers (thin marks, hairline grid, hover tooltips)
  // =====================================================================
  function niceMax(v) {
    const p = Math.pow(10, Math.floor(Math.log10(v || 1))), m = v / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }
  const roundTop = (x, y, w, h, r) => {          // bar with 4px rounded data-end, square at the baseline
    r = Math.min(r, w / 2, h);
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  };
  const roundRight = (x, y, w, h, r) => {
    r = Math.min(r, h / 2, w);
    return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
  };
  function bindHits(el, items) {
    el.querySelectorAll("[data-i]").forEach((h) => {
      const it = items[+h.dataset.i];
      h.addEventListener("mousemove", (ev) => showTip(it.tip, ev));
      h.addEventListener("mouseleave", hideTip);
      if (it.onClick) h.addEventListener("click", it.onClick);
    });
  }

  /** Vertical bars. items: {label, value, color, tip}. Direct label on the tallest bar only. */
  function vbars(el, items, opts = {}) {
    const W = Math.max(320, el.clientWidth), H = opts.height || 260;
    const m = { l: 52, r: 8, t: 20, b: 40 }, pw = W - m.l - m.r, ph = H - m.t - m.b;
    const max = niceMax(Math.max(...items.map((d) => d.value)));
    const band = pw / items.length, bw = Math.max(4, Math.min(48, band - 6));
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${opts.aria || "bar chart"}">`;
    for (let k = 0; k <= 4; k++) {
      const y = m.t + ph - (ph * k) / 4;
      s += `<line class="${k ? "gridline" : "axisline"}" x1="${m.l}" x2="${W - m.r}" y1="${y}" y2="${y}"/>` +
        `<text x="${m.l - 8}" y="${y + 4}" text-anchor="end" class="num">${fmt((max * k) / 4)}</text>`;
    }
    if (opts.yLabel) s += `<text x="${m.l - 8}" y="${m.t - 8}" text-anchor="end">${opts.yLabel}</text>`;
    const top = items.reduce((b, d, i) => (d.value > items[b].value ? i : b), 0);
    items.forEach((d, i) => {
      const x = m.l + i * band + (band - bw) / 2, h = (ph * d.value) / max, y = m.t + ph - h;
      s += `<rect class="hit" data-i="${i}" x="${m.l + i * band}" y="${m.t}" width="${band}" height="${ph}"/>`;
      s += `<path class="mark" d="${roundTop(x, y, bw, Math.max(h, 0.5), 4)}" fill="${d.color}" pointer-events="none"/>`;
      if (i === top) s += `<text class="val" x="${x + bw / 2}" y="${y - 6}" text-anchor="middle">${fmt(d.value)}</text>`;
      s += `<text x="${x + bw / 2}" y="${H - m.b + 16}" text-anchor="middle">${d.label}</text>`;
    });
    if (opts.xLabel) s += `<text x="${m.l + pw / 2}" y="${H - 4}" text-anchor="middle">${opts.xLabel}</text>`;
    el.innerHTML = s + "</svg>";
    bindHits(el, items);
  }

  /** Horizontal bars, one row per item. labelValues: which rows show their value. */
  function hbars(el, items, opts = {}) {
    const W = Math.max(320, el.clientWidth), rowH = opts.rowH || 24, lw = opts.labelWidth || 150;
    const m = { t: 4, b: 8 }, H = m.t + items.length * rowH + m.b, pw = W - lw - 70;
    const max = Math.max(...items.map((d) => d.value));
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${opts.aria || "bar chart"}">`;
    s += `<line class="axisline" x1="${lw}" x2="${lw}" y1="${m.t}" y2="${H - m.b}"/>`;
    items.forEach((d, i) => {
      const y = m.t + i * rowH, bh = Math.min(14, rowH - 6), w = Math.max(1, (pw * d.value) / max);
      s += `<rect class="hit" data-i="${i}" x="0" y="${y}" width="${W}" height="${rowH}"/>`;
      s += `<text class="lbl" x="${lw - 8}" y="${y + rowH / 2 + 4}" text-anchor="end" pointer-events="none">${d.label}</text>`;
      s += `<path class="mark" d="${roundRight(lw, y + (rowH - bh) / 2, w, bh, 4)}" fill="${d.color}" pointer-events="none"/>`;
      if (opts.labelValues === "all" || (opts.labelValues === "first" && i === 0))
        s += `<text class="val num" x="${lw + w + 6}" y="${y + rowH / 2 + 4}" pointer-events="none">${d.valueText || fmt(d.value)}</text>`;
    });
    el.innerHTML = s + "</svg>";
    bindHits(el, items);
  }

  function tiles(el, list) {
    el.innerHTML = list.map((t) =>
      `<div class="tile"><div class="label">${t[0]}</div><div class="value">${t[1]}</div><div class="hint">${t[2]}</div></div>`).join("");
  }

  // =====================================================================
  // 1. Overview
  // =====================================================================
  // Power-of-two ranges: 1, 2-3, 4-7, ... (heavy tail). The few hubs share one "256+" bar.
  const degreeBuckets = (() => {
    const TAIL = 8, counts = new Map();
    U.degree.forEach((d) => { const b = Math.min(TAIL, Math.floor(Math.log2(Math.max(d, 1)))); counts.set(b, (counts.get(b) || 0) + 1); });
    return Array.from({ length: TAIL + 1 }, (_, b) => {
      const lo = 2 ** b, hi = 2 ** (b + 1) - 1;
      const label = b === TAIL ? `${lo}+` : lo === hi ? `${lo}` : `${lo}–${hi}`;
      return { label, value: counts.get(b) || 0 };
    });
  })();

  function renderOverview() {
    const connected = S.components === 1 ? "everyone can reach everyone" : `largest: ${fmt(S.largest_component)} users`;
    $("ov-lead").innerHTML = `<b>${fmt(S.vertices)} users</b> and <b>${fmt(S.connections)} friendships</b> from the
      SNAP ego-Facebook dataset (anonymized friend lists). Every dot in the graph is a person, every line a friendship.`;
    tiles($("ov-tiles"), [
      ["Users", fmt(S.vertices), "people in the network"],
      ["Friendships", fmt(S.connections), "two-way connections"],
      ["Average friends", fmt(S.avg_degree, 1), `median ${fmt(S.median_degree)}, most ${fmt(S.max_degree)}`],
      ["Connected", fmt(S.components) + (S.components === 1 ? " piece" : " pieces"), connected],
      ["Triangles", fmt(S.triangles), "groups of 3 people who are all friends"],
      ["Clustering", fmt(S.avg_clustering, 3), "chance that two of your friends know each other"],
      ["Communities", fmt(CS.communities), "friend groups found by Label Propagation"],
      ["Modularity", fmt(CS.modularity, 3), "above 0.3 = clear group structure"],
    ]);
    const items = degreeBuckets.map((b) => ({
      label: b.label, value: b.value, color: pal.accent,
      tip: `<b>${b.label} friends</b>` + row("Users", fmt(b.value)) + row("Share", pct(b.value / N)),
    }));
    vbars($("ov-degree"), items, { yLabel: "users", xLabel: "number of friends", aria: "users per friend-count range" });
    const mid = U.degree.filter((d) => d >= 16 && d <= 63).length;
    $("ov-degree-note").innerHTML = `Most users have between 16 and 63 friends (${pct(mid / N, 0)}), but a few
      <b>hubs</b> have hundreds (up to ${fmt(S.max_degree)}). This long tail is typical of social networks.`;

    const top = prOrder[0], firstRecUser = index.get(460) ?? degOrder[N >> 1];
    const r0 = D.recs[firstRecUser][0];
    const feats = [
      ["Network graph", `${fmt(N)} users, ${fmt(S.connections)} friendships`, "See the whole network, colored by community. Zoom in and click anyone.", "graph"],
      ["Influencers", `#1 by PageRank: user ${U.id[top]}`, "Who is most connected, and who is connected to important people.", "influencers"],
      ["Communities", `${fmt(CS.communities)} groups · modularity ${fmt(CS.modularity, 3)}`, "Groups of friends found automatically.", "communities"],
      ["Friend recommendations", r0 ? `user ${U.id[firstRecUser]} → may know ${r0[1]} (${r0[2]} mutual)` : "for every user",
        "People you may know, with the mutual friends that explain why.", "recs"],
    ];
    $("ov-features").innerHTML = feats.map((f) =>
      `<button class="feature" data-go="${f[3]}"><span class="tag">${f[0]}</span><span class="big">${f[1]}</span><span class="desc">${f[2]}</span></button>`).join("");
    $("ov-features").querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.go)));
  }

  // =====================================================================
  // 2. Network graph (canvas)
  // =====================================================================
  const canvas = $("graph"), ctx = canvas.getContext("2d");
  const view = { scale: 1, tx: 0, ty: 0, fit: 1, w: 0, h: 0 };
  let colorMode = "community", showEdges = true, hovered = -1, pendingCenter = null;
  let focus = null;      // null | {type:"user", i} | {type:"community", c} | {type:"recs", i, sel}
  let drawQueued = false;

  // Bounds of the layout, for "fit to screen".
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < N; i++) {
    minX = Math.min(minX, U.x[i]); maxX = Math.max(maxX, U.x[i]);
    minY = Math.min(minY, U.y[i]); maxY = Math.max(maxY, U.y[i]);
  }
  function fitView() {
    view.fit = 0.92 * Math.min(view.w / (maxX - minX || 1), view.h / (maxY - minY || 1));
    view.scale = view.fit;
    view.tx = view.w / 2 - view.scale * (minX + maxX) / 2;
    view.ty = view.h / 2 - view.scale * (minY + maxY) / 2;
  }
  function resizeGraph() {
    const r = canvas.getBoundingClientRect();
    if (!r.width) return;
    const first = view.w === 0, dpr = devicePixelRatio || 1;
    view.w = r.width; view.h = r.height;
    canvas.width = Math.round(r.width * dpr); canvas.height = Math.round(r.height * dpr);
    if (first) fitView();
    if (pendingCenter) { centerOn(...pendingCenter); pendingCenter = null; }
    paint();               // right away: a resized canvas is blank until repainted
  }
  new ResizeObserver(() => { if (currentTab === "graph") resizeGraph(); }).observe(canvas);

  // Friendship lines, built once in layout coordinates (fast redraw while panning/zooming).
  // Lines inside one of the 8 colored communities get that community's color.
  const edgePaths = (() => {
    const bySlot = Array.from({ length: TOP_COLORED }, () => new Path2D()), rest = new Path2D(), all = new Path2D();
    for (let k = 0; k < E.length; k += 2) {
      const a = E[k], b = E[k + 1], ca = U.community[a];
      const p = ca === U.community[b] && commSlot.has(ca) ? bySlot[commSlot.get(ca)] : rest;
      p.moveTo(U.x[a], U.y[a]); p.lineTo(U.x[b], U.y[b]);
      all.moveTo(U.x[a], U.y[a]); all.lineTo(U.x[b], U.y[b]);
    }
    return { bySlot, rest, all };
  })();
  const drawOrder = [...prOrder].reverse();       // small first, hubs drawn on top

  const nodeColor = (i) => (colorMode === "community" ? commColor(U.community[i]) : pal.ramp[prStep(i)]);
  const zoomFactor = () => Math.min(3, Math.max(1, Math.sqrt(view.scale / view.fit)));
  const radiusPx = (i) => (1.4 + 1.25 * Math.sqrt(U.pagerank[i])) * zoomFactor();
  const toScreen = (i) => [U.x[i] * view.scale + view.tx, U.y[i] * view.scale + view.ty];

  function drawGraph() {
    if (drawQueued || currentTab !== "graph") return;
    drawQueued = true;
    requestAnimationFrame(() => { drawQueued = false; paint(); });
  }

  function paint() {
    const dpr = devicePixelRatio || 1, s = view.scale;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(dpr * s, 0, 0, dpr * s, dpr * view.tx, dpr * view.ty);
    const dim = focus ? 0.14 : 1;

    // 1. Friendships
    if (showEdges) {
      ctx.lineWidth = 0.7 / s;
      ctx.globalAlpha = pal.edgeAlpha * dim * (focus ? 0.6 : 1);
      if (colorMode === "community") {
        ctx.strokeStyle = pal.other; ctx.stroke(edgePaths.rest);
        edgePaths.bySlot.forEach((p, k) => { ctx.strokeStyle = pal.slots[k]; ctx.stroke(p); });
      } else { ctx.strokeStyle = pal.muted; ctx.stroke(edgePaths.all); }
    }

    // 2. Users (batched by color: one fill per color)
    ctx.globalAlpha = dim;
    drawNodes(drawOrder, 0);

    // 3. Focus layer
    ctx.globalAlpha = 1;
    const labels = [];
    if (focus && focus.type === "user") {
      const i = focus.i;
      lines([[i, nbrs[i]]], pal.ink, 0.35, 1);
      drawNodes(nbrs[i], 0); drawNodes([i], 3, pal.ink);
      labels.push([i, `User ${U.id[i]}`]);
    } else if (focus && focus.type === "community") {
      const ms = members.get(focus.c) || [], set = new Set(ms), col = commColor(focus.c);
      ctx.beginPath();
      ms.forEach((a) => nbrs[a].forEach((b) => { if (a < b && set.has(b)) { ctx.moveTo(U.x[a], U.y[a]); ctx.lineTo(U.x[b], U.y[b]); } }));
      ctx.lineWidth = 0.8 / s; ctx.globalAlpha = 0.25; ctx.strokeStyle = col === pal.other ? pal.ink2 : col; ctx.stroke();
      ctx.globalAlpha = 1;
      drawNodes(ms, 0);
      const leader = index.get(commInfo.get(focus.c).leader);
      if (leader !== undefined) labels.push([leader, `Leader ${U.id[leader]}`]);
    } else if (focus && focus.type === "recs") {
      const i = focus.i, recs = D.recs[i];
      const cands = recs.map((r) => index.get(r[1])).filter((x) => x !== undefined);
      lines([[i, nbrs[i]]], pal.ink, 0.18, 1);
      if (focus.sel != null && cands[focus.sel] !== undefined) {
        const c = cands[focus.sel], mutual = mutualFriends(i, c);
        lines([[i, mutual], [c, mutual]], pal.slots[1], 0.75, 1.5);
        drawNodes(mutual, 1);
      }
      drawNodes(nbrs[i], 0);
      drawNodes(cands, 3, pal.slots[1]);
      drawNodes([i], 4, pal.ink);
      labels.push([i, `User ${U.id[i]}`]);
      cands.forEach((c, k) => labels.push([c, `#${k + 1} ${U.id[c]}`]));
    } else {
      prOrder.slice(0, 5).forEach((i, k) => labels.push([i, `#${k + 1} ${U.id[i]}`]));   // the top influencers
    }
    if (hovered >= 0) { drawNodes([hovered], 3, pal.ink); }

    // 4. Labels in screen pixels, with a surface-colored halo for readability
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = "600 12px system-ui, -apple-system, Segoe UI, sans-serif";
    ctx.lineJoin = "round";
    labels.forEach(([i, text]) => {
      const [x, y] = toScreen(i), r = radiusPx(i);
      ctx.lineWidth = 4; ctx.strokeStyle = pal.surface; ctx.strokeText(text, x + r + 4, y + 4);
      ctx.fillStyle = pal.ink; ctx.fillText(text, x + r + 4, y + 4);
    });
  }

  /** Draw users; extra = extra radius in px; ring = optional outline color. */
  function drawNodes(list, extra, ring) {
    const s = view.scale, groups = new Map();
    list.forEach((i) => { const c = nodeColor(i); if (!groups.has(c)) groups.set(c, []); groups.get(c).push(i); });
    groups.forEach((ids, color) => {
      const p = new Path2D();
      ids.forEach((i) => { const r = (radiusPx(i) + extra) / s; p.moveTo(U.x[i] + r, U.y[i]); p.arc(U.x[i], U.y[i], r, 0, 2 * Math.PI); });
      ctx.fillStyle = color; ctx.fill(p);
      ctx.lineWidth = (ring ? 2 : 0.8) / s; ctx.strokeStyle = ring || pal.surface; ctx.stroke(p);
    });
  }
  function lines(pairs, color, alpha, widthPx) {
    ctx.beginPath();
    pairs.forEach(([a, list]) => list.forEach((b) => { ctx.moveTo(U.x[a], U.y[a]); ctx.lineTo(U.x[b], U.y[b]); }));
    ctx.globalAlpha = alpha; ctx.lineWidth = widthPx / view.scale; ctx.strokeStyle = color; ctx.stroke(); ctx.globalAlpha = 1;
  }
  function mutualFriends(a, b) {
    const set = new Set(nbrs[a]);
    return nbrs[b].filter((x) => set.has(x)).sort((x, y) => U.degree[x] - U.degree[y] || U.id[x] - U.id[y]);
  }

  // ---------- interaction: hover, click, pan, zoom ----------
  function nodeAt(mx, my) {
    let best = -1, bestD = Infinity;
    for (let i = 0; i < N; i++) {
      const dx = U.x[i] * view.scale + view.tx - mx, dy = U.y[i] * view.scale + view.ty - my;
      const d = dx * dx + dy * dy, hit = Math.max(9, radiusPx(i) + 3);
      if (d < hit * hit && d < bestD) { best = i; bestD = d; }
    }
    return best;
  }
  let drag = null;
  canvas.addEventListener("pointerdown", (ev) => {
    drag = { x: ev.clientX, y: ev.clientY, tx: view.tx, ty: view.ty, moved: false };
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener("pointermove", (ev) => {
    const r = canvas.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
    if (drag) {
      const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) { drag.moved = true; canvas.classList.add("dragging"); }
      if (drag.moved) { view.tx = drag.tx + dx; view.ty = drag.ty + dy; hideTip(); drawGraph(); return; }
    }
    const h = nodeAt(mx, my);
    if (h !== hovered) { hovered = h; drawGraph(); }
    canvas.style.cursor = h >= 0 ? "pointer" : "";
    if (h >= 0) showTip(userTip(h) + `<div class="muted" style="margin-top:4px">Click to select</div>`, ev); else hideTip();
  });
  canvas.addEventListener("pointerup", (ev) => {
    canvas.classList.remove("dragging");
    const wasDrag = drag && drag.moved; drag = null;
    if (wasDrag) return;
    const r = canvas.getBoundingClientRect(), i = nodeAt(ev.clientX - r.left, ev.clientY - r.top);
    if (i >= 0) focusUser(i, false); else { focus = null; renderPanel(); drawGraph(); }
  });
  canvas.addEventListener("pointerleave", () => { hovered = -1; hideTip(); drawGraph(); });
  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const r = canvas.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
    const k = Math.exp(-ev.deltaY * 0.0015), ns = Math.min(view.fit * 40, Math.max(view.fit * 0.5, view.scale * k));
    view.tx = mx - ((mx - view.tx) * ns) / view.scale; view.ty = my - ((my - view.ty) * ns) / view.scale;
    view.scale = ns; drawGraph();
  }, { passive: false });

  function centerOn(i, zoom) {
    if (!view.w) return;
    view.scale = Math.max(view.scale, view.fit * zoom);
    view.tx = view.w / 2 - U.x[i] * view.scale; view.ty = view.h / 2 - U.y[i] * view.scale;
  }
  // zoom=true when coming from another tab: center on the user once the canvas has its size.
  function focusUser(i, zoom) { focus = { type: "user", i }; if (zoom) pendingCenter = [i, 3]; renderPanel(); drawGraph(); }

  document.querySelectorAll("[data-color]").forEach((b) => b.addEventListener("click", () => {
    colorMode = b.dataset.color;
    document.querySelectorAll("[data-color]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    renderLegend(); drawGraph();
  }));
  $("g-edges").addEventListener("change", (ev) => { showEdges = ev.target.checked; drawGraph(); });
  $("g-reset").addEventListener("click", () => { focus = null; fitView(); renderPanel(); drawGraph(); });
  function findUser() {
    const v = $("g-search").value.trim(), i = index.get(Number(v));
    if (v === "" ) return;
    if (i === undefined) { $("g-search").setCustomValidity("No user with this id"); $("g-search").reportValidity(); return; }
    $("g-search").setCustomValidity("");
    focusUser(i, false); centerOn(i, 3); drawGraph();
  }
  $("g-search-btn").addEventListener("click", findUser);
  $("g-search").addEventListener("keydown", (ev) => { if (ev.key === "Enter") findUser(); });

  function renderLegend() {
    if (colorMode === "community") {
      $("g-legend").innerHTML = `<div class="legend">` +
        comms.slice(0, TOP_COLORED).map((c, k) => `<span>${swatch(pal.slots[k])}Community ${c.community} (${fmt(c.size)})</span>`).join("") +
        `<span>${swatch(pal.other)}${comms.length - TOP_COLORED} smaller communities</span></div>`;
    } else {
      $("g-legend").innerHTML = `<div class="legend"><span>PageRank: lowest</span><span class="ramp">${pal.ramp.map((c) => `<i style="background:${c}"></i>`).join("")}</span>` +
        `<span>highest (each shade = ⅙ of users) · dot size = PageRank</span></div>`;
    }
  }

  // ---------- side panel ----------
  function renderPanel() {
    renderLegend();
    const p = $("g-panel");
    if (!focus) {
      p.innerHTML = `<div><h2>The whole network</h2><p class="ink2" style="margin-top:6px">Each dot is a user,
        each line a friendship. Friends are pulled together, so <b>groups of friends form clusters</b>; colors are the
        communities from step 4. Bigger dots have a higher <b>PageRank</b>.</p></div>
        <dl class="kv"><dt>Users</dt><dd>${fmt(N)}</dd><dt>Friendships</dt><dd>${fmt(S.connections)}</dd>
        <dt>Communities</dt><dd>${fmt(CS.communities)}</dd><dt>Modularity</dt><dd>${fmt(CS.modularity, 3)}</dd></dl>
        <div><h3>Try</h3><ul class="ink2" style="margin:6px 0 0;padding-left:18px">
          <li>Hover a dot to see who it is, click to select it.</li>
          <li>Switch to <b>Color: PageRank</b> to see the influencers.</li>
          <li>Labels show the top 5 users by PageRank.</li></ul></div>
        <div class="btn-row">${prOrder.slice(0, 5).map((i) => `<button class="btn" data-user="${U.id[i]}">${U.id[i]}</button>`).join("")}</div>`;
      return;
    }
    if (focus.type === "community") {
      const c = commInfo.get(focus.c);
      p.innerHTML = `<div><h2>${swatch(commColor(c.community))} Community ${c.community}</h2>
        <p class="muted">#${c.rank} largest of ${fmt(comms.length)}</p></div>
        <dl class="kv"><dt>Members</dt><dd>${fmt(c.size)} (${pct(c.size / N)})</dd>
        <dt>Friendships inside</dt><dd>${fmt(c.internal_connections)}</dd>
        <dt>Density</dt><dd>${pct(c.density)}</dd>
        <dt>Leader (most friends)</dt><dd>${userLink(c.leader)} · ${fmt(c.leader_degree)} friends</dd></dl>
        <p class="ink2" style="font-size:14px">Density: of all possible friendships between members, how many exist.</p>
        <div class="btn-row"><button class="btn" id="p-clear">Show everyone</button></div>`;
      $("p-clear").onclick = () => { focus = null; renderPanel(); drawGraph(); };
      return;
    }
    const i = focus.i, c = U.community[i], ci = commInfo.get(c), recs = D.recs[i];
    p.innerHTML = `<div><h2>User ${U.id[i]}</h2><p class="muted">${swatch(commColor(c))} Community ${c} ·
        #${ci.rank} largest (${fmt(ci.size)} members)</p></div>
      <dl class="kv">
        <dt>Friends</dt><dd>${fmt(U.degree[i])} <span class="muted">(#${degRank[i]})</span></dd>
        <dt>PageRank</dt><dd>${fmt(U.pagerank[i], 2)} <span class="muted">(#${prRank[i]})</span></dd>
        <dt>Triangles</dt><dd>${fmt(U.triangles[i])}</dd>
        <dt>Clustering</dt><dd>${fmt(U.clustering[i], 3)}</dd></dl>
      <p class="ink2" style="font-size:14px">${pct(U.clustering[i], 0)} of this user's friend pairs are friends with each other.</p>
      <div><h3>People they may know</h3>
        <div class="rec-mini">${recs.slice(0, 5).map((r) => `<button data-user="${r[1]}"><span>#${r[0]} · user <b>${r[1]}</b></span><span class="muted">${r[2]} mutual</span></button>`).join("") || '<span class="muted">No suggestions</span>'}</div></div>
      <div class="btn-row">
        <button class="btn ${focus.type === "recs" ? "" : "primary"}" id="p-recs">${focus.type === "recs" ? "Show friends" : "Show suggestions"}</button>
        <button class="btn" id="p-comm">Show community</button>
        <button class="btn" id="p-more">Details →</button></div>`;
    $("p-recs").onclick = () => { focus = focus.type === "recs" ? { type: "user", i } : { type: "recs", i, sel: null }; renderPanel(); drawGraph(); };
    $("p-comm").onclick = () => { focus = { type: "community", c }; renderPanel(); drawGraph(); };
    $("p-more").onclick = () => { recUser = i; recSel = 0; showTab("recs"); };
  }

  // =====================================================================
  // 3. Influencers
  // =====================================================================
  function renderInfluencers() {
    const K = 15, topD = degOrder.slice(0, K), topP = prOrder.slice(0, K);
    const setD = new Set(topD), setP = new Set(topP), both = topD.filter((i) => setP.has(i)).length;
    // Pearson correlation of friends and PageRank over all users.
    const mx = U.degree.reduce((a, b) => a + b, 0) / N, my = U.pagerank.reduce((a, b) => a + b, 0) / N;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < N; i++) { const a = U.degree[i] - mx, b = U.pagerank[i] - my; sxy += a * b; sxx += a * a; syy += b * b; }
    const corr = sxy / Math.sqrt(sxx * syy);
    const surprise = prOrder.slice(0, 10).reduce((b, i) => (U.degree[i] < U.degree[b] ? i : b), prOrder[0]);
    tiles($("inf-tiles"), [
      ["#1 by friends", `User ${U.id[degOrder[0]]}`, `${fmt(U.degree[degOrder[0]])} friends`],
      ["#1 by PageRank", `User ${U.id[prOrder[0]]}`, `PageRank ${fmt(U.pagerank[prOrder[0]], 1)} (${fmt(U.pagerank[prOrder[0]], 0)}× average)`],
      ["In both top 15", `${both} of ${K}`, "the two measures partly agree"],
      ["Surprise", `User ${U.id[surprise]}`, `only ${fmt(U.degree[surprise])} friends, but PageRank #${prRank[surprise]}`],
    ]);
    const table = (list, other, valueOf, label, maxV) => `<table><thead><tr><th class="r">#</th><th>User</th><th class="r">${label}</th><th></th></tr></thead><tbody>` +
      list.map((i, k) => `<tr data-user="${U.id[i]}"><td class="r">${k + 1}</td><td>${userLink(U.id[i])} ${other.has(i) ? '<span class="both">◆</span>' : ""}</td>` +
        `<td class="r">${valueOf(i)}</td><td><div class="inbar"><i style="width:${(100 * (label === "Friends" ? U.degree[i] : U.pagerank[i])) / maxV}%"></i></div></td></tr>`).join("") + "</tbody></table>";
    $("inf-degree").innerHTML = table(topD, setP, (i) => fmt(U.degree[i]), "Friends", U.degree[topD[0]]);
    $("inf-pr").innerHTML = table(topP, setD, (i) => fmt(U.pagerank[i], 2), "PageRank", U.pagerank[topP[0]]);
    scatter(corr);
  }

  function scatter(corr) {
    const el = $("inf-scatter"), W = Math.max(320, el.clientWidth), H = 380;
    const m = { l: 56, r: 16, t: 16, b: 44 }, pw = W - m.l - m.r, ph = H - m.t - m.b;
    const lx = (d) => Math.log10(d), ly = (p) => Math.log10(p);
    const x0 = 0, x1 = Math.ceil(lx(Math.max(...U.degree)) * 2) / 2;
    const y0 = Math.floor(ly(Math.min(...U.pagerank)) * 2) / 2, y1 = Math.ceil(ly(Math.max(...U.pagerank)) * 2) / 2;
    const X = (d) => m.l + ((lx(Math.max(d, 1)) - x0) / (x1 - x0)) * pw, Y = (p) => m.t + ph - ((ly(p) - y0) / (y1 - y0)) * ph;
    const top10 = new Set(prOrder.slice(0, 10));
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="friends versus PageRank for every user">`;
    for (let e = Math.ceil(x0); e <= x1; e++) s += `<line class="gridline" x1="${X(10 ** e)}" x2="${X(10 ** e)}" y1="${m.t}" y2="${m.t + ph}"/><text x="${X(10 ** e)}" y="${m.t + ph + 16}" text-anchor="middle" class="num">${fmt(10 ** e)}</text>`;
    for (let e = Math.ceil(y0); e <= y1; e++) s += `<line class="gridline" x1="${m.l}" x2="${m.l + pw}" y1="${Y(10 ** e)}" y2="${Y(10 ** e)}"/><text x="${m.l - 8}" y="${Y(10 ** e) + 4}" text-anchor="end" class="num">${10 ** e >= 1 ? fmt(10 ** e) : 10 ** e}</text>`;
    s += `<line class="axisline" x1="${m.l}" x2="${m.l + pw}" y1="${m.t + ph}" y2="${m.t + ph}"/>`;
    s += `<text x="${m.l + pw / 2}" y="${H - 6}" text-anchor="middle">number of friends</text>`;
    s += `<text transform="translate(14 ${m.t + ph / 2}) rotate(-90)" text-anchor="middle">PageRank (1 = average)</text>`;
    let dots = "", tops = "", labels = "";
    for (let i = 0; i < N; i++) if (!top10.has(i)) dots += `<circle cx="${X(U.degree[i]).toFixed(1)}" cy="${Y(U.pagerank[i]).toFixed(1)}" r="2.6"/>`;
    prOrder.slice(0, 10).forEach((i, k) => {
      const cx = X(U.degree[i]), cy = Y(U.pagerank[i]);
      tops += `<circle cx="${cx}" cy="${cy}" r="5" fill="${pal.slots[1]}" stroke="${pal.surface}" stroke-width="2"/>`;
      if (k < 5) labels += `<text class="lbl" x="${cx - 8}" y="${cy + 4}" text-anchor="end" style="paint-order:stroke;stroke:${pal.surface};stroke-width:3px">${U.id[i]}</text>`;
    });
    s += `<g fill="${pal.accent}" fill-opacity="0.35">${dots}</g>${tops}${labels}`;
    s += `<circle id="sc-hover" r="7" fill="none" stroke="${pal.ink}" stroke-width="2" visibility="hidden"/>`;
    s += `<rect id="sc-hit" x="${m.l}" y="${m.t}" width="${pw}" height="${ph}" fill="transparent" style="cursor:pointer"/>`;
    el.innerHTML = s + "</svg>";
    $("inf-legend").innerHTML = `<span>${swatch(pal.accent)}All users</span><span>${swatch(pal.slots[1])}Top 10 by PageRank</span>` +
      `<span class="muted">Correlation friends ↔ PageRank: ${fmt(corr, 2)}</span>`;
    // Nearest-dot hover (dots are tiny; the hit area is the whole plot).
    const svg = el.querySelector("svg"), ring = $("sc-hover"), hit = $("sc-hit");
    let near = -1;
    hit.addEventListener("mousemove", (ev) => {
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      const q = pt.matrixTransform(svg.getScreenCTM().inverse());
      let best = -1, bd = 400;                                    // within 20 px
      for (let i = 0; i < N; i++) { const dx = X(U.degree[i]) - q.x, dy = Y(U.pagerank[i]) - q.y, d = dx * dx + dy * dy; if (d < bd) { bd = d; best = i; } }
      near = best;
      if (best < 0) { ring.setAttribute("visibility", "hidden"); hideTip(); return; }
      ring.setAttribute("cx", X(U.degree[best])); ring.setAttribute("cy", Y(U.pagerank[best])); ring.setAttribute("visibility", "visible");
      showTip(userTip(best) + `<div class="muted" style="margin-top:4px">Click to open in the graph</div>`, ev);
    });
    hit.addEventListener("mouseleave", () => { ring.setAttribute("visibility", "hidden"); hideTip(); near = -1; });
    hit.addEventListener("click", () => { if (near >= 0) { focusUser(near, true); showTab("graph"); } });
  }

  // =====================================================================
  // 4. Communities
  // =====================================================================
  function renderCommunities() {
    const inside = comms.reduce((a, c) => a + c.internal_connections, 0) / S.connections;
    const big = comms[0];
    tiles($("com-tiles"), [
      ["Communities", fmt(CS.communities), `found in ${fmt(N)} users`],
      ["Modularity", fmt(CS.modularity, 3), CS.modularity > 0.3 ? "very clear group structure" : "weak group structure"],
      ["Largest community", fmt(big.size), `${pct(big.size / N)} of users · leader ${big.leader}`],
      ["Friendships inside groups", pct(inside), "both friends in the same community"],
    ]);
    const items = comms.slice(0, 20).map((c, k) => ({
      label: `${c.community} · leader ${c.leader}`, value: c.size, color: commColor(c.community),
      tip: `<b>Community ${c.community}</b>` + row("Members", fmt(c.size)) + row("Density", pct(c.density)) +
        row("Leader", `${c.leader} (${fmt(c.leader_degree)} friends)`) + `<div class="muted" style="margin-top:4px">Click to show in the graph</div>`,
      onClick: () => openCommunity(c.community),
    }));
    hbars($("com-bars"), items, { labelValues: "all", labelWidth: 170, aria: "members of the 20 largest communities" });
    $("com-table").innerHTML = `<table><thead><tr><th class="r">#</th><th>Community</th><th class="r">Members</th><th class="r">Density</th><th class="r">Friendships inside</th><th>Leader</th></tr></thead><tbody>` +
      comms.map((c, k) => `<tr data-comm="${c.community}"><td class="r">${k + 1}</td><td>${swatch(commColor(c.community))} ${c.community}</td>` +
        `<td class="r">${fmt(c.size)}</td><td class="r">${pct(c.density)}</td><td class="r">${fmt(c.internal_connections)}</td>` +
        `<td>${c.leader} <span class="muted">(${fmt(c.leader_degree)})</span></td></tr>`).join("") + "</tbody></table>";
    $("com-table").querySelectorAll("[data-comm]").forEach((tr) => tr.addEventListener("click", () => openCommunity(Number(tr.dataset.comm))));
  }
  function openCommunity(c) {
    focus = { type: "community", c };
    const ms = members.get(c) || [];
    if (ms.length) {           // zoom to the community's middle
      let x = 0, y = 0; ms.forEach((i) => { x += U.x[i]; y += U.y[i]; });
      pendingCenter = null; showTab("graph");
      view.scale = view.fit * (ms.length > 200 ? 1.6 : 2.5);
      view.tx = view.w / 2 - (x / ms.length) * view.scale; view.ty = view.h / 2 - (y / ms.length) * view.scale;
      renderPanel(); drawGraph();
    } else showTab("graph");
  }

  // =====================================================================
  // 5. Recommendations
  // =====================================================================
  let recUser = index.get(460) ?? degOrder[0], recSel = 0;
  const examples = [0, 107, 460, 3980, 1912].filter((id) => index.has(id));
  $("r-chips").innerHTML = examples.map((id) => `<button class="chip" data-pick="${id}">${id}</button>`).join("") +
    `<button class="chip" data-pick="random">Random user</button>`;
  $("r-chips").querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => {
    const i = b.dataset.pick === "random" ? Math.floor(Math.random() * N) : index.get(Number(b.dataset.pick));
    recUser = i; recSel = 0; $("r-input").value = U.id[i]; renderRecs();
  }));
  function pickRecUser() {
    const i = index.get(Number($("r-input").value));
    if (i === undefined) { $("r-input").setCustomValidity("No user with this id"); $("r-input").reportValidity(); return; }
    $("r-input").setCustomValidity(""); recUser = i; recSel = 0; renderRecs();
  }
  $("r-go").addEventListener("click", pickRecUser);
  $("r-input").addEventListener("keydown", (ev) => { if (ev.key === "Enter") pickRecUser(); });
  $("r-graph").addEventListener("click", () => { focus = { type: "recs", i: recUser, sel: recSel }; pendingCenter = [recUser, 2]; showTab("graph"); renderPanel(); });

  // Over ALL users: how many suggestions stay in the user's own community?
  const recStats = (() => {
    let n = 0, same = 0, users = 0, topMutual = 0;
    D.recs.forEach((list) => { if (list.length) { users++; topMutual += list[0][2]; } list.forEach((r) => { n++; same += r[4]; }); });
    return { n, same, users, topMutual: users ? topMutual / users : 0 };
  })();

  function renderRecs() {
    const i = recUser, recs = D.recs[i] || [];
    $("r-input").value = U.id[i];
    $("r-title").innerHTML = `Suggestions for user ${userLink(U.id[i])}`;
    $("r-sub").textContent = `${fmt(U.degree[i])} friends · community ${U.community[i]} · top ${recs.length} by mutual friends`;
    $("r-table").innerHTML = recs.length ? `<table><thead><tr><th class="r">#</th><th>Suggest</th><th>Mutual friends</th><th class="r">Adamic-Adar</th><th>Same community</th><th>Because you both know</th></tr></thead><tbody>` +
      recs.map((r, k) => `<tr data-k="${k}" class="${k === recSel ? "sel" : ""}"><td class="r">${r[0]}</td><td><b>${r[1]}</b></td>` +
        `<td><div class="inbar"><i style="width:${(100 * r[2]) / recs[0][2]}%"></i><span class="num">${r[2]}</span></div></td>` +
        `<td class="r">${fmt(r[3], 2)}</td><td>${r[4] ? '<span class="badge yes">✓ Yes</span>' : '<span class="badge">– No</span>'}</td>` +
        `<td class="ink2">${r[5].join(", ")}${r[2] > r[5].length ? ", …" : ""}</td></tr>`).join("") + "</tbody></table>"
      : `<p class="ink2" style="padding:12px">No suggestions: none of this user's friends have friends they don't know yet.</p>`;
    $("r-table").querySelectorAll("[data-k]").forEach((tr) => tr.addEventListener("click", () => { recSel = +tr.dataset.k; renderRecs(); }));
    renderWhy();
    tiles($("r-tiles"), [
      ["Users with suggestions", fmt(recStats.users), `of ${fmt(N)}, computed by Spark for everyone`],
      ["Suggestions in own community", pct(recStats.same / recStats.n, 0), "recommendations and communities agree"],
      ["Mutual friends, #1 suggestion", fmt(recStats.topMutual, 1), "on average over all users"],
    ]);
  }

  /** Diagram: the user on the left, the suggestion on the right, mutual friends in between. */
  function renderWhy() {
    const i = recUser, r = (D.recs[i] || [])[recSel], el = $("w-svg");
    if (!r) { el.innerHTML = ""; $("w-title").textContent = "Why this suggestion?"; return; }
    const c = index.get(r[1]), mutual = mutualFriends(i, c), MAX = 10, shown = mutual.slice(0, MAX);
    $("w-title").innerHTML = `Why suggest ${r[1]} to ${U.id[i]}?`;
    $("w-sub").innerHTML = `They have <b>${mutual.length} mutual friends</b>. Mutual friends with few friends of their own
      count most for Adamic-Adar, so they are listed first.`;
    const W = Math.max(300, el.clientWidth || 420), rowH = 30, H = Math.max(200, shown.length * rowH + 60);
    const ax = 50, bx = W - 50, mx = W / 2, cy = H / 2, top = (H - (shown.length - 1) * rowH) / 2;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="mutual friends diagram">`;
    shown.forEach((m, k) => {
      const y = top + k * rowH;
      s += `<path d="M${ax},${cy} C${(ax + mx) / 2},${cy} ${(ax + mx) / 2},${y} ${mx},${y} C${(mx + bx) / 2},${y} ${(mx + bx) / 2},${cy} ${bx},${cy}" fill="none" stroke="${pal.slots[1]}" stroke-opacity="0.45" stroke-width="1.5"/>`;
    });
    shown.forEach((m, k) => {
      const y = top + k * rowH;
      s += `<circle cx="${mx}" cy="${y}" r="6" fill="${commColor(U.community[m])}" stroke="${pal.surface}" stroke-width="2"/>`;
      s += `<text x="${mx + 12}" y="${y + 4}" style="paint-order:stroke;stroke:${pal.surface};stroke-width:3px">${U.id[m]} · ${fmt(U.degree[m])} friends</text>`;
    });
    if (mutual.length > MAX) s += `<text x="${mx}" y="${H - 8}" text-anchor="middle">+ ${mutual.length - MAX} more mutual friends</text>`;
    [[ax, i, "User"], [bx, c, "Suggest"]].forEach(([x, u, t]) => {
      s += `<circle cx="${x}" cy="${cy}" r="14" fill="${commColor(U.community[u])}" stroke="${pal.ink}" stroke-width="2"/>`;
      s += `<text class="name" x="${x}" y="${cy + 32}" text-anchor="middle">${U.id[u]}</text><text x="${x}" y="${cy - 22}" text-anchor="middle">${t}</text>`;
    });
    el.innerHTML = s + "</svg>";
  }

  // =====================================================================
  // 6. How it works
  // =====================================================================
  function renderHow() {
    const runs = [["1 laptop", 121], ["2 laptops", 362], ["3 laptops", 443]];   // README section 6.5
    hbars($("how-times"), runs.map(([l, v]) => ({ label: l, value: v, valueText: `${v} s`, color: pal.accent,
      tip: `<b>${l}</b>` + row("All 5 jobs", `${v} s`) })), { labelValues: "all", labelWidth: 90, rowH: 34, aria: "pipeline time per cluster size" });
  }

  showTab(location.hash.slice(1) || "overview");
  addEventListener("hashchange", () => showTab(location.hash.slice(1)));
})();
