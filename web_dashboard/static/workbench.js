"use strict";
const byId = (id) => document.getElementById(id);
const methods = {tfidf: "TF-IDF · Keyword", minilm: "MiniLM · Semantic"};
const notes = {
  tfidf: "TF-IDF compares weighted terms and phrases shared by the prepared resume and job description. It only sees exact words, so it rewards keyword overlap and misses paraphrased experience.",
  minilm: "MiniLM encodes both texts and compares their embeddings. Its score summarizes how similar the texts are in meaning, so it can catch paraphrased or related experience TF-IDF misses — at the cost of being slower and harder to explain term-by-term."
};
let result = null;
let live = false;
let matchingIds = null;
let jobsById = new Map();
let skillTerms = [];
let labels = new Map();
const candidateName = (id) => labels.get(id) || id;

async function api(path, options) {
  const response = await fetch(path, {...options, cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The request failed.");
  return data;
}
function status(message, error = false, busy = false) {
  byId("status").textContent = message;
  byId("status").classList.toggle("error", error);
  byId("status").classList.toggle("busy", busy);
  byId("scan-progress").hidden = !busy;
}
function showView(id) {
  for (const tab of document.querySelectorAll(".tab")) {
    const selected = tab.dataset.view === id;
    tab.classList.toggle("chosen", selected);
    tab.setAttribute("aria-pressed", String(selected));
    byId(tab.dataset.view).hidden = !selected;
  }
  const pane = byId(id);
  pane.classList.remove("enter");
  void pane.offsetWidth;
  pane.classList.add("enter");
  if (id === "agents") loadAgents();
  if (id === "audits") loadAudits();
}
for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => showView(tab.dataset.view));
}

function renderRanking() {
  const method = byId("method").value;
  const cohort = result?.scores?.filter((row) => row.model_name === method) || [];
  const matches = matchingIds ? cohort.filter((row) => matchingIds.has(row.resume_id)) : cohort;
  const rows = matches.slice(0, 20);
  byId("search-form").hidden = !cohort.length;
  if (matchingIds) {
    byId("search-status").textContent = `${matches.length} matches · showing ${rows.length}`;
    byId("empty").textContent = "No candidates match this search.";
  }
  renderCharts(cohort);
  const body = byId("scores");
  body.replaceChildren();
  for (const row of rows) {
    const tr = body.insertRow();
    tr.insertCell().textContent = row.rank_position;
    const candidate = document.createElement("button");
    candidate.type = "button";
    candidate.className = "candidate-link";
    candidate.textContent = candidateName(row.resume_id);
    candidate.title = row.resume_id;
    candidate.addEventListener("click", () => showCandidate(row));
    tr.insertCell().append(candidate);
    const group = document.createElement("span");
    group.className = "chip" + (row.domain_group === "control" ? " control" : "");
    group.textContent = row.domain_group === "tech_data_proxy" ? "Tech/data" : row.domain_group === "control" ? "Control" : "—";
    tr.insertCell().append(group);
    const score = Number(row.similarity_score);
    const cell = document.createElement("div");
    cell.className = "score";
    tr.insertCell().append(cell);
    const number = document.createElement("span");
    number.textContent = asPercent(score);
    const track = document.createElement("span");
    track.className = "track";
    track.setAttribute("aria-hidden", "true");
    const fill = document.createElement("span");
    fill.className = "fill";
    fill.style.width = (score * 100) + "%";
    track.append(fill);
    cell.append(number, track);
  }
  byId("table-wrap").hidden = rows.length === 0;
  byId("empty").hidden = rows.length > 0;
  byId("why").hidden = rows.length === 0;
  byId("method-note").textContent = notes[method] || "";
}
byId("method").addEventListener("change", renderRanking);
byId("analytics-method").addEventListener("change", () => {
  byId("method").value = byId("analytics-method").value;
  renderRanking();
});

