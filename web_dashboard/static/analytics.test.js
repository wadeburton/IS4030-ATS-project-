"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {medianScore, binScores, sourceMix, groupBreakdown, overlapSummary, demoEvidence, sourceLabel, rankGapNote, rankFractions, densityGrid, candidateLabels, rankCorrelation, postingPoints, analyticsVerdict, auditSummary, nameSwapVerdict, stuffingVerdict} = require("./analytics.js");

test("medianScore averages the two middle values for an even-length sample", () => {
  const rows = [{similarity_score: 0.8}, {similarity_score: 0.2}, {similarity_score: 0.6}, {similarity_score: 0.4}];
  assert.equal(medianScore(rows), 0.5);
});

test("medianScore returns the middle value for an odd-length sample", () => {
  const rows = [{similarity_score: 0.9}, {similarity_score: 0.1}, {similarity_score: 0.5}];
  assert.equal(medianScore(rows), 0.5);
});

test("binScores sorts scores into five fixed buckets, with 1.0 landing in the top bucket", () => {
  const rows = [0, 0.19999, 0.2, 0.39999, 0.4, 0.59999, 0.6, 0.79999, 0.8, 1.0]
    .map((similarity_score) => ({similarity_score}));
  assert.deepEqual(binScores(rows), [
    {label: "0–<0.2", count: 2},
    {label: "0.2–<0.4", count: 2},
    {label: "0.4–<0.6", count: 2},
    {label: "0.6–<0.8", count: 2},
    {label: "0.8–1.0", count: 2},
  ]);
});

test("sourceMix counts resumes per dataset, mapping known codes to labels and sorting by count", () => {
  const rows = [
    ...Array(3).fill({source_dataset: "structured"}),
    ...Array(2).fill({source_dataset: "recruitment"}),
    {source_dataset: "custom"},
  ];
  assert.deepEqual(sourceMix(rows), [
    {label: "Resume dataset", count: 3},
    {label: "Recruitment dataset", count: 2},
    {label: "custom", count: 1},
  ]);
});

test("groupBreakdown summarizes count, share, median score, and top-20 count per domain group", () => {
  const rows = [
    {domain_group: "tech_data_proxy", similarity_score: 0.9, rank_position: 1},
    {domain_group: "tech_data_proxy", similarity_score: 0.8, rank_position: 2},
    {domain_group: "tech_data_proxy", similarity_score: 0.7, rank_position: 25},
    {domain_group: "control", similarity_score: 0.3, rank_position: 3},
    {domain_group: "control", similarity_score: 0.5, rank_position: 30},
    {domain_group: null, similarity_score: 0.4, rank_position: 40},
  ];
  assert.deepEqual(groupBreakdown(rows), [
    {label: "Tech/data", count: 3, sharePercent: 50, medianScore: 0.8, topCount: 2},
    {label: "Control", count: 2, sharePercent: 33, medianScore: 0.4, topCount: 1},
    {label: "Unclassified", count: 1, sharePercent: 17, medianScore: 0.4, topCount: 0},
  ]);
});

test("overlapSummary compares two models' top-20 lists when every resume has both", () => {
  const scores = [
    {resume_id: "A", model_name: "tfidf", rank_position: 1}, {resume_id: "A", model_name: "minilm", rank_position: 5},
    {resume_id: "B", model_name: "tfidf", rank_position: 2}, {resume_id: "B", model_name: "minilm", rank_position: 21},
    {resume_id: "C", model_name: "tfidf", rank_position: 25}, {resume_id: "C", model_name: "minilm", rank_position: 3},
    {resume_id: "D", model_name: "tfidf", rank_position: 4}, {resume_id: "D", model_name: "minilm", rank_position: 4},
    {resume_id: "E", model_name: "tfidf", rank_position: 10}, {resume_id: "E", model_name: "minilm", rank_position: 18},
  ];
  assert.deepEqual(overlapSummary(scores), {
    comparable: true, shared: 3, keywordOnly: 1, semanticOnly: 1,
    differences: [
      {resumeId: "C", keywordRank: 25, semanticRank: 3, gap: 22},
      {resumeId: "B", keywordRank: 2, semanticRank: 21, gap: 19},
      {resumeId: "E", keywordRank: 10, semanticRank: 18, gap: 8},
      {resumeId: "A", keywordRank: 1, semanticRank: 5, gap: 4},
    ],
  });
});

