(function () {
  "use strict";
  const D = window.SSP, M = D.meta, S = D.students;
  const RISK_COL = { High: "#B3392F", Medium: "#D9A021", Low: "#3F7D5C" };
  const BAND_COL = { Critical: "#B3392F", Watch: "#D9A021", Good: "#8DBBA9", Excellent: "#1E4D40" };
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const avg = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);
  const f1 = (x) => (x == null ? "-" : (+x).toFixed(1));
  const st = { dept: "All", year: "All", risk: "All", seg: "All", q: "", sort: "priority", dir: -1, shown: 50 };

  // ---------- filters ----------
  const uniq = (k) => [...new Set(S.map((s) => s[k]))].sort();
  function fill(id, label, vals) {
    $(id).innerHTML = [`All`, ...vals].map((v) => `<option value="${esc(v)}">${v === "All" ? "All " + label : esc(v)}</option>`).join("");
  }
  fill("f-dept", "departments", uniq("dept"));
  fill("f-year", "years", uniq("year"));
  fill("f-risk", "risk levels", ["High", "Medium", "Low"]);
  fill("f-seg", "segments", Object.keys(M.segments));
  const bind = [["f-dept", "dept"], ["f-year", "year"], ["f-risk", "risk"], ["f-seg", "seg"]];
  bind.forEach(([id, k]) => $(id).addEventListener("change", (e) => { st[k] = e.target.value; st.shown = 50; render(); }));
  $("f-q").addEventListener("input", (e) => { st.q = e.target.value.trim().toLowerCase(); st.shown = 50; render(); });
  $("f-reset").addEventListener("click", () => {
    Object.assign(st, { dept: "All", year: "All", risk: "All", seg: "All", q: "", shown: 50 });
    bind.forEach(([id]) => ($(id).value = "All")); $("f-q").value = ""; render();
  });
  function setFilter(k, v) { st[k] = st[k] === v ? "All" : v; $({ dept: "f-dept", seg: "f-seg", risk: "f-risk" }[k]).value = st[k]; render(); }

  const rows = () => S.filter((s) =>
    (st.dept === "All" || s.dept === st.dept) && (st.year === "All" || String(s.year) === String(st.year)) &&
    (st.risk === "All" || s.risk === st.risk) && (st.seg === "All" || s.segment === st.seg) &&
    (!st.q || s.name.toLowerCase().includes(st.q) || s.id.toLowerCase().includes(st.q)));

  // ---------- tabs ----------
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-selected", x === b));
    document.querySelectorAll(".panel").forEach((p) => (p.hidden = p.id !== "tab-" + b.dataset.tab));
  }));

  // ---------- svg helpers ----------
  const svg = (w, h, inner) => `<svg viewBox="0 0 ${w} ${h}" role="img">${inner}</svg>`;
  const tx = (x, y, t, o = "") => `<text x="${x}" y="${y}" ${o}>${esc(t)}</text>`;

  function hist(R) {
    const W = 640, H = 230, L = 34, B = 28, bins = Array(20).fill(0);
    R.forEach((s) => bins[Math.min(19, Math.floor(s.score / 5))]++);
    const mx = Math.max(1, ...bins), bw = (W - L - 8) / 20;
    let o = "";
    bins.forEach((c, i) => {
      const h = (c / mx) * (H - B - 14), lo = i * 5;
      const b = M.bands.find((x) => lo >= x.min).name;
      o += `<rect x="${L + i * bw + 1}" y="${H - B - h}" width="${bw - 2}" height="${h}" fill="${BAND_COL[b]}"><title>${lo} to ${lo + 4}: ${c} students</title></rect>`;
      if (i % 2 === 0) o += tx(L + i * bw, H - 10, lo, 'class="mut"');
    });
    o += `<line x1="${L}" x2="${W}" y1="${H - B}" y2="${H - B}" stroke="#999"/>` + tx(2, 14, mx, 'class="mut"');
    let lx = 300;
    ["Critical", "Watch", "Good", "Excellent"].forEach((b) => { o += `<rect x="${lx}" y="0" width="10" height="10" fill="${BAND_COL[b]}"/>` + tx(lx + 14, 9, b); lx += 80; });
    $("c-hist").innerHTML = svg(W, H, o);
  }

  function hbars(el, items, click) {
    const W = 340, rh = 44, H = items.length * rh + 4, mx = Math.max(1, ...items.map((i) => i.v));
    let o = "";
    items.forEach((it, i) => {
      const y = i * rh, w = (it.v / mx) * 270;
      o += `<g ${click ? `data-k="${esc(it.k)}" style="cursor:pointer"` : ""}><title>${esc(it.k)}: ${it.v}</title>` +
        tx(0, y + 14, it.k, it.on ? 'font-weight="700"' : "") +
        `<rect x="0" y="${y + 20}" width="${Math.max(2, w)}" height="14" fill="${it.on ? "#1E4D40" : "#2F6F5E"}"/>` +
        tx(Math.max(2, w) + 6, y + 32, it.v, 'class="mut"') + `</g>`;
    });
    $(el).innerHTML = svg(W, H, o);
    if (click) $(el).querySelectorAll("g[data-k]").forEach((g) => g.addEventListener("click", () => click(g.dataset.k)));
  }

  function deptStack(R) {
    const depts = uniq("dept"), W = 340, rh = 34;
    let o = "";
    depts.forEach((d, i) => {
      const g = R.filter((s) => s.dept === d), n = g.length || 1, y = i * rh;
      let x = 56;
      o += `<g data-k="${d}" style="cursor:pointer">` + tx(0, y + 20, d, st.dept === d ? 'font-weight="700"' : "");
      ["High", "Medium", "Low"].forEach((r) => {
        const c = g.filter((s) => s.risk === r).length, w = (c / n) * 270;
        o += `<rect x="${x}" y="${y + 6}" width="${w}" height="18" fill="${RISK_COL[r]}"><title>${d} ${r}: ${c} (${Math.round((c / n) * 100)}%)</title></rect>`;
        if (w > 28) o += tx(x + 4, y + 19, Math.round((c / n) * 100) + "%", 'fill="#fff" style="fill:#fff"');
        x += w;
      });
      o += "</g>";
    });
    const y0 = depts.length * rh + 6;
    let lx = 56;
    ["High", "Medium", "Low"].forEach((r) => { o += `<rect x="${lx}" y="${y0}" width="10" height="10" fill="${RISK_COL[r]}"/>` + tx(lx + 14, y0 + 9, r); lx += 70; });
    $("c-dept").innerHTML = svg(W, y0 + 16, o);
    $("c-dept").querySelectorAll("g[data-k]").forEach((g) => g.addEventListener("click", () => setFilter("dept", g.dataset.k)));
  }

  function scatter(R) {
    const W = 640, H = 300, L = 40, B = 32, T = 8, R_ = 10;
    const X = (a) => L + ((a - 30) / 70) * (W - L - R_), Y = (c) => H - B - ((c - 3) / 7) * (H - B - T);
    let o = "";
    [40, 50, 60, 70, 80, 90].forEach((a) => (o += tx(X(a) - 10, H - 14, a + "%", 'class="mut"')));
    [4, 6, 8, 10].forEach((c) => (o += tx(8, Y(c) + 4, c, 'class="mut"')));
    o += `<line x1="${X(75)}" x2="${X(75)}" y1="${T}" y2="${H - B}" stroke="#999" stroke-dasharray="4"/>` +
         `<line x1="${L}" x2="${W - R_}" y1="${Y(6)}" y2="${Y(6)}" stroke="#999" stroke-dasharray="4"/>`;
    R.slice().sort((a, b) => ({ Low: 0, Medium: 1, High: 2 }[a.risk] - { Low: 0, Medium: 1, High: 2 }[b.risk])).forEach((s) => {
      o += `<circle cx="${X(Math.max(30, s.att))}" cy="${Y(Math.max(3, s.cgpa))}" r="4" fill="${RISK_COL[s.risk]}" fill-opacity=".75" data-id="${s.id}" style="cursor:pointer"><title>${esc(s.name)}: attendance ${f1(s.att)}%, CGPA ${s.cgpa}, ${s.risk} risk</title></circle>`;
    });
    o += tx(W / 2 - 50, H - 1, "Overall attendance", 'class="mut"') + tx(W - 100, 14, "CGPA ↑", 'class="mut"');
    $("c-scatter").innerHTML = svg(W, H, o);
    $("c-scatter").querySelectorAll("circle").forEach((c) => c.addEventListener("click", () => openStudent(c.dataset.id)));
  }

  function line(el, vals, labels, color, lo, hi) {
    const W = 340, H = 190, L = 30, B = 24;
    const pts = vals.map((v, i) => [L + (i / Math.max(1, vals.length - 1)) * (W - L - 12), H - B - ((v - lo) / (hi - lo)) * (H - B - 12)]);
    let o = [lo, (lo + hi) / 2, hi].map((g) => `<line x1="${L}" x2="${W - 8}" y1="${H - B - ((g - lo) / (hi - lo)) * (H - B - 12)}" y2="${H - B - ((g - lo) / (hi - lo)) * (H - B - 12)}" stroke="#E1E6E1"/>` + tx(0, H - B - ((g - lo) / (hi - lo)) * (H - B - 12) + 4, g.toFixed(g % 1 ? 1 : 0), 'class="mut"')).join("");
    o += `<polyline fill="none" stroke="${color}" stroke-width="2.5" points="${pts.map((p) => p.join(",")).join(" ")}"/>`;
    pts.forEach((p, i) => (o += `<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="${color}"><title>${labels[i]}: ${vals[i].toFixed(2)}</title></circle>` + tx(p[0] - 8, H - 6, labels[i], 'class="mut"')));
    $(el).innerHTML = svg(W, H, o);
  }

  function trends(R) {
    const sg = [], sl = [];
    for (let i = 0; i < 7; i++) { const v = R.filter((s) => s.sgpa.length > i).map((s) => s.sgpa[i]); if (v.length) { sg.push(avg(v)); sl.push("S" + (i + 1)); } }
    if (sg.length > 1) line("c-sgpa", sg, sl, "#2F6F5E", Math.floor(Math.min(...sg) - .2), Math.ceil(Math.max(...sg) + .2));
    else $("c-sgpa").innerHTML = '<p class="sub">Not enough semesters for this selection.</p>';
    const am = M.months.map((_, i) => avg(R.filter((s) => s.att_monthly.length > i).map((s) => s.att_monthly[i])));
    if (R.length) line("c-att", am, M.months, "#B3392F", Math.floor(Math.min(...am) - 2), Math.ceil(Math.max(...am) + 2));
    else $("c-att").innerHTML = "";
  }

  function pillars(R) {
    const W = 340, rh = 30; let o = "";
    M.pillars.forEach((p, i) => {
      const a = avg(R.map((s) => s.pillars[p])), c = avg(S.map((s) => s.pillars[p])), y = i * rh;
      o += tx(0, y + 19, p) + `<rect x="90" y="${y + 6}" width="${a * 2.3}" height="16" fill="#2F6F5E"><title>${p}: ${a.toFixed(0)}</title></rect>` +
        `<line x1="${90 + c * 2.3}" x2="${90 + c * 2.3}" y1="${y + 2}" y2="${y + 26}" stroke="#172321" stroke-width="2"><title>Campus ${p}: ${c.toFixed(0)}</title></line>` + tx(96 + a * 2.3 > 300 ? 300 : 96 + a * 2.3, y + 19, a.toFixed(0), 'class="mut"');
    });
    $("c-pillar").innerHTML = svg(W, M.pillars.length * rh + 4, o);
  }

  // ---------- KPIs, insights, table ----------
  function kpis(R) {
    const n = R.length, hi = R.filter((s) => s.risk === "High").length, ph = R.filter((s) => s.plc_risk === "High").length;
    const items = [[n, "students selected"], [avg(R.map((s) => s.score)).toFixed(1), "average Success Score"],
      [hi, `high risk (${n ? Math.round((hi / n) * 100) : 0}%)`, "hot"], [ph, "high placement risk", "hot"],
      [avg(R.map((s) => s.att)).toFixed(0) + "%", "average attendance"], [avg(R.map((s) => s.cgpa)).toFixed(2), "average CGPA"]];
    $("kpis").innerHTML = items.map(([v, l, c]) => `<div class="kpi ${c || ""}"><div class="n">${v}</div><div class="l">${l}</div></div>`).join("");
    $("rail-note").innerHTML = `<b>${n}</b> of ${S.length} students match.<br>Data as of ${esc(M.generated)}.`;
  }

  const COLS = [["name", "Student"], ["dept", "Dept"], ["year", "Yr"], ["score", "Score"], ["acad_risk", "Academic risk"], ["plc_risk", "Placement risk"], ["segment", "Segment"], ["reasons", "Main reasons"]];
  function table(R) {
    const k = st.sort, d = st.dir;
    const ord = { High: 3, Medium: 2, Low: 1 };
    const val = (s) => (k === "reasons" ? (s.reasons[0] || "") : k === "acad_risk" || k === "plc_risk" ? ord[s[k]] : s[k]);
    const sorted = R.slice().sort((a, b) => { const x = val(a), y = val(b); return (x > y ? 1 : x < y ? -1 : 0) * d; });
    $("list-count").textContent = `${R.length} students, sorted by ${k === "priority" ? "intervention priority" : COLS.find((c) => c[0] === k)[1].toLowerCase()}. Click a row for the full profile.`;
    const head = `<thead><tr>${COLS.map(([c, l]) => `<th class="sortable" data-k="${c}">${l}${st.sort === c ? (st.dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead>`;
    const body = sorted.slice(0, st.shown).map((s) => `<tr class="row" data-id="${s.id}" tabindex="0"><td>${esc(s.name)}<br><small>${s.id}</small></td><td>${s.dept}</td><td>${s.year}</td>` +
      `<td><b>${s.score}</b> <span class="pill ${s.band}">${s.band}</span></td><td><span class="pill ${s.acad_risk}">${s.acad_risk}</span></td><td><span class="pill ${s.plc_risk}">${s.plc_risk}</span></td>` +
      `<td class="wrap">${esc(s.segment)}</td><td class="wrap">${esc(s.reasons[0] || "No flags")}</td></tr>`).join("");
    $("tbl").innerHTML = head + `<tbody>${body}</tbody>`;
    $("more").style.display = sorted.length > st.shown ? "" : "none";
    $("tbl").querySelectorAll("th").forEach((th) => th.addEventListener("click", () => { st.dir = st.sort === th.dataset.k ? -st.dir : -1; st.sort = th.dataset.k; table(rows()); }));
    $("tbl").querySelectorAll("tr.row").forEach((tr) => { tr.addEventListener("click", () => openStudent(tr.dataset.id)); tr.addEventListener("keydown", (e) => { if (e.key === "Enter") openStudent(tr.dataset.id); }); });
  }
  $("more").addEventListener("click", () => { st.shown += 100; table(rows()); });
  $("export").addEventListener("click", () => {
    const R = rows(), h = ["id", "name", "dept", "year", "score", "band", "risk", "acad_risk", "plc_risk", "segment", "reasons", "actions"];
    const q = (v) => `"${String(Array.isArray(v) ? v.join("; ") : v).replace(/"/g, '""')}"`;
    const csv = [h.join(","), ...R.map((s) => h.map((k) => q(s[k])).join(","))].join("\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); a.download = "intervention_list.csv"; a.click();
  });

  // ---------- student drawer with explainable score ----------
  function driverChart(s) {
    const items = M.indicators.map((ind, i) => ({ l: ind.label, v: s.drivers[i] })).sort((a, b) => a.v - b.v);
    const mx = Math.max(1, ...items.map((i) => Math.abs(i.v))), W = 500, rh = 24, mid = 330, scale = 130 / mx;
    let o = `<line x1="${mid}" x2="${mid}" y1="0" y2="${items.length * rh}" stroke="#172321"/>`;
    items.forEach((it, i) => {
      const y = i * rh, w = Math.abs(it.v) * scale;
      o += tx(0, y + 16, it.l) + `<rect x="${it.v < 0 ? mid - w : mid}" y="${y + 4}" width="${Math.max(1, w)}" height="14" fill="${it.v < 0 ? "#B3392F" : "#2F6F5E"}"><title>${it.l}: ${it.v > 0 ? "+" : ""}${it.v} points vs campus average</title></rect>` +
        tx(it.v < 0 ? mid - w - 30 : mid + w + 4, y + 16, (it.v > 0 ? "+" : "") + it.v, 'class="mut"');
    });
    return svg(W, items.length * rh + 2, o);
  }
  function spark(vals, fc) {
    if (!vals.length) return '<p class="sub">No semester data.</p>';
    const W = 500, H = 120, all = fc ? [...vals, fc] : vals, n = all.length;
    const X = (i) => 30 + (i / Math.max(1, n - 1)) * (W - 60), Y = (v) => H - 22 - ((v - 3) / 7) * (H - 40);
    let o = `<polyline fill="none" stroke="#2F6F5E" stroke-width="2.5" points="${vals.map((v, i) => X(i) + "," + Y(v)).join(" ")}"/>`;
    vals.forEach((v, i) => (o += `<circle cx="${X(i)}" cy="${Y(v)}" r="3.5" fill="#2F6F5E"/>` + tx(X(i) - 12, Y(v) - 8, v.toFixed(1), 'class="mut"') + tx(X(i) - 6, H - 4, "S" + (i + 1), 'class="mut"')));
    if (fc) o += `<line x1="${X(vals.length - 1)}" y1="${Y(vals[vals.length - 1])}" x2="${X(n - 1)}" y2="${Y(fc)}" stroke="#D9A021" stroke-width="2.5" stroke-dasharray="5"/><circle cx="${X(n - 1)}" cy="${Y(fc)}" r="4" fill="#D9A021"/>` + tx(X(n - 1) - 20, Y(fc) - 8, "next " + fc.toFixed(1), 'class="mut"');
    return svg(W, H, o);
  }
  function openStudent(id) {
    const s = S.find((x) => x.id === id); if (!s) return;
    const subj = Object.entries(s.subjects).sort((a, b) => a[1] - b[1]);
    $("drawer-body").innerHTML = `
      <div class="dh"><div><h2>${esc(s.name)}</h2><span class="sub">${s.id} · ${s.dept} · Year ${s.year}</span></div></div>
      <div class="scorebox"><div class="big">${s.score}</div><div><span class="pill ${s.band}">${s.band}</span><div class="sub">Student Success Score (campus average ${f1(avg(S.map((x) => x.score)))})</div></div></div>
      <div class="tags"><span class="pill ${s.acad_risk}">Academic risk: ${s.acad_risk}</span><span class="pill ${s.plc_risk}">Placement risk: ${s.plc_risk}</span></div>
      <p class="sub">Segment: <b>${esc(s.segment)}</b>. ${esc(M.segments[s.segment].what)}</p>
      <div class="dsec"><h3>Why this student is flagged</h3>${s.reasons.length ? `<ul class="plain">${s.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : '<p class="sub">No risk rules triggered.</p>'}</div>
      <div class="dsec"><h3>Suggested actions</h3>${s.actions.length ? `<ul class="plain">${s.actions.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : '<p class="sub">Keep monitoring; consider stretch opportunities.</p>'}</div>
      <div class="dsec"><h3>What moves the score</h3><p class="sub">Points each indicator adds (green) or costs (red) compared with the campus average.</p>${driverChart(s)}</div>
      <div class="dsec"><h3>Semester GPA${s.forecast != null ? " and forecast" : ""}</h3>${spark(s.sgpa, s.forecast)}</div>
      <div class="dsec"><h3>Snapshot</h3><div class="mini">
        <div><b>${s.cgpa}</b><span>CGPA</span></div><div><b>${f1(s.att)}%</b><span>Attendance</span></div><div><b>${s.backlogs}</b><span>Backlogs</span></div>
        <div><b>${f1(s.assign)}%</b><span>LMS assignments</span></div><div><b>${f1(s.coding)}</b><span>Coding</span></div><div><b>${f1(s.apt)}</b><span>Aptitude</span></div>
        <div><b>${f1(s.mock)}</b><span>Mock interview</span></div><div><b>${s.hack}/${s.certs}</b><span>Hackathons / certs</span></div><div><b>${Math.round(s.completeness * 100)}%</b><span>Data completeness</span></div></div></div>
      ${subj.length ? `<div class="dsec"><h3>Subject marks</h3><p class="sub">Weakest: ${esc(subj[0][0])} (${subj[0][1]}). Strongest: ${esc(subj[subj.length - 1][0])} (${subj[subj.length - 1][1]}).</p></div>` : ""}`;
    $("drawer").classList.add("on"); $("scrim").classList.add("on"); $("drawer").setAttribute("aria-hidden", "false"); $("close").focus();
  }
  const closeD = () => { $("drawer").classList.remove("on"); $("scrim").classList.remove("on"); $("drawer").setAttribute("aria-hidden", "true"); };
  $("close").addEventListener("click", closeD); $("scrim").addEventListener("click", closeD);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeD(); });

  // ---------- static tabs ----------
  function staticTabs() {
    $("insights").innerHTML = D.insights.map((t) => `<li>${esc(t)}</li>`).join("");
    const cols = [["source", "Source"], ["rows_raw", "Raw rows"], ["ids_standardised", "IDs fixed"], ["duplicates_removed", "Duplicates removed"], ["orphans_dropped", "Unmatched IDs dropped"], ["outliers_fixed", "Outliers fixed"], ["students_missing", "Students missing"], ["cells_imputed", "Cells imputed"], ["rows_clean", "Clean rows"]];
    $("dq").innerHTML = `<thead><tr>${cols.map((c) => `<th>${c[1]}</th>`).join("")}</tr></thead><tbody>${D.dq.map((r) => `<tr>${cols.map((c) => `<td>${r[c[0]] ?? 0}</td>`).join("")}</tr>`).join("")}</tbody>
      <tfoot><tr><td colspan="9" class="sub">Average data completeness per student: ${(avg(S.map((s) => s.completeness)) * 100).toFixed(1)}%</td></tr></tfoot>`;
    $("weights").innerHTML = M.indicators.map((i) => `<div class="wrow"><span>${esc(i.label)}</span><div class="wbar"><i style="width:${i.weight * 600}%"></i></div><b>${Math.round(i.weight * 100)}%</b><span class="sub">${i.pillar}</span></div>`).join("");
    $("r-acad").innerHTML = M.rule_text.academic.map((t) => `<li>${esc(t)}</li>`).join("");
    $("r-plc").innerHTML = M.rule_text.placement.map((t) => `<li>${esc(t)}</li>`).join("");
    $("r-acad-t").textContent = `High at ${M.thresholds.acad_high}+ points, Medium at ${M.thresholds.acad_med}+.`;
    $("r-plc-t").textContent = `High at ${M.thresholds.plc_high}+ points, Medium at ${M.thresholds.plc_med}+. Placement readiness = 30% aptitude + 40% coding + 30% mock interview.`;
    $("seg-tbl").innerHTML = `<thead><tr><th>Segment</th><th>Who they are</th><th>Targeted action</th><th>Students</th></tr></thead><tbody>${Object.entries(M.segments).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="wrap">${esc(v.what)}</td><td class="wrap">${esc(v.action)}</td><td>${S.filter((s) => s.segment === k).length}</td></tr>`).join("")}</tbody>`;
  }

  function render() {
    const R = rows();
    kpis(R); hist(R); deptStack(R); scatter(R); trends(R); pillars(R); table(R);
    const sc = Object.keys(M.segments).map((k) => ({ k, v: R.filter((s) => s.segment === k).length, on: st.seg === k }));
    hbars("c-seg", sc, (k) => setFilter("seg", k));
  }
  staticTabs(); render();
})();
