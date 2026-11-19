"use strict";
const byId = (id) => document.getElementById(id);
const methods = {tfidf: "TF-IDF · Keyword", minilm: "MiniLM · Semantic"};
const notes = {
  tfidf: "TF-IDF compares weighted terms and phrases shared by the prepared resume and job description.",
  minilm: "MiniLM encodes both texts and compares their embeddings. Its score summarizes how similar the texts are in meaning."
};
let result = null;
let live = false;
let matchingIds = null;

async function api(path, options) {
  const response = await fetch(path, {...options, cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The request failed.");
  return data;
}
function status(message, error = false) {
  byId("status").textContent = message;
  byId("status").classList.toggle("error", error);
}
function showView(id) {
  for (const tab of document.querySelectorAll(".tab")) {
    const selected = tab.dataset.view === id;
    tab.classList.toggle("chosen", selected);
    tab.setAttribute("aria-pressed", String(selected));
    byId(tab.dataset.view).hidden = !selected;
  }
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
    candidate.textContent = row.resume_id;
    candidate.addEventListener("click", () => showCandidate(row));
    tr.insertCell().append(candidate);
    const score = Number(row.similarity_score);
    const cell = tr.insertCell();
    cell.className = "score";
    const number = document.createElement("span");
    number.textContent = score.toFixed(3);
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

function medianScore(rows) {
  const scores = rows.map((row) => Number(row.similarity_score)).sort((a, b) => a - b);
  const middle = Math.floor(scores.length / 2);
  return scores.length % 2 ? scores[middle] : (scores[middle - 1] + scores[middle]) / 2;
}

function addRow(container, values) {
  const row = container.insertRow();
  for (const value of values) row.insertCell().textContent = value;
  return row;
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
  byId("score-summary").textContent = `Median score ${medianScore(rows).toFixed(3)} · Range ${Math.min(...scores).toFixed(3)} to ${Math.max(...scores).toFixed(3)} · ${skipped} resumes skipped`;
  const bins = [0, 0, 0, 0, 0];
  for (const row of rows) bins[Math.min(4, Math.floor(Number(row.similarity_score) * 5))]++;
  chart("distribution", ["0–<0.2", "0.2–<0.4", "0.4–<0.6", "0.6–<0.8", "0.8–1.0"]
    .map((label, i) => [label, bins[i]]), rows.length);
  const groups = new Map();
  const sources = new Map();
  for (const row of rows) {
    const label = {tech_data_proxy: "Tech/data", control: "Control"}[row.domain_group] || "Unclassified";
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(row);
    const source = {structured: "Resume dataset", recruitment: "Recruitment dataset"}[row.source_dataset]
      || row.source_dataset || "Unknown";
    sources.set(source, (sources.get(source) || 0) + 1);
  }
  chart("source-mix", [...sources].sort((a, b) => b[1] - a[1]), rows.length);
  const breakdown = byId("group-results");
  breakdown.replaceChildren();
  for (const [label, group] of [...groups].sort((a, b) => b[1].length - a[1].length)) {
    const share = (group.length / rows.length * 100).toFixed(0);
    addRow(breakdown, [label, `${group.length} (${share}%)`, medianScore(group).toFixed(3),
      group.filter((row) => row.rank_position <= 20).length]);
  }
  renderOverlap();
}

function renderOverlap() {
  const ranks = {tfidf: new Map(), minilm: new Map()};
  for (const row of result.scores) ranks[row.model_name]?.set(row.resume_id, row);
  const summary = byId("overlap-summary");
  const changes = byId("rank-differences");
  changes.replaceChildren();
  byId("rank-changes").hidden = true;
  if (!ranks.tfidf.size || ranks.tfidf.size !== ranks.minilm.size ||
      ![...ranks.tfidf.keys()].every((id) => ranks.minilm.has(id))) {
    summary.textContent = "Load a run that scored the same resumes with both models to compare ranks.";
    return;
  }
  const compared = [...ranks.tfidf].map(([id, keyword]) => ({id, keyword, semantic: ranks.minilm.get(id)}));
  const keywordTop = compared.filter(({keyword}) => keyword.rank_position <= 20);
  const semanticTop = compared.filter(({semantic}) => semantic.rank_position <= 20);
  const shared = keywordTop.filter(({semantic}) => semantic.rank_position <= 20).length;
  summary.textContent = `${shared} in both lists · ${keywordTop.length - shared} only in TF-IDF · ${semanticTop.length - shared} only in MiniLM`;
  const differences = compared.filter(({keyword, semantic}) => Math.min(keyword.rank_position, semantic.rank_position) <= 20)
    .map((row) => ({...row, gap: Math.abs(row.keyword.rank_position - row.semantic.rank_position)}))
    .filter((row) => row.gap > 0)
    .sort((a, b) => b.gap - a.gap || a.id.localeCompare(b.id))
    .slice(0, 5);
  byId("rank-changes").hidden = !differences.length;
  for (const row of differences) {
    const tr = addRow(changes, ["", row.keyword.rank_position, row.semantic.rank_position, row.gap]);
    const link = document.createElement("button");
    link.type = "button";
    link.className = "candidate-link";
    link.textContent = row.id;
    link.addEventListener("click", () => showCandidate(row.keyword));
    tr.cells[0].append(link);
  }
}

function chart(id, entries, total) {
  const container = byId(id);
  container.className = "chart";
  container.replaceChildren();
  if (!total) {
    container.textContent = "Load rankings to see this chart.";
    return;
  }
  for (const [label, count] of entries) {
    const row = document.createElement("div");
    row.className = "chart-row";
    const name = document.createElement("span");
    name.textContent = label;
    const track = document.createElement("span");
    track.className = "track";
    track.setAttribute("aria-hidden", "true");
    const bar = document.createElement("span");
    bar.className = "fill";
    bar.style.width = (100 * count / total) + "%";
    track.append(bar);
    const value = document.createElement("span");
    value.textContent = count;
    row.append(name, track, value);
    container.append(row);
  }
}

async function showCandidate(row) {
  const dialog = byId("candidate-detail");
  byId("candidate-title").textContent = row.resume_id;
  byId("candidate-source").textContent = `Source: ${row.source_dataset || "Unknown"} · ${row.domain_group === "tech_data_proxy" ? "Tech/data" : row.domain_group || "Unclassified"}`;
  const list = byId("candidate-scores");
  list.replaceChildren();
  for (const score of result.scores.filter((item) => item.resume_id === row.resume_id)) {
    const li = document.createElement("li");
    li.textContent = `${methods[score.model_name]} · rank ${score.rank_position} · score ${Number(score.similarity_score).toFixed(3)}`;
    list.append(li);
  }
  byId("candidate-evidence").textContent = live ? "Loading skills…" : "Skill evidence is available in live mode.";
  byId("candidate-gap").textContent = "";
  dialog.showModal();
  if (!live) return;
  try {
    const evidence = await api(`/api/saved/${result.run_id}/evidence?candidate=${encodeURIComponent(row.resume_id)}`);
    if (byId("candidate-title").textContent !== row.resume_id) return;
    byId("candidate-evidence").textContent = evidence.matched.join(", ") || "No tracked skills overlap.";
    byId("candidate-gap").textContent = evidence.not_found.join(", ") || "None among the tracked terms.";
  } catch (error) {
    if (byId("candidate-title").textContent === row.resume_id) byId("candidate-evidence").textContent = error.message;
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
    matchingIds = new Set(ids);
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

function renderChecks(checks) {
  byId("no-checks").hidden = checks.length > 0;
  byId("check-list").replaceChildren();
  for (const check of checks) {
    const item = document.createElement("li");
    const label = document.createElement("strong");
    label.textContent = check.check_name.replaceAll("_", " ");
    const badge = document.createElement("span");
    badge.className = "badge";
    if (["warning", "failed"].includes(check.status)) badge.classList.add(check.status);
    badge.textContent = check.status + (check.fail_count ? " · " + check.fail_count + " flagged" : "");
    const detail = document.createElement("p");
    detail.textContent = check.detail;
    item.append(label, badge, detail);
    byId("check-list").append(item);
  }
}

async function initialize() {
  try {
    const data = await api("/api/jobs");
    live = data.mode === "live";
    byId("fix-data").disabled = false;
    byId("connection").textContent = live ? "Databricks connected" : "Demo · synthetic data";
    const job = byId("job");
    job.replaceChildren(new Option("Select a job", ""));
    job.options[0].disabled = true;
    for (const row of data.jobs) {
      job.add(new Option(row.company ? row.title + " · " + row.company : row.title, row.job_id));
    }
    job.disabled = !data.jobs.length;
    job.addEventListener("change", () => { byId("start").disabled = byId("rescan").disabled = !job.value; });
    status(data.jobs.length ? "" : "No prepared study jobs are available.");
  } catch (error) {
    byId("connection").textContent = "Connection unavailable";
    status(error.message, true);
  }
}

async function loadMatches(fresh) {
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
  showView("ranking");
  status(fresh ? "Starting scan…" : "Loading saved rankings…");
  try {
    if (fresh) {
    const scan = await api("/api/scans", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({job_id: job.value, model: model.value})
    });
    for (;;) {
      result = await api("/api/scans/" + scan.run_id);
      if (["succeeded", "blocked", "failed"].includes(result.status)) break;
      status("Scan status · " + result.status.replaceAll("_", " "));
      await new Promise((resolve) => setTimeout(resolve, live ? 4000 : 900));
    }
    } else {
      const params = new URLSearchParams({job_id: job.value, model: model.value});
      result = await api("/api/saved?" + params);
    }
    const scored = result.status === "succeeded";
    byId("metrics").hidden = !result.quality_status;
    byId("count").textContent = scored ? result.resume_count : "0";
    byId("skipped").textContent = result.skipped_resume_count ?? "—";
    byId("quality").textContent = result.quality_status ?? "—";
    const available = [...new Set((result.scores || []).map((row) => row.model_name))]
      .filter((name) => model.value === "both" || name === model.value);
    byId("method").replaceChildren(...available.map((name) => new Option(methods[name], name)));
    byId("analytics-method").replaceChildren(...available.map((name) => new Option(methods[name], name)));
    byId("method-wrap").hidden = available.length < 2;
    byId("analytics-method-wrap").hidden = available.length < 2;
    result.job_title = job.selectedOptions[0].text.split(" · ")[0];
    byId("result-title").textContent = "Top 20 · " + result.job_title;
    byId("empty").textContent = scored ? "No candidate matches were saved." : "No rankings are available for this scan.";
    renderChecks(result.checks || []);
    renderRanking();
    if (result.status === "blocked") showView("checks");
    const time = result.completed_at ? new Date(result.completed_at).toLocaleString() : "";
    status(scored ? (fresh ? "Scan complete" : "Saved rankings") + (time ? " · Scored " + time : "")
      : result.error || "Scan " + result.status + ". Review Data Quality for details.", !scored);
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