function countUp(el, target) {
  if (!Number.isFinite(target)) { el.textContent = "—"; return; }
  const start = Number(el.textContent) || 0;
  const duration = 500;
  const startTime = performance.now();
  function tick(now) {
    const progress = Math.min(1, (now - startTime) / duration);
    el.textContent = Math.round(start + (target - start) * progress);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function addRow(container, values) {
  const row = container.insertRow();
  for (const value of values) row.insertCell().textContent = value;
  return row;
}

// --- inline SVG charts: a hairline track, a rounded single-hue bar, a hover/focus tooltip ---
function vizTooltip(container) {
  let tooltip = container.querySelector(".viz-tooltip");
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.className = "viz-tooltip";
    tooltip.hidden = true;
    container.append(tooltip);
  }
  return tooltip;
}
function showTooltip(container, target, valueText, labelText) {
  const tooltip = vizTooltip(container);
  const value = document.createElement("strong");
  value.textContent = valueText;
  const label = document.createElement("span");
  label.textContent = labelText;
  tooltip.replaceChildren(value, label);
  const box = target.getBoundingClientRect();
  const origin = container.getBoundingClientRect();
  tooltip.style.left = (box.left - origin.left + box.width / 2) + "px";
  tooltip.style.top = (box.top - origin.top) + "px";
  tooltip.hidden = false;
}
function hideTooltip(container) {
  const tooltip = container.querySelector(".viz-tooltip");
  if (tooltip) tooltip.hidden = true;
}

function growBar(rect, attr, finalValue) {
  rect.setAttribute(attr, "0");
  requestAnimationFrame(() => requestAnimationFrame(() => rect.setAttribute(attr, String(finalValue))));
}

function barRow(label, count, total) {
  const row = document.createElement("div");
  row.className = "chart-row";
  row.tabIndex = 0;
  const name = document.createElement("span");
  name.className = "viz-label";
  name.textContent = label;
  const pct = total ? (100 * count / total) : 0;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 100 10");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${label}: ${count}`);
  const track = document.createElementNS(svg.namespaceURI, "rect");
  track.setAttribute("class", "viz-gridline");
  track.setAttribute("x", "0"); track.setAttribute("y", "3");
  track.setAttribute("width", "100"); track.setAttribute("height", "4"); track.setAttribute("rx", "2");
  const bar = document.createElementNS(svg.namespaceURI, "rect");
  bar.setAttribute("class", "viz-bar");
  bar.setAttribute("x", "0"); bar.setAttribute("y", "3");
  bar.setAttribute("height", "4"); bar.setAttribute("rx", "2");
  svg.append(track, bar);
  growBar(bar, "width", pct);
  const value = document.createElement("span");
  value.className = "viz-value";
  value.textContent = count;
  row.append(name, svg, value);
  const onEnter = () => showTooltip(row.closest(".viz"), row, String(count), label);
  const onLeave = () => hideTooltip(row.closest(".viz"));
  row.addEventListener("mouseenter", onEnter);
  row.addEventListener("focus", onEnter);
  row.addEventListener("mouseleave", onLeave);
  row.addEventListener("blur", onLeave);
  return row;
}

function renderMagnitudeChart(container, rows, total) {
  container.replaceChildren();
  if (!total) {
    const empty = document.createElement("p");
    empty.className = "viz-empty";
    empty.textContent = "Load rankings to see this chart.";
    container.append(empty);
    return;
  }
  for (const {label, count} of rows) container.append(barRow(label, count, total));
}

const DONUT_COLORS = ["var(--blue)", "var(--orange)", "var(--chart-red)", "var(--dim)"];

function foldToOther(segments, cap = 4) {
  if (segments.length <= cap) return segments;
  const kept = segments.slice(0, cap - 1);
  const rest = segments.slice(cap - 1).reduce((sum, s) => sum + s.value, 0);
  return [...kept, {label: "Other", value: rest}];
}

// A donut is appropriate here (unlike the 5-bin score distribution): both callers are a
// genuine small part-to-whole composition (<=4 slices after folding), not a magnitude
// comparison or a continuous scale, so it doesn't fall into the pie/donut anti-pattern.
function renderDonut(container, legendContainer, rawSegments, {emptyMessage, ariaLabel}) {
  container.replaceChildren();
  legendContainer.replaceChildren();
  legendContainer.hidden = true;
  const total = rawSegments.reduce((sum, s) => sum + s.value, 0);
  if (!total) {
    const empty = document.createElement("p");
    empty.className = "viz-empty";
    empty.textContent = emptyMessage;
    container.append(empty);
    return;
  }
  const segments = foldToOther(rawSegments).map((s, i) => ({...s, color: DONUT_COLORS[i]}));
  const r = 38, gap = 1.5, circumference = 2 * Math.PI * r;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", ariaLabel);
  const group = document.createElementNS(svg.namespaceURI, "g");
  group.setAttribute("transform", "rotate(-90 50 50)");
  const track = document.createElementNS(svg.namespaceURI, "circle");
  track.setAttribute("class", "viz-gridline");
  track.setAttribute("cx", "50"); track.setAttribute("cy", "50"); track.setAttribute("r", String(r));
  track.setAttribute("fill", "none"); track.setAttribute("stroke-width", "16");
  group.append(track);
  let cumulative = 0;
  for (const segment of segments) {
    const length = Math.max(0, (segment.value / total) * circumference - (segment.value ? gap : 0));
    const circle = document.createElementNS(svg.namespaceURI, "circle");
    circle.setAttribute("cx", "50"); circle.setAttribute("cy", "50"); circle.setAttribute("r", String(r));
    circle.setAttribute("fill", "none"); circle.setAttribute("stroke-width", "16");
    circle.setAttribute("stroke", segment.color);
    circle.setAttribute("stroke-dasharray", `0 ${circumference}`);
    circle.setAttribute("stroke-dashoffset", String(-cumulative));
    circle.setAttribute("tabindex", "0");
    const percent = Math.round(segment.value / total * 100);
    circle.addEventListener("mouseenter", () => showTooltip(container, circle, `${segment.value} (${percent}%)`, segment.label));
    circle.addEventListener("focus", () => showTooltip(container, circle, `${segment.value} (${percent}%)`, segment.label));
    circle.addEventListener("mouseleave", () => hideTooltip(container));
    circle.addEventListener("blur", () => hideTooltip(container));
    group.append(circle);
    requestAnimationFrame(() => requestAnimationFrame(() =>
      circle.setAttribute("stroke-dasharray", `${length} ${circumference - length}`)));
    cumulative += (segment.value / total) * circumference;
  }
  svg.append(group);
  const center = document.createElementNS(svg.namespaceURI, "text");
  center.setAttribute("x", "50"); center.setAttribute("y", "54"); center.setAttribute("text-anchor", "middle");
  center.setAttribute("class", "viz-value"); center.setAttribute("font-size", "13");
  center.textContent = total;
  svg.append(center);
  container.append(svg);
  legendContainer.hidden = false;
  for (const segment of segments) {
    const item = document.createElement("span");
    item.className = "viz-legend-item";
    const swatch = document.createElement("span");
    swatch.className = "viz-legend-swatch";
    swatch.style.background = segment.color;
    const text = document.createElement("span");
    text.textContent = `${segment.label} (${segment.value})`;
    item.append(swatch, text);
    legendContainer.append(item);
  }
}

function renderTiles(container, kpis) {
  container.replaceChildren(...kpis.map(([name, value, note]) => {
    const tile = document.createElement("div");
    tile.className = "tile";
    const label = document.createElement("span");
    label.textContent = name;
    const strong = document.createElement("strong");
    strong.textContent = value;
    const small = document.createElement("small");
    small.textContent = note;
    tile.append(label, strong, small);
    return tile;
  }));
}

function renderCharts(rows) {
  const method = byId("method").value;
  byId("analytics-method").value = method;
  byId("analytics-body").hidden = !rows.length;
  byId("analytics-context").textContent = rows.length
    ? `${result.job_title} · ${methods[method]} · ${rows.length} scored resumes`
    : "Load rankings to see the sample and scores.";
  if (!rows.length) return;
  const scores = rows.map((row) => Number(row.similarity_score));
  const skipped = result.skipped_resume_count ?? 0;
  const overlapNow = overlapSummary(result.scores);
  const agreement = rankCorrelation(result.scores);
  const techTop = rows.filter((row) => row.rank_position <= 20 && row.domain_group === "tech_data_proxy").length;
  const kpis = [
    ["Median match", asPercent(medianScore(rows)), `${methods[method]} · all ${rows.length} resumes`],
    ["Top 20 from tech/data", `${techTop} of 20`, "Control resumes should not reach the top"],
    ["Picked by both models", overlapNow.comparable ? `${overlapNow.shared} of 20` : "—", "Overlap of the two top-20 lists"],
    ["Rank agreement", agreement == null ? "—" : agreement.toFixed(2), "Spearman: 1 = same order, 0 = unrelated, −1 = opposite"],
  ];
  const summary = byId("score-summary");
  const controlTop = Math.min(20, rows.length) - techTop;
  summary.textContent = analyticsVerdict({agreement, shared: overlapNow.shared, controlTop});
  summary.classList.toggle("caution", controlTop > 0 || (agreement != null && agreement < 0.2));
  byId("score-range").textContent = `${methods[method]} scores for this job run from ${asPercent(Math.min(...scores))} to ${asPercent(Math.max(...scores))} match. Scores measure text similarity, not hiring probability, and the two methods use different scales, so compare ranks rather than raw scores. ${skipped} resumes skipped.`;
  renderTiles(byId("analytics-kpis"), kpis);
  renderMagnitudeChart(byId("distribution"), binScores(rows), rows.length);
  renderDonut(byId("source-mix"), byId("source-mix-legend"),
    sourceMix(rows).map((s) => ({label: s.label, value: s.count})),
    {emptyMessage: "Load rankings to see this chart.", ariaLabel: "Resumes by source dataset"});
  const breakdown = byId("group-results");
  breakdown.replaceChildren();
  for (const group of groupBreakdown(rows)) {
    addRow(breakdown, [group.label, `${group.count} (${group.sharePercent}%)`, asPercent(group.medianScore), group.topCount]);
  }
  renderOverlap();
  renderScoreSpace();
}

// MATLAB-surf-style density surface: height = how many resumes landed at that
// TF-IDF/MiniLM score combination. Projected and painter-sorted by hand (no 3D library)
// since this is a single slowly-rotated view, not a physically-lit scene.
let scoreSpaceRotation = {x: -32, y: -40};
const VIRIDIS = [[68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]];
function viridis(t) {
  const scaled = Math.max(0, Math.min(1, t)) * (VIRIDIS.length - 1);
  const i = Math.min(VIRIDIS.length - 2, Math.floor(scaled));
  const f = scaled - i;
  const mix = (a, b) => Math.round(a + (b - a) * f);
  const [r1, g1, b1] = VIRIDIS[i], [r2, g2, b2] = VIRIDIS[i + 1];
  return `rgb(${mix(r1, r2)}, ${mix(g1, g2)}, ${mix(b1, b2)})`;
}
function scoreSpaceProject(x, y, z) {
  const ry = scoreSpaceRotation.y * Math.PI / 180, rx = scoreSpaceRotation.x * Math.PI / 180;
  const x1 = x * Math.cos(ry) - z * Math.sin(ry);
  const z1 = x * Math.sin(ry) + z * Math.cos(ry);
  const y2 = y * Math.cos(rx) - z1 * Math.sin(rx);
  const depth = y * Math.sin(rx) + z1 * Math.cos(rx);
  return {sx: x1, sy: -y2, depth};
}
function svgEl(tag, attrs) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
}
const SCORE_SPACE_BINS = 12, SCORE_SPACE_HALF = 50, SCORE_SPACE_HEIGHT = 55;
function renderScoreSpace() {
  const scene = byId("score-space-scene");
  const legend = byId("score-space-legend");
  scene.replaceChildren();
  legend.replaceChildren();
  legend.hidden = true;
  const points = rankFractions(result.scores, result.resume_count || 0);
  if (!points.length) {
    const empty = document.createElement("p");
    empty.className = "viz-empty";
    empty.textContent = "Load a run scored with both models to see this.";
    scene.append(empty);
    return;
  }
  const {grid, maxCount} = densityGrid(points, SCORE_SPACE_BINS, SCORE_SPACE_BINS);
  const cell = (2 * SCORE_SPACE_HALF) / SCORE_SPACE_BINS;
  const toLocal = (i) => -SCORE_SPACE_HALF + i * cell;
  const svg = svgEl("svg", {viewBox: "-105 -75 210 150"});

  const floor = svgEl("g", {});
  for (let s = 0; s <= 5; s++) {
    const t = toLocal(s * SCORE_SPACE_BINS / 5);
    const a = scoreSpaceProject(t, 0, -SCORE_SPACE_HALF), b = scoreSpaceProject(t, 0, SCORE_SPACE_HALF);
    floor.append(svgEl("line", {class: "score-space-grid", x1: a.sx, y1: a.sy, x2: b.sx, y2: b.sy}));
    const c = scoreSpaceProject(-SCORE_SPACE_HALF, 0, t), d = scoreSpaceProject(SCORE_SPACE_HALF, 0, t);
    floor.append(svgEl("line", {class: "score-space-grid", x1: c.sx, y1: c.sy, x2: d.sx, y2: d.sy}));
  }
  svg.append(floor);

  const N = SCORE_SPACE_BINS;
  const vertex = (i, j) => {
    let sum = 0, n = 0;
    for (const [ci, cj] of [[i - 1, j - 1], [i, j - 1], [i - 1, j], [i, j]]) {
      if (ci >= 0 && ci < N && cj >= 0 && cj < N) { sum += grid[cj][ci]; n++; }
    }
    return sum / n / maxCount;
  };
  const quads = [];
  for (let j = 0; j < N; j++) {
    for (let i = 0; i < N; i++) {
      const levels = [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]].map(([vi, vj]) => [vi, vj, vertex(vi, vj)]);
      const corners = levels.map(([vi, vj, level]) => scoreSpaceProject(toLocal(vi), level * SCORE_SPACE_HEIGHT, toLocal(vj)));
      quads.push({corners, depth: corners.reduce((sum, c) => sum + c.depth, 0) / 4,
        color: viridis(levels.reduce((sum, l) => sum + l[2], 0) / 4)});
    }
  }
  quads.sort((a, b) => a.depth - b.depth);
  for (const quad of quads) {
    const pts = quad.corners.map((c) => `${c.sx},${c.sy}`).join(" ");
    svg.append(svgEl("polygon", {class: "score-space-quad", points: pts, fill: quad.color}));
  }

  // Put tick labels on the floor edges nearest the viewer and the count axis on the
  // left-most corner, so labels sit outside the surface at any rotation.
  const H = SCORE_SPACE_HALF;
  const nearZ = scoreSpaceProject(0, 0, H).sy > scoreSpaceProject(0, 0, -H).sy ? H : -H;
  const nearX = scoreSpaceProject(H, 0, 0).sy > scoreSpaceProject(-H, 0, 0).sy ? H : -H;
  const outward = (p, distance) => {
    const length = Math.hypot(p.sx, p.sy) || 1;
    return {x: p.sx + p.sx / length * distance, y: p.sy + p.sy / length * distance + 3};
  };
  const text = (cls, pos, content, anchor = "middle") => {
    const label = svgEl("text", {class: cls, x: pos.x, y: pos.y, "text-anchor": anchor});
    label.textContent = content;
    svg.append(label);
  };
  // Each axis labels its own side of the plot (left or right of center), so the two
  // sets of ticks never collide where the near edges meet.
  const edgeLabels = (pointAt, title) => {
    const side = pointAt(N / 2).sx < 0 ? -1 : 1;
    const anchor = side < 0 ? "end" : "start";
    for (const [frac, name] of [[0, "worst"], [0.5, "middle"], [1, "best"]]) {
      const p = pointAt(frac * N);
      text("score-space-tick", {x: p.sx + side * 4, y: p.sy + 6}, name, anchor);
    }
    const mid = pointAt(N / 2);
    text("score-space-title", {x: mid.sx + side * 6, y: mid.sy + 16}, title, anchor);
  };
  edgeLabels((i) => scoreSpaceProject(toLocal(i), 0, nearZ), "TF-IDF rank");
  edgeLabels((i) => scoreSpaceProject(nearX, 0, toLocal(i)), "MiniLM rank");
  const corner = [[-H, -H], [-H, H], [H, -H], [H, H]]
    .map(([x, z]) => ({x, z, p: scoreSpaceProject(x, 0, z)})).sort((a, b) => a.p.sx - b.p.sx)[0];
  const axisTop = scoreSpaceProject(corner.x, SCORE_SPACE_HEIGHT, corner.z);
  svg.append(svgEl("line", {class: "score-space-grid", x1: corner.p.sx, y1: corner.p.sy, x2: axisTop.sx, y2: axisTop.sy}));
  for (const frac of [0.5, 1]) {
    const p = scoreSpaceProject(corner.x, frac * SCORE_SPACE_HEIGHT, corner.z);
    text("score-space-tick", {x: p.sx - 5, y: p.sy + 3}, String(Math.round(frac * maxCount)), "end");
  }
  text("score-space-title", {x: axisTop.sx - 5, y: axisTop.sy - 8}, "resumes per cell", "end");
  scene.append(svg);

  legend.hidden = false;
  const low = document.createElement("span");
  low.textContent = "0 resumes in a cell";
  const ramp = document.createElement("span");
  ramp.className = "viz-ramp";
  ramp.style.background = `linear-gradient(90deg, ${[0, .25, .5, .75, 1].map(viridis).join(", ")})`;
  const high = document.createElement("span");
  high.textContent = `${maxCount} resumes (busiest cell)`;
  legend.append(low, ramp, high);
}
let scoreSpaceRedrawQueued = false;
function queueScoreSpaceRedraw() {
  if (scoreSpaceRedrawQueued) return;
  scoreSpaceRedrawQueued = true;
  requestAnimationFrame(() => { scoreSpaceRedrawQueued = false; renderScoreSpace(); });
}
function setupScoreSpaceDrag() {
  const container = byId("score-space");
  let dragging = false;
  let last = {x: 0, y: 0};
  container.addEventListener("pointerdown", (event) => {
    dragging = true;
    last = {x: event.clientX, y: event.clientY};
    container.classList.add("grabbing");
    container.setPointerCapture(event.pointerId);
  });
  container.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    scoreSpaceRotation.y += (event.clientX - last.x) * 0.4;
    scoreSpaceRotation.x = Math.max(-85, Math.min(85, scoreSpaceRotation.x - (event.clientY - last.y) * 0.4));
    last = {x: event.clientX, y: event.clientY};
    queueScoreSpaceRedraw();
  });
  const stop = () => { dragging = false; container.classList.remove("grabbing"); };
  container.addEventListener("pointerup", stop);
  container.addEventListener("pointerleave", stop);
}