test("overlapSummary reports not comparable when the two models didn't score the same resumes", () => {
  const scores = [
    {resume_id: "A", model_name: "tfidf", rank_position: 1}, {resume_id: "A", model_name: "minilm", rank_position: 1},
    {resume_id: "B", model_name: "tfidf", rank_position: 2},
  ];
  assert.deepEqual(overlapSummary(scores), {comparable: false, shared: 0, keywordOnly: 0, semanticOnly: 0, differences: []});
});

test("demoEvidence deterministically partitions every tracked skill into matched or not_found, with no overlap", () => {
  const skills = ["SQL", "Python", "Power BI", "Tableau", "Excel"];
  const first = demoEvidence("DEMO-012", skills);
  const second = demoEvidence("DEMO-012", skills);
  assert.deepEqual(first, second, "the same candidate must get the same illustrative split every time");
  assert.deepEqual([...first.matched, ...first.not_found].sort(), [...skills].sort());
  assert.deepEqual(first.matched.filter((skill) => first.not_found.includes(skill)), []);
});

test("sourceLabel maps known dataset codes and falls back to the raw code or Unknown", () => {
  assert.equal(sourceLabel("structured"), "Resume dataset");
  assert.equal(sourceLabel("recruitment"), "Recruitment dataset");
  assert.equal(sourceLabel("custom"), "custom");
  assert.equal(sourceLabel(undefined), "Unknown");
});

test("rankGapNote explains a large TF-IDF/MiniLM rank disagreement in the direction it occurred", () => {
  assert.match(rankGapNote(23, 1), /MiniLM ranked this candidate much higher/);
  assert.match(rankGapNote(1, 23), /TF-IDF ranked this candidate much higher/);
  assert.match(rankGapNote(10, 12), /similarly/);
  assert.equal(rankGapNote(10, null), null);
});

test("rankFractions converts each model's rank into a 0-1 standing where 1 is the best rank, dropping resumes missing either", () => {
  const scores = [
    {resume_id: "A", model_name: "tfidf", rank_position: 1}, {resume_id: "A", model_name: "minilm", rank_position: 5},
    {resume_id: "B", model_name: "tfidf", rank_position: 3}, {resume_id: "B", model_name: "minilm", rank_position: 3},
    {resume_id: "C", model_name: "tfidf", rank_position: 5}, {resume_id: "C", model_name: "minilm", rank_position: 1},
    {resume_id: "D", model_name: "tfidf", rank_position: 2},
  ];
  assert.deepEqual(rankFractions(scores, 5), [
    {resumeId: "A", tfidf: 1, minilm: 0},
    {resumeId: "B", tfidf: 0.5, minilm: 0.5},
    {resumeId: "C", tfidf: 0, minilm: 1},
  ]);
});

test("densityGrid bins points into a 2D count grid, clamping a score of exactly 1.0 into the last bin", () => {
  const points = [
    {tfidf: 0.1, minilm: 0.1}, {tfidf: 0.4, minilm: 0.4},
    {tfidf: 0.1, minilm: 0.9}, {tfidf: 0.9, minilm: 0.9}, {tfidf: 1.0, minilm: 1.0},
  ];
  const {grid, maxCount, binsX, binsY} = densityGrid(points, 2, 2);
  assert.deepEqual(grid, [
    [2, 0],
    [1, 2],
  ]);
  assert.equal(maxCount, 2);
  assert.equal(binsX, 2);
  assert.equal(binsY, 2);
});

test("demoEvidence varies the split across different candidates", () => {
  const skills = ["SQL", "Python", "Power BI", "Tableau", "Excel", "R", "ETL", "statistics"];
  const splits = new Set(["DEMO-001", "DEMO-002", "DEMO-003", "DEMO-004"]
    .map((id) => demoEvidence(id, skills).matched.join(",")));
  assert.ok(splits.size > 1, "different candidates should not all get an identical split");
});

test("candidateLabels gives each resume one stable short label regardless of row order or repeats", () => {
  const scores = [
    {resume_id: "structured-bb"}, {resume_id: "recruitment-aa"}, {resume_id: "structured-bb"}, {resume_id: "structured-cc"},
  ];
  const labels = candidateLabels(scores);
  assert.equal(labels.get("recruitment-aa"), "Candidate 001");
  assert.equal(labels.get("structured-bb"), "Candidate 002");
  assert.equal(labels.get("structured-cc"), "Candidate 003");
  assert.deepEqual([...candidateLabels([...scores].reverse())], [...labels]);
});

