"use strict";
const SOURCE_LABELS = {structured: "Resume dataset", recruitment: "Recruitment dataset"};
const GROUP_LABELS = {tech_data_proxy: "Tech/data", control: "Control"};
const BIN_LABELS = ["0–<20%", "20–<40%", "40–<60%", "60–<80%", "80–100%"];

// Scores are stored 0–1 but shown as a percent match; score changes are percentage points.
const asPercent = (score) => `${(Number(score) * 100).toFixed(1)}%`;
const asPoints = (change) => `${(Number(change) * 100).toFixed(1)} points`;

function medianScore(rows) {
  const scores = rows.map((row) => Number(row.similarity_score)).sort((a, b) => a - b);
  const middle = Math.floor(scores.length / 2);
  return scores.length % 2 ? scores[middle] : (scores[middle - 1] + scores[middle]) / 2;
}

function binScores(rows) {
  const counts = [0, 0, 0, 0, 0];
  for (const row of rows) counts[Math.min(4, Math.floor(Number(row.similarity_score) * 5))]++;
  return BIN_LABELS.map((label, i) => ({label, count: counts[i]}));
}

function countBy(rows, labelOf) {
  const counts = new Map();
  for (const row of rows) {
    const label = labelOf(row);
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return [...counts].map(([label, count]) => ({label, count})).sort((a, b) => b.count - a.count);
}

function sourceLabel(code) {
  return SOURCE_LABELS[code] || code || "Unknown";
}

function sourceMix(rows) {
  return countBy(rows, (row) => sourceLabel(row.source_dataset));
}

function rankGapNote(tfidfRank, minilmRank) {
  if (!Number.isFinite(tfidfRank) || !Number.isFinite(minilmRank)) return null;
  const gap = tfidfRank - minilmRank;
  if (gap >= 5) return "MiniLM ranked this candidate much higher than TF-IDF — likely matching on meaning rather than shared keywords.";
  if (gap <= -5) return "TF-IDF ranked this candidate much higher than MiniLM — likely an exact keyword match that doesn't carry the same weight in meaning-based scoring.";
  return "Both methods rank this candidate similarly.";
}

function groupBreakdown(rows) {
  const groups = new Map();
  for (const row of rows) {
    const label = GROUP_LABELS[row.domain_group] || "Unclassified";
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(row);
  }
  return [...groups].map(([label, group]) => ({
    label, count: group.length, sharePercent: Math.round(group.length / rows.length * 100),
    medianScore: medianScore(group), topCount: group.filter((row) => row.rank_position <= 20).length,
  })).sort((a, b) => b.count - a.count);
}

function overlapSummary(scores) {
  const ranks = {tfidf: new Map(), minilm: new Map()};
  for (const row of scores) ranks[row.model_name]?.set(row.resume_id, row);
  const comparable = ranks.tfidf.size > 0 && ranks.tfidf.size === ranks.minilm.size &&
    [...ranks.tfidf.keys()].every((id) => ranks.minilm.has(id));
  if (!comparable) return {comparable: false, shared: 0, keywordOnly: 0, semanticOnly: 0, differences: []};
  const compared = [...ranks.tfidf].map(([id, keyword]) => ({id, keyword, semantic: ranks.minilm.get(id)}));
  const keywordTop = compared.filter(({keyword}) => keyword.rank_position <= 20);
  const semanticTop = compared.filter(({semantic}) => semantic.rank_position <= 20);
  const shared = keywordTop.filter(({semantic}) => semantic.rank_position <= 20).length;
  const differences = compared
    .filter(({keyword, semantic}) => Math.min(keyword.rank_position, semantic.rank_position) <= 20)
    .map(({id, keyword, semantic}) => ({resumeId: id, keywordRank: keyword.rank_position,
      semanticRank: semantic.rank_position, gap: Math.abs(keyword.rank_position - semantic.rank_position)}))
    .filter((row) => row.gap > 0)
    .sort((a, b) => b.gap - a.gap || a.resumeId.localeCompare(b.resumeId))
    .slice(0, 5);
  return {comparable: true, shared, keywordOnly: keywordTop.length - shared,
    semanticOnly: semanticTop.length - shared, differences};
}

function simpleHash(text) {
  let hash = 0;
  for (const char of text) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  return hash;
}

function demoEvidence(resumeId, skills) {
  const matched = [];
  const not_found = [];
  for (const skill of skills) (simpleHash(`${resumeId}:${skill}`) % 3 === 0 ? matched : not_found).push(skill);
  return {matched, not_found};
}

// Raw TF-IDF and MiniLM scores sit on different scales (TF-IDF hugs 0), so models are
// compared by standing within their own ranking: 1 = best rank, 0 = worst.
function rankFractions(scores, total) {
  const byResume = new Map();
  for (const row of scores) {
    if (row.model_name !== "tfidf" && row.model_name !== "minilm") continue;
    if (!byResume.has(row.resume_id)) byResume.set(row.resume_id, {});
    byResume.get(row.resume_id)[row.model_name] = row.rank_position;
  }
  const standing = (rank) => total > 1 ? 1 - (rank - 1) / (total - 1) : 1;
  const points = [];
  for (const [resumeId, pair] of byResume) {
    if (pair.tfidf == null || pair.minilm == null) continue;
    points.push({resumeId, tfidf: standing(pair.tfidf), minilm: standing(pair.minilm)});
  }
  return points;
}

function densityGrid(points, binsX = 10, binsY = 10) {
  const grid = Array.from({length: binsY}, () => new Array(binsX).fill(0));
  for (const point of points) {
    const ix = Math.min(binsX - 1, Math.max(0, Math.floor(point.tfidf * binsX)));
    const iy = Math.min(binsY - 1, Math.max(0, Math.floor(point.minilm * binsY)));
    grid[iy][ix]++;
  }
  const maxCount = Math.max(1, ...grid.flat());
  return {grid, maxCount, binsX, binsY};
}

// Display-only labels: the hashed study IDs are unreadable, and real names are
// deliberately excluded from the study. Numbered by sorted ID so a resume keeps the
// same label for every job and model.
function candidateLabels(scores) {
  const ids = [...new Set(scores.map((row) => row.resume_id))].sort();
  const width = Math.max(3, String(ids.length).length);
  return new Map(ids.map((id, i) => [id, `Candidate ${String(i + 1).padStart(width, "0")}`]));
}

// Spearman rank correlation between the two models' rankings of the same resumes.
function rankCorrelation(scores) {
  const ranks = new Map();
  for (const row of scores) {
    if (row.model_name !== "tfidf" && row.model_name !== "minilm") continue;
    if (!ranks.has(row.resume_id)) ranks.set(row.resume_id, {});
    ranks.get(row.resume_id)[row.model_name] = row.rank_position;
  }
  const pairs = [...ranks.values()].filter((pair) => pair.tfidf != null && pair.minilm != null);
  const n = pairs.length;
  if (n < 2) return null;
  const squared = pairs.reduce((sum, pair) => sum + (pair.tfidf - pair.minilm) ** 2, 0);
  return Math.round((1 - 6 * squared / (n * (n * n - 1))) * 1000) / 1000;
}

function postingPoints(text) {
  const parts = (text || "").split(/\s[·•]\s|^[\s:·•-]+/).map((part) => part.replace(/^[\s:·•-]+/, "").trim()).filter(Boolean);
  return parts.map((part) => part[0].toUpperCase() + part.slice(1));
}

// One plain-language reading of the headline numbers for the selected job and method.
function analyticsVerdict({agreement, shared, controlTop}) {
  const parts = [];
  if (agreement != null) {
    const strength = agreement >= 0.5 ? "broadly agree on how to rank these resumes"
      : agreement >= 0.2 ? "only partly agree on how to rank these resumes"
      : agreement > -0.2 ? "show little relationship in how they rank these resumes"
      : "tend to rank these resumes in opposite order";
    const overlap = shared ? `share ${shared} of their top 20` : "share none of their top 20";
    parts.push(`The two models ${strength} (rank agreement ${agreement.toFixed(2)}) and ${overlap}.`);
  }
  parts.push(controlTop
    ? `${controlTop} control resume${controlTop === 1 ? "" : "s"} reached this method's top 20 — treat this ranking with caution and review it by hand.`
    : "No control resumes reached this method's top 20.");
  return parts.join(" ");
}

// Rolls the per-condition audit rows (one per synthetic name, or "stuffed") up to one
// entry per test and model, keeping the per-condition rows for charts.
function auditSummary(rows) {
  const out = {};
  for (const row of rows) {
    const audit = (out[row.audit] ||= {});
    const model = (audit[row.model_name] ||= {pairs: 0, moved5: 0, top20Before: 0, top20After: 0,
      top20Changed: 0, maxChange: 0, maxRankMove: 0, conditions: []});
    model.pairs += row.pairs;
    model.moved5 += row.moved_5;
    model.top20Before += row.top20_before;
    model.top20After += row.top20_after;
    model.top20Changed += row.top20_changed;
    model.maxChange = Math.max(model.maxChange, row.max_change);
    model.maxRankMove = Math.max(model.maxRankMove, row.max_rank_move);
    model.conditions.push({label: row.test_condition, meanChange: row.mean_change, moved5: row.moved_5,
      pairs: row.pairs, medianBefore: row.median_rank_before, medianAfter: row.median_rank_after});
  }
  return out;
}

const percent = (part, whole) => whole ? Math.round(100 * part / whole) : 0;

function nameSwapVerdict(test) {
  if (!test?.tfidf || !test?.minilm) return "";
  const {tfidf, minilm} = test;
  const keyword = tfidf.maxChange < 0.0005
    ? "Swapping the name never changed a TF-IDF score: the keyword model only counts words it learned from the resumes' qualifications and the posting, so names are ignored."
    : `Swapping the name changed TF-IDF scores by at most ${asPoints(tfidf.maxChange)}.`;
  return `${keyword} MiniLM reads the whole text, so its scores moved by up to ${asPoints(minilm.maxChange)} and `
    + `${minilm.moved5.toLocaleString()} of ${minilm.pairs.toLocaleString()} name/resume pairs (${percent(minilm.moved5, minilm.pairs)}%) `
    + "shifted 5 or more rank places with identical qualifications.";
}

function stuffingVerdict(test) {
  if (!test?.tfidf || !test?.minilm) return "";
  const part = (name, m) => `${m.top20After.toLocaleString()} of ${m.pairs.toLocaleString()} (${percent(m.top20After, m.pairs)}%) under ${name}, up from ${m.top20Before.toLocaleString()}`;
  const gap = test.tfidf.top20After - test.minilm.top20After;
  const worse = gap ? `${gap > 0 ? "TF-IDF" : "MiniLM"} is the easier model to game this way.` : "Both models were equally easy to game here.";
  return `After pasting in the posting's keywords, out-of-field control resumes would reach the top 20 in ${part("TF-IDF", test.tfidf)}; `
    + `${part("MiniLM", test.minilm)}. ${worse}`;
}

if (typeof module !== "undefined") {
  module.exports = {asPercent, asPoints, medianScore, binScores, sourceMix, groupBreakdown, overlapSummary, demoEvidence, sourceLabel, rankGapNote, rankFractions, densityGrid, candidateLabels, rankCorrelation, postingPoints, analyticsVerdict, auditSummary, nameSwapVerdict, stuffingVerdict};
}