function renderOverlap() {
  const overlap = overlapSummary(result.scores);
  renderDonut(byId("overlap-chart"), byId("overlap-legend"), [
    {label: "Only TF-IDF top 20", value: overlap.keywordOnly},
    {label: "In both top 20s", value: overlap.shared},
    {label: "Only MiniLM top 20", value: overlap.semanticOnly},
  ], {emptyMessage: "Load a run that scored the same resumes with both models to compare ranks.",
      ariaLabel: "Top 20 overlap between TF-IDF and MiniLM"});
  const summary = byId("overlap-summary");
  const changes = byId("rank-differences");
  changes.replaceChildren();
  byId("rank-changes").hidden = true;
  if (!overlap.comparable) {
    summary.textContent = "Load a run that scored the same resumes with both models to compare ranks.";
    return;
  }
  summary.textContent = `${overlap.shared} in both lists · ${overlap.keywordOnly} only in TF-IDF · ${overlap.semanticOnly} only in MiniLM`;
  byId("rank-changes").hidden = !overlap.differences.length;
  for (const diff of overlap.differences) {
    const tr = addRow(changes, ["", diff.keywordRank, diff.semanticRank, diff.gap]);
    const link = document.createElement("button");
    link.type = "button";
    link.className = "candidate-link";
    link.textContent = candidateName(diff.resumeId);
    link.title = diff.resumeId;
    link.addEventListener("click", () => showCandidate(result.scores.find((row) => row.resume_id === diff.resumeId)));
    tr.cells[0].append(link);
  }
}

