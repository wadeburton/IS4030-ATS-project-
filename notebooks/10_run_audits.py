# Databricks notebook source
# MAGIC %md
# MAGIC # Screening consistency audits: synthetic name swap and keyword stuffing
# MAGIC For every study job, rescores changed copies of the study resumes with both scoring
# MAGIC methods held fixed and overwrites `workspace.is4030_ops.ats_audit_results`.
# MAGIC
# MAGIC - **name_swap:** every resume carries the reference name line (`name: Emily Walsh`); one resume at a time has
# MAGIC   that name swapped for each of 5 other synthetic names. Qualifications are identical. TF-IDF keeps the
# MAGIC   vocabulary fitted on the unnamed qualification text.
# MAGIC - **keyword_stuffing:** control (out-of-domain) resumes with the posting's 12 most distinctive words appended.
# MAGIC
# MAGIC Resumes are shortened first (800 characters, 64 tokens of headroom) so the added text is never
# MAGIC truncated; the unchanged comparison copy uses the same shortened text. No resume text is written out.

# COMMAND ----------
# MAGIC %pip install scikit-learn==1.9.1 sentence-transformers==6.1.0

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
from datetime import datetime, timezone
from pathlib import Path
import sys

repo_root = str(Path.cwd().parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from ats_audits import (minilm_scorer, name_variants, paired_audit, stuffed_variants,
                        stuffing_terms, tfidf_scorer, with_headroom, with_name)
from ats_semantic import bound_text, load_model

model = load_model()
resumes = [row.asDict() for row in spark.table("workspace.is4030_silver.ats_study_resumes").collect()]
jobs = [row.asDict() for row in spark.table("workspace.is4030_silver.ats_study_jobs").collect()]
resumes = sorted(({"resume_id": r["resume_id"], "domain_group": r["domain_group"],
                   "text": with_headroom(r["text"], model)} for r in resumes if (r["text"] or "").strip()),
                 key=lambda r: r["resume_id"])
controls = [r for r in resumes if r["domain_group"] == "control"]
texts = [r["text"] for r in resumes]
reference = with_name(resumes)
named = name_variants(resumes)


def assert_fits(variants):
    for _, _, text in variants:
        tokens = len(model.tokenizer(text)["input_ids"])
        if len(text) > 1000 or tokens > model.max_seq_length:
            raise ValueError(f"A test variant would be truncated ({len(text)} chars, {tokens} tokens).")


assert_fits(named)
run_at = datetime.now(timezone.utc).isoformat()
cache, rows = {}, []
for job in sorted(jobs, key=lambda j: j["job_id"]):
    job_text = bound_text(job["text"], model)[0]
    stuffed = stuffed_variants(controls, stuffing_terms(job_text, texts))
    assert_fits(stuffed)
    for model_name, score in (("tfidf", tfidf_scorer(texts, job_text)),
                              ("minilm", minilm_scorer(model, job_text, cache))):
        for audit, pool, variants in (("name_swap", reference, named), ("keyword_stuffing", resumes, stuffed)):
            rows.extend((audit, job["job_id"], model_name, r["resume_id"], r["test_condition"],
                         r["base_score"], r["test_score"], r["base_rank"], r["test_rank"], run_at)
                        for r in paired_audit(pool, variants, score))
    print(job["job_id"], len(rows))

# COMMAND ----------
schema = ("audit string, job_id string, model_name string, resume_id string, test_condition string, "
          "base_score double, test_score double, base_rank int, test_rank int, run_at string")
spark.createDataFrame(rows, schema).write.format("delta").mode("overwrite") \
    .option("overwriteSchema", "true").saveAsTable("workspace.is4030_ops.ats_audit_results")
display(spark.sql("""
    SELECT audit, model_name, count(*) AS pairs, max(abs(test_score - base_score)) AS max_score_change,
           count_if(base_rank <= 20) AS top20_before, count_if(test_rank <= 20) AS top20_after
    FROM workspace.is4030_ops.ats_audit_results GROUP BY audit, model_name ORDER BY audit, model_name"""))