test("rankCorrelation is 1 for identical rankings, -1 for reversed, and matches a worked example", () => {
  const pairs = (tf, ml) => tf.flatMap((rank, i) => [
    {resume_id: "r" + i, model_name: "tfidf", rank_position: rank},
    {resume_id: "r" + i, model_name: "minilm", rank_position: ml[i]}]);
  assert.equal(rankCorrelation(pairs([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])), 1);
  assert.equal(rankCorrelation(pairs([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])), -1);
  assert.equal(rankCorrelation(pairs([1, 2, 3, 4, 5], [2, 1, 4, 3, 5])), 0.8);
  assert.equal(rankCorrelation([{resume_id: "a", model_name: "tfidf", rank_position: 1}]), null);
});

test("postingPoints turns a bullet-separated posting into clean capitalized points", () => {
  assert.deepEqual(postingPoints(": · proven experience as a data analyst · strong knowledge of sql · adept at queries"),
    ["Proven experience as a data analyst", "Strong knowledge of sql", "Adept at queries"]);
  assert.deepEqual(postingPoints("one plain sentence with no separators."), ["One plain sentence with no separators."]);
  assert.deepEqual(postingPoints(""), []);
});

test("analyticsVerdict states agreement strength and flags control resumes in the top 20", () => {
  assert.match(analyticsVerdict({agreement: 0.59, shared: 9, controlTop: 0}), /broadly agree.*9 of their top 20.*No control resumes/s);
  assert.match(analyticsVerdict({agreement: 0.29, shared: 11, controlTop: 0}), /only partly agree/);
  assert.match(analyticsVerdict({agreement: 0.05, shared: 4, controlTop: 0}), /little relationship/);
  assert.match(analyticsVerdict({agreement: -0.2, shared: 0, controlTop: 3}), /opposite.*none of their top 20.*3 control resumes reached.*caution/s);
  assert.match(analyticsVerdict({agreement: null, shared: 0, controlTop: 1}), /^1 control resume reached/);
});

const auditRow = (audit, model_name, test_condition, values) => ({audit, model_name, test_condition, pairs: 300,
  mean_change: 0, max_change: 0, moved_5: 0, max_rank_move: 0, top20_before: 20, top20_after: 20, top20_changed: 0,
  median_rank_before: 150, median_rank_after: 150, ...values});

test("auditSummary totals counts and keeps the worst case across names", () => {
  const summary = auditSummary([
    auditRow("name_swap", "minilm", "Emily Walsh", {moved_5: 10, max_change: 0.02, max_rank_move: 12}),
    auditRow("name_swap", "minilm", "Wei Chen", {moved_5: 30, max_change: 0.05, max_rank_move: 40}),
    auditRow("name_swap", "tfidf", "Emily Walsh", {}),
  ]);
  const minilm = summary.name_swap.minilm;
  assert.deepEqual([minilm.pairs, minilm.moved5, minilm.maxChange, minilm.maxRankMove], [600, 40, 0.05, 40]);
  assert.deepEqual(minilm.conditions.map((c) => [c.label, c.moved5]), [["Emily Walsh", 10], ["Wei Chen", 30]]);
  assert.equal(summary.name_swap.tfidf.maxChange, 0);
});

test("nameSwapVerdict says the keyword model ignores names and quantifies the semantic shift", () => {
  const text = nameSwapVerdict(auditSummary([
    auditRow("name_swap", "tfidf", "Emily Walsh", {}),
    auditRow("name_swap", "minilm", "Emily Walsh", {moved_5: 75, max_change: 0.0412}),
  ]).name_swap);
  assert.match(text, /never changed a TF-IDF score/);
  assert.match(text, /up to 0\.041 and 75 of 300 name\/resume pairs \(25%\)/);
  assert.equal(nameSwapVerdict(undefined), "");
});

test("stuffingVerdict names the model that is easier to game", () => {
  const text = stuffingVerdict(auditSummary([
    auditRow("keyword_stuffing", "tfidf", "stuffed", {pairs: 90, top20_before: 1, top20_after: 45}),
    auditRow("keyword_stuffing", "minilm", "stuffed", {pairs: 90, top20_before: 0, top20_after: 9}),
  ]).keyword_stuffing);
  assert.match(text, /45 of 90 \(50%\) under TF-IDF, up from 1/);
  assert.match(text, /9 of 90 \(10%\) under MiniLM, up from 0/);
  assert.match(text, /TF-IDF is the easier model to game/);
});

test("stuffingVerdict does not pick a loser when both models are fooled equally", () => {
  const row = (model) => auditRow("keyword_stuffing", model, "stuffed", {pairs: 90, top20_before: 0, top20_after: 90});
  assert.match(stuffingVerdict(auditSummary([row("tfidf"), row("minilm")]).keyword_stuffing), /Both models were equally easy to game here\.$/);
});