function chips(container, items, kind, emptyText) {
  container.replaceChildren();
  if (!items.length) {
    const none = document.createElement("span");
    none.className = "chip-empty";
    none.textContent = emptyText;
    container.append(none);
    return;
  }
  for (const item of items) {
    const chip = document.createElement("span");
    chip.className = "chip" + (kind ? " " + kind : "");
    chip.textContent = item;
    container.append(chip);
  }
}
function scoreCard(score) {
  const card = document.createElement("div");
  card.className = "score-card";
  const model = document.createElement("span");
  model.className = "score-card-model";
  model.textContent = methods[score.model_name] || score.model_name;
  const rank = document.createElement("strong");
  rank.textContent = `#${score.rank_position}`;
  const total = result.resume_count;
  const of = document.createElement("span");
  of.className = "score-card-of";
  of.textContent = total ? `of ${total} · top ${Math.max(1, Math.round(score.rank_position / total * 100))}%` : "";
  const track = document.createElement("span");
  track.className = "track";
  const fill = document.createElement("span");
  fill.className = "fill";
  fill.style.width = (total ? (1 - (score.rank_position - 1) / Math.max(1, total - 1)) * 100 : 0) + "%";
  track.append(fill);
  const raw = document.createElement("span");
  raw.className = "score-card-raw";
  raw.textContent = `${asPercent(score.similarity_score)} match`;
  card.append(model, rank, of, track, raw);
  return card;
}
async function showCandidate(row) {
  const dialog = byId("candidate-detail");
  const title = byId("candidate-title");
  title.textContent = candidateName(row.resume_id);
  title.dataset.id = row.resume_id;
  chips(byId("candidate-source"), [sourceLabel(row.source_dataset),
    row.domain_group === "tech_data_proxy" ? "Tech/data group" : row.domain_group === "control" ? "Control group" : "Unclassified"], "", "");
  byId("candidate-id").textContent = `Study ID ${row.resume_id}`;
  const candidateScores = result.scores.filter((item) => item.resume_id === row.resume_id)
    .sort((a, b) => a.model_name.localeCompare(b.model_name)).reverse();
  byId("candidate-scores").replaceChildren(...candidateScores.map(scoreCard));
  const byModel = Object.fromEntries(candidateScores.map((s) => [s.model_name, s.rank_position]));
  const note = rankGapNote(byModel.tfidf, byModel.minilm);
  byId("candidate-agreement").textContent = note || "";
  byId("candidate-agreement").hidden = !note;
  const showEvidence = (evidence) => {
    chips(byId("candidate-evidence"), evidence.matched, "good", "No tracked skills appear in both.");
    chips(byId("candidate-gap"), evidence.not_found, "gap", "None — every tracked skill the job asks for appears.");
  };
  if (!live) {
    showEvidence(demoEvidence(row.resume_id, skillTerms));
    dialog.showModal();
    return;
  }
  chips(byId("candidate-evidence"), [], "", "Loading skills…");
  chips(byId("candidate-gap"), [], "", "");
  dialog.showModal();
  try {
    const evidence = await api(`/api/saved/${result.run_id}/evidence?candidate=${encodeURIComponent(row.resume_id)}`);
    if (title.dataset.id === row.resume_id) showEvidence(evidence);
  } catch (error) {
    if (title.dataset.id === row.resume_id) chips(byId("candidate-evidence"), [], "", error.message);
  }
}

