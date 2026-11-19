"use strict";
const byId = (id) => document.getElementById(id);
const methods = {tfidf: "TF-IDF · Keyword", minilm: "MiniLM · Semantic"};
const notes = {
  tfidf: "TF-IDF compares weighted terms and phrases shared by the prepared resume and job description.",
  minilm: "MiniLM encodes both texts and compares their embeddings. Its score summarizes how similar the texts are in meaning."
};
let result = null;
let live = false;

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
  const rows = result?.scores?.filter((row) => row.model_name === method) || [];
  const body = byId("scores");
  body.replaceChildren();
  for (const row of rows) {
    const tr = body.insertRow();
    tr.insertCell().textContent = row.rank_position;
    tr.insertCell().textContent = row.resume_id;
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
    byId("connection").textContent = live ? "Databricks connected" : "Demo · synthetic data";
    const job = byId("job");
    job.replaceChildren(new Option("Select a job", ""));
    job.options[0].disabled = true;
    for (const row of data.jobs) {
      job.add(new Option(row.company ? row.title + " · " + row.company : row.title, row.job_id));
    }
    job.disabled = !data.jobs.length;
    job.addEventListener("change", () => { byId("start").disabled = !job.value; });
    status(data.jobs.length ? "" : "No prepared study jobs are available.");
  } catch (error) {
    byId("connection").textContent = "Connection unavailable";
    status(error.message, true);
  }
}

byId("scan-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const job = byId("job");
  const model = byId("model");
  const start = byId("start");
  start.disabled = job.disabled = model.disabled = true;
  result = null;
  byId("metrics").hidden = byId("method-wrap").hidden = true;
  byId("result-title").textContent = "Top 20 matches";
  byId("empty").textContent = "Waiting for the scan to finish.";
  renderRanking();
  renderChecks([]);
  showView("ranking");
  status("Starting scan…");
  try {
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
    const scored = result.status === "succeeded";
    byId("metrics").hidden = !result.quality_status;
    byId("count").textContent = scored ? result.resume_count : "0";
    byId("skipped").textContent = result.skipped_resume_count ?? "—";
    byId("quality").textContent = result.quality_status ?? "—";
    const available = [...new Set((result.scores || []).map((row) => row.model_name))];
    byId("method").replaceChildren(...available.map((name) => new Option(methods[name], name)));
    byId("method-wrap").hidden = available.length < 2;
    byId("result-title").textContent = "Top 20 · " + job.selectedOptions[0].text.split(" · ")[0];
    byId("empty").textContent = scored ? "No candidate matches were saved." : "No rankings are available for this scan.";
    renderChecks(result.checks || []);
    renderRanking();
    if (result.status === "blocked") showView("checks");
    status(scored ? "Scan complete." : result.error || "Scan " + result.status + ". Review Data Quality for details.", !scored);
  } catch (error) {
    status(error.message, true);
    byId("empty").textContent = "No rankings available. Try another scan.";
  } finally {
    start.disabled = job.disabled = model.disabled = false;
  }
});

initialize();
