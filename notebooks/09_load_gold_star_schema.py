# Databricks notebook source
# MAGIC %md
# MAGIC # Load the Gold star schema
# MAGIC Populates the 1-fact / 4-dimension star schema in `workspace.is4030_gold` from the
# MAGIC prepared Silver study inputs and the ops tables the dashboard writes to. Each table
# MAGIC load is an `INSERT OVERWRITE`, so this notebook is safe to re-run after a fresh scoring
# MAGIC pass: it always reflects the current frozen choice below, never accumulates duplicates.
# MAGIC
# MAGIC **Frozen run choice:** `fact_evaluation` has no `run_id` column — its grain is one row per
# MAGIC resume/job/model/test-condition. For each `(job_id, model_name)` pair this loads only the
# MAGIC scores from the single most recent **succeeded** run, so re-running a scan twice never
# MAGIC creates duplicate fact rows for the same job/model.

# COMMAND ----------
# MAGIC %md ## dim_model and dim_test_condition (fixed reference rows)

# COMMAND ----------
spark.sql("""
INSERT OVERWRITE TABLE workspace.is4030_gold.dim_model (model_name, method, model_version)
VALUES
  ('tfidf', 'Keyword overlap (TF-IDF cosine similarity)', 'scikit-learn TfidfVectorizer'),
  ('minilm', 'Pretrained semantic embedding (cosine similarity)', 'sentence-transformers/all-MiniLM-L6-v2')
""")

# COMMAND ----------
spark.sql("""
INSERT OVERWRITE TABLE workspace.is4030_gold.dim_test_condition (test_condition_id, description)
VALUES
  ('normal', 'Normal scoring: each resume''s original prepared qualification text and the job''s original prepared requirements text, with no identity-cue changes.')
""")

# COMMAND ----------
# MAGIC %md ## dim_resume and dim_job (from the frozen Silver study inputs)

# COMMAND ----------
spark.sql("""
INSERT OVERWRITE TABLE workspace.is4030_gold.dim_resume
  (resume_id, source_dataset, source_row_id, domain_group, qualification_text)
SELECT resume_id, source_dataset, CAST(NULL AS STRING), domain_group, text
FROM workspace.is4030_silver.ats_study_resumes
""")

# COMMAND ----------
spark.sql("""
INSERT OVERWRITE TABLE workspace.is4030_gold.dim_job
  (job_id, title, company, job_family, requirements_text, source_dataset, source_row_id)
SELECT job_id, title, company, 'Data Analyst / Business Intelligence', text, 'linkedin_jobs', source_id
FROM workspace.is4030_silver.ats_study_jobs
""")

# COMMAND ----------
# MAGIC %md ## fact_evaluation (one frozen run per job/model from the ops tables)

# COMMAND ----------
spark.sql("""
INSERT OVERWRITE TABLE workspace.is4030_gold.fact_evaluation
  (evaluation_id, resume_id, job_id, model_name, similarity_score, rank_position, test_condition_id)
WITH frozen_runs AS (
  SELECT run_id, job_id, model_name,
         ROW_NUMBER() OVER (PARTITION BY job_id, model_name ORDER BY completed_at DESC) AS rn
  FROM (
    SELECT DISTINCT s.run_id, s.job_id, s.model_name, m.completed_at
    FROM workspace.is4030_ops.ats_run_scores s
    JOIN workspace.is4030_ops.ats_run_metadata m ON s.run_id = m.run_id
    WHERE m.status = 'succeeded'
  )
)
SELECT s.evaluation_id, s.resume_id, s.job_id, s.model_name, s.similarity_score, s.rank_position, s.test_condition_id
FROM workspace.is4030_ops.ats_run_scores s
JOIN frozen_runs f ON s.run_id = f.run_id AND s.job_id = f.job_id AND s.model_name = f.model_name
WHERE f.rn = 1
""")

# COMMAND ----------
# MAGIC %md ## Verify: re-run the Part 03 reporting/integrity checks

# COMMAND ----------
display(spark.sql("""
SELECT model_name, COUNT(*) AS evaluations, AVG(similarity_score) AS mean_similarity
FROM workspace.is4030_gold.fact_evaluation GROUP BY model_name
"""))

# COMMAND ----------
display(spark.sql("""
SELECT COUNT(*) AS duplicate_grain_rows FROM (
  SELECT resume_id, job_id, model_name, test_condition_id, COUNT(*) AS n
  FROM workspace.is4030_gold.fact_evaluation
  GROUP BY resume_id, job_id, model_name, test_condition_id HAVING COUNT(*) > 1
)
"""))

# COMMAND ----------
display(spark.sql("""
SELECT COUNT(*) AS invalid_scores_or_ranks FROM workspace.is4030_gold.fact_evaluation
WHERE similarity_score < 0 OR similarity_score > 1 OR rank_position < 1
"""))

# COMMAND ----------
display(spark.sql("""
SELECT COUNT(*) AS orphan_evaluations FROM workspace.is4030_gold.fact_evaluation f
LEFT JOIN workspace.is4030_gold.dim_resume r ON f.resume_id = r.resume_id
LEFT JOIN workspace.is4030_gold.dim_job j ON f.job_id = j.job_id
LEFT JOIN workspace.is4030_gold.dim_model m ON f.model_name = m.model_name
LEFT JOIN workspace.is4030_gold.dim_test_condition t ON f.test_condition_id = t.test_condition_id
WHERE r.resume_id IS NULL OR j.job_id IS NULL OR m.model_name IS NULL OR t.test_condition_id IS NULL
"""))