byId("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const term = byId("candidate-search").value.trim();
  if (term.length < 2) {
    byId("search-status").textContent = "Enter at least two characters.";
    return;
  }
  const current = result;
  byId("search-status").textContent = "Searching…";
  try {
    const ids = live ? (await api(`/api/saved/${current.run_id}/search?q=${encodeURIComponent(term)}`)).ids
      : current.scores.filter((row) => row.resume_id.toLowerCase().includes(term.toLowerCase())).map((row) => row.resume_id);
    if (result !== current || byId("candidate-search").value.trim() !== term) return;
    const byLabel = [...labels].filter(([, label]) => label.toLowerCase().includes(term.toLowerCase())).map(([id]) => id);
    matchingIds = new Set([...ids, ...byLabel]);
    renderRanking();
  } catch (error) {
    if (result === current) byId("search-status").textContent = error.message;
  }
});
byId("search-form").addEventListener("reset", () => {
  matchingIds = null;
  byId("search-status").textContent = "";
  renderRanking();
});

byId("fix-data").addEventListener("click", async () => {
  const button = byId("fix-data");
  button.disabled = true;
  byId("fix-status").textContent = "Checking prepared data…";
  byId("fix-summary").replaceChildren();
  try {
    const data = await api("/api/fix-data", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
    for (const row of data.summary) {
      const li = document.createElement("li");
      li.textContent = `${row.table} · ${row.trimmed ?? "Unknown number of"} trimmed · ${row.remaining_spaces} still need trimming · ${row.missing_text} missing text · ${row.missing_ids} missing IDs · ${row.duplicate_ids} duplicate IDs`;
      byId("fix-summary").append(li);
    }
    byId("fix-status").textContent = "Cleanup checked. Review any missing fields or duplicate IDs.";
  } catch (error) {
    byId("fix-status").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

const CHECK_NAMES = {
  complete_score_count: "Every resume received a score", expected_score_count: "No extra score rows",
  positive_ranks: "Ranks are valid", scores_between_zero_and_one: "Scores are between 0% and 100%",
  selected_job_exists_once: "Selected job is unique", selected_job_only: "Scores belong to the selected job",
  selected_model_only: "Scores belong to the selected model", study_domain_ratio: "70/30 sample mix holds",
  study_job_count: "Job count is within study range", study_resume_count: "Resume count is within study range",
  text_character_limit: "Text is within the 1,000-character limit", unique_evaluation_ids: "Evaluation IDs are unique",
  unique_identifiers: "Record IDs are unique", usable_records: "Records have usable text",
  valid_required_inputs: "Required fields are present", missing_text_audit: "Missing-text audit",
  duplicate_prepared_text: "Duplicate prepared text", minilm_token_limit: "MiniLM token limit",
  pipeline_execution: "Pipeline ran without errors",
};
function renderChecks(checks) {
  byId("no-checks").hidden = checks.length > 0;
  const summary = byId("check-summary");
  const list = byId("check-list");
  list.replaceChildren();
  summary.hidden = !checks.length;
  if (!checks.length) return;
  const problems = checks.filter((check) => check.status !== "passed");
  summary.className = "check-summary " + (problems.some((c) => c.status === "failed") ? "critical" : problems.length ? "warning" : "good");
  summary.textContent = problems.length
    ? `${problems.length} of ${checks.length} checks need attention — listed first below.`
    : `All ${checks.length} checks passed. Scores for this run are safe to use.`;
  const merged = new Map();
  for (const check of checks) {
    const key = check.check_name + "|" + check.status;
    if (!merged.has(key)) merged.set(key, {...check, times: 0, fail_count: 0});
    merged.get(key).times++;
    merged.get(key).fail_count += check.fail_count || 0;
  }
  const order = {failed: 0, warning: 1, passed: 2};
  for (const check of [...merged.values()].sort((a, b) => order[a.status] - order[b.status])) {
    const item = document.createElement("li");
    item.className = "check " + check.status;
    const label = document.createElement("strong");
    label.textContent = (CHECK_NAMES[check.check_name] || check.check_name.replaceAll("_", " "))
      + (check.times > 1 ? " (resumes and jobs)" : "");
    const detail = document.createElement("span");
    detail.textContent = check.status === "passed" ? "Passed"
      : `${check.status}${check.fail_count ? " · " + check.fail_count + " flagged" : ""}${check.detail ? " — " + check.detail : ""}`;
    item.append(label, detail);
    list.append(item);
  }
}

// --- consistency tests tab: name-swap and keyword-stuffing results from notebook 10 ---
let audits = null;
function renderAudits() {
  const jobId = byId("job").value;
  const scope = byId("audit-scope");
  scope.options[0].disabled = !jobId || !audits.job.length;
  if (scope.options[0].disabled) scope.value = "all";
  const summary = auditSummary(scope.value === "job" ? audits.job : audits.all);
  const names = summary.name_swap, stuffing = summary.keyword_stuffing;
  byId("audit-body").hidden = !names || !stuffing;
  byId("audit-status").hidden = Boolean(names && stuffing);
  if (!names || !stuffing) {
    byId("audit-status").textContent = "No test results are saved yet. Run notebook 10_run_audits in Databricks.";
    return;
  }
  byId("audit-context").textContent = (scope.value === "job" ? jobLabel(jobId) : "All jobs combined")
    + ` · ${names.minilm.pairs.toLocaleString()} name-swap comparisons and ${stuffing.minilm.pairs.toLocaleString()} keyword-stuffing comparisons per model.`;
  const share = (part, whole) => `${part.toLocaleString()} (${whole ? Math.round(100 * part / whole) : 0}%)`;
  renderTiles(byId("name-kpis"), [
    ["TF-IDF · largest score change", asPoints(names.tfidf.maxChange), "0 means a name can never matter"],
    ["MiniLM · largest score change", asPoints(names.minilm.maxChange), "Percentage points on the 0–100% match scale"],
    ["MiniLM · moved 5+ places", share(names.minilm.moved5, names.minilm.pairs), `Biggest single move: ${names.minilm.maxRankMove} places`],
    ["MiniLM · top-20 changes", names.minilm.top20Changed.toLocaleString(), "Times a name moved a resume into or out of the top 20"],
  ]);
  byId("name-verdict").textContent = nameSwapVerdict(names);
  byId("name-verdict").classList.toggle("caution", names.minilm.moved5 > 0);
  const perName = names.minilm.conditions;
  renderMagnitudeChart(byId("name-chart"), perName.map((c) => ({label: c.label, count: c.moved5})),
    Math.max(1, ...perName.map((c) => c.moved5)) * 1.15);
  const signed = (value) => (value > 0 ? "+" : value < 0 ? "−" : "") + (Math.abs(value) * 100).toFixed(2) + " pts";
  const keywordByName = new Map(names.tfidf.conditions.map((c) => [c.label, c.meanChange]));
  byId("name-table").replaceChildren();
  for (const c of perName) addRow(byId("name-table"), [c.label, signed(keywordByName.get(c.label) ?? 0), signed(c.meanChange)]);
  const medians = (m) => `${Math.round(m.conditions[0].medianBefore)} → ${Math.round(m.conditions[0].medianAfter)}`;
  renderTiles(byId("stuffing-kpis"), [
    ["TF-IDF · reach top 20", `${stuffing.tfidf.top20Before} → ${stuffing.tfidf.top20After.toLocaleString()}`, `of ${stuffing.tfidf.pairs.toLocaleString()} control resumes`],
    ["TF-IDF · typical jump", medians(stuffing.tfidf), "Median rank before → after (1 is best)"],
    ["MiniLM · reach top 20", `${stuffing.minilm.top20Before} → ${stuffing.minilm.top20After.toLocaleString()}`, `of ${stuffing.minilm.pairs.toLocaleString()} control resumes`],
    ["MiniLM · typical jump", medians(stuffing.minilm), "Median rank before → after (1 is best)"],
  ]);
  byId("stuffing-verdict").textContent = stuffingVerdict(stuffing);
  renderMagnitudeChart(byId("stuffing-chart"), [
    {label: "TF-IDF before", count: stuffing.tfidf.top20Before}, {label: "TF-IDF after", count: stuffing.tfidf.top20After},
    {label: "MiniLM before", count: stuffing.minilm.top20Before}, {label: "MiniLM after", count: stuffing.minilm.top20After},
  ], stuffing.tfidf.pairs);
}
async function loadAudits() {
  const jobId = byId("job").value;
  if (audits?.jobId === jobId) return renderAudits();
  byId("audit-status").hidden = false;
  byId("audit-status").textContent = "Loading test results…";
  try {
    const data = await api("/api/audits" + (jobId ? "?job_id=" + encodeURIComponent(jobId) : ""));
    if (byId("job").value !== jobId) return;
    audits = {...data, jobId};
    renderAudits();
  } catch (error) {
    byId("audit-body").hidden = true;
    byId("audit-status").textContent = error.message;
  }
}
byId("audit-scope").addEventListener("change", renderAudits);

// --- agents tab: the scoring job and the data-fix operation, framed as controllable agents ---
function statusDot(level) {
  const dot = document.createElement("span");
  dot.className = "status-dot" + (level ? " " + level : "");
  dot.setAttribute("aria-hidden", "true");
  return dot;
}
function runStatusLevel(run) {
  if (!run) return "";
  if (run.status === "running" || run.status === "pending") return "running";
  if (run.status !== "succeeded") return "critical";
  if (run.quality_status === "warning") return "warning";
  if (run.quality_status === "failed") return "critical";
  return "good";
}
function jobLabel(jobId) {
  const job = jobsById.get(jobId);
  return job ? (job.company ? `${job.title} · ${job.company}` : job.title) : jobId;
}
function methodLabel(name) {
  return name === "both" ? "Both models" : methods[name] || name;
}
function agentStat(label, value) {
  const cell = document.createElement("div");
  const name = document.createElement("span");
  name.textContent = label;
  const strong = document.createElement("strong");
  strong.textContent = value ?? "—";
  cell.append(name, strong);
  return cell;
}
function renderScoringAgent(agent, runs) {
  const card = document.createElement("article");
  card.className = "agent-card";
  const head = document.createElement("div");
  head.className = "agent-card-head";
  const title = document.createElement("h3");
  const latest = runs[0];
  title.append(statusDot(runStatusLevel(latest)), document.createTextNode(agent.name));
  head.append(title);
  const description = document.createElement("p");
  description.className = "agent-description";
  description.textContent = agent.description;
  const stats = document.createElement("div");
  stats.className = "agent-stats";
  stats.append(
    agentStat("Last job", latest ? jobLabel(latest.job_id) : null),
    agentStat("Method", latest ? methodLabel(latest.model_name) : null),
    agentStat("Resumes scored", latest?.resume_count),
    agentStat("Data quality", latest?.quality_status),
  );
  const history = document.createElement("div");
  history.className = "agent-history";
  const historyTitle = document.createElement("h3");
  historyTitle.textContent = "Recent runs";
  const list = document.createElement("ul");
  if (!runs.length) {
    const li = document.createElement("li");
    li.textContent = "No scans recorded yet this session.";
    list.append(li);
  }
  for (const run of runs) {
    const li = document.createElement("li");
    const strong = document.createElement("strong");
    strong.textContent = `${jobLabel(run.job_id)} · ${methodLabel(run.model_name)}`;
    const state = document.createElement("span");
    state.className = "run-state";
    const when = run.completed_at ? new Date(run.completed_at) : null;
    state.textContent = run.status + (when && !isNaN(when) ? " · " + when.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"}) : "");
    li.append(statusDot(runStatusLevel(run)), strong, state);
    list.append(li);
  }
  history.append(historyTitle, list);
  card.append(head, description, stats, history);
  return card;
}
function renderFixDataAgent(agent, lastFix) {
  const card = document.createElement("article");
  card.className = "agent-card";
  const head = document.createElement("div");
  head.className = "agent-card-head";
  const title = document.createElement("h3");
  title.append(statusDot(lastFix ? "good" : ""), document.createTextNode(agent.name));
  head.append(title);
  const description = document.createElement("p");
  description.className = "agent-description";
  description.textContent = agent.description;
  const stats = document.createElement("div");
  stats.className = "agent-stats";
  const totals = (lastFix || []).reduce((sum, row) => ({
    missing: sum.missing + (row.missing_text || 0) + (row.missing_ids || 0),
    duplicates: sum.duplicates + (row.duplicate_ids || 0),
  }), {missing: 0, duplicates: 0});
  stats.append(
    agentStat("Tables checked", lastFix ? lastFix.length : null),
    agentStat("Missing fields found", lastFix ? totals.missing : null),
    agentStat("Duplicate IDs found", lastFix ? totals.duplicates : null),
  );
  const hint = document.createElement("p");
  hint.className = "agent-description";
  hint.textContent = lastFix ? "Run it again from the Data Quality tab after new data lands."
    : "Run it from the Data Quality tab to check the prepared tables.";
  card.append(head, description, stats, hint);
  return card;
}
async function loadAgents() {
  const grid = byId("agents-grid");
  try {
    const data = await api("/api/agents");
    grid.replaceChildren();
    for (const agent of data.agents) {
      grid.append(agent.id === "scoring" ? renderScoringAgent(agent, data.runs) : renderFixDataAgent(agent, data.last_fix));
    }
  } catch (error) {
    grid.replaceChildren();
    const empty = document.createElement("p");
    empty.className = "viz-empty";
    empty.textContent = error.message;
    grid.append(empty);
  }
}

function renderJobDescription(job) {
  const container = byId("job-description");
  container.replaceChildren();
  if (!job) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Choose a job above to see its posting.";
    container.append(empty);
    return;
  }
  const title = document.createElement("h3");
  title.textContent = job.company ? `${job.title} · ${job.company}` : job.title;
  const points = postingPoints(job.text);
  const label = document.createElement("p");
  label.className = "posting-label";
  label.textContent = points.length ? "What the posting asks for (prepared text used for scoring)" : "No posting text is available for this job.";
  const list = document.createElement("ul");
  list.className = "posting-points";
  for (const point of points) {
    const li = document.createElement("li");
    li.textContent = point;
    list.append(li);
  }
  container.append(title, label, list);
}

async function initialize() {
  try {
    const data = await api("/api/jobs");
    live = data.mode === "live";
    byId("fix-data").disabled = false;
    byId("connection").textContent = live ? "Databricks connected" : "Demo · synthetic data";
    jobsById = new Map(data.jobs.map((job) => [job.job_id, job]));
    skillTerms = data.skills || [];
    byId("evidence-caption").textContent = live
      ? "From a fixed list of 14 data skills (SQL, Python, Tableau…). Exact word matches only."
      : "Demo mode has no real resume text, so this illustrates the kind of overlap check live mode performs using placeholder terms, not this candidate's actual skills.";
    byId("gap-caption").textContent = live
      ? "Worth a manual check, not a disqualifier — the resume may describe the skill in other words."
      : "Illustrative only, for the same reason as above — not a real gap in this candidate's experience.";
    const job = byId("job");
    job.replaceChildren(new Option("Select a job", ""));
    job.options[0].disabled = true;
    for (const row of data.jobs) {
      job.add(new Option(row.company ? row.title + " · " + row.company : row.title, row.job_id));
    }
    job.disabled = !data.jobs.length;
    job.addEventListener("change", () => {
      byId("start").disabled = byId("rescan").disabled = !job.value;
      renderJobDescription(jobsById.get(job.value));
      if (!byId("audits").hidden) loadAudits();
      // Reload saved results right away so every chart follows the selected posting.
      loadMatches(false, true);
    });
    byId("model").addEventListener("change", () => { if (job.value) loadMatches(false, true); });
    status(data.jobs.length ? "" : "No prepared study jobs are available.");
  } catch (error) {
    byId("connection").textContent = "Connection unavailable";
    status(error.message, true);
  }
}

async function loadMatches(fresh, stayOnView) {
  const job = byId("job");
  const model = byId("model");
  const start = byId("start");
  const rescan = byId("rescan");
  start.disabled = rescan.disabled = job.disabled = model.disabled = true;
  result = null;
  matchingIds = null;
  byId("candidate-search").value = "";
  byId("search-status").textContent = "";
  byId("metrics").hidden = byId("method-wrap").hidden = byId("analytics-method-wrap").hidden = true;
  byId("result-title").textContent = "Top 20 matches";
  byId("empty").textContent = fresh ? "Waiting for the scan." : "Loading saved rankings.";
  renderRanking();
  renderChecks([]);
  if (!stayOnView) showView("ranking");
  status(fresh ? "Starting scan…" : "Loading saved rankings…", false, true);
  try {
    if (fresh) {
    const scan = await api("/api/scans", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({job_id: job.value, model: model.value})
    });
    for (;;) {
      result = await api("/api/scans/" + scan.run_id);
      if (["succeeded", "blocked", "failed"].includes(result.status)) break;
      status("Scan status · " + result.status.replaceAll("_", " "), false, true);
      await new Promise((resolve) => setTimeout(resolve, live ? 4000 : 900));
    }
    } else {
      const params = new URLSearchParams({job_id: job.value, model: model.value});
      result = await api("/api/saved?" + params);
    }
    const scored = result.status === "succeeded";
    byId("metrics").hidden = !result.quality_status;
    countUp(byId("count"), scored ? result.resume_count : 0);
    countUp(byId("skipped"), result.skipped_resume_count);
    byId("quality").textContent = result.quality_status ?? "—";
    const available = [...new Set((result.scores || []).map((row) => row.model_name))]
      .filter((name) => model.value === "both" || name === model.value);
    byId("method").replaceChildren(...available.map((name) => new Option(methods[name], name)));
    byId("analytics-method").replaceChildren(...available.map((name) => new Option(methods[name], name)));
    byId("method-wrap").hidden = available.length < 2;
    byId("analytics-method-wrap").hidden = available.length < 2;
    labels = candidateLabels(result.scores || []);
    result.job_title = job.selectedOptions[0].text.split(" · ")[0];
    byId("result-title").textContent = "Top 20 · " + result.job_title;
    byId("empty").textContent = scored ? "No candidate matches were saved." : "No rankings are available for this scan.";
    renderChecks(result.checks || []);
    renderRanking();
    if (result.status === "blocked") showView("checks");
    const time = result.completed_at ? new Date(result.completed_at).toLocaleString() : "";
    status(scored ? job.selectedOptions[0].text + " — " + (fresh ? "scan complete" : "saved rankings") + (time ? ", scored " + time : "")
      : result.error || "Scan " + result.status + ". Review Data Quality for details.", !scored);
    if (fresh && !byId("agents").hidden) loadAgents();
  } catch (error) {
    status(error.message, true);
    byId("empty").textContent = "No rankings available. Try another scan.";
  } finally {
    start.disabled = rescan.disabled = job.disabled = model.disabled = false;
  }
}
byId("scan-form").addEventListener("submit", (event) => {
  event.preventDefault();
  loadMatches(false);
});
byId("rescan").addEventListener("click", () => loadMatches(true));

renderRanking();
initialize();
setupScoreSpaceDrag();
