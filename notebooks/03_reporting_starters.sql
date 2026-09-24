-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Reporting queries return no study results until scoring is loaded
-- COMMAND ----------
SELECT model_name, COUNT(*) AS evaluations, AVG(similarity_score) AS mean_similarity FROM workspace.is4030_gold.fact_evaluation GROUP BY model_name;
-- COMMAND ----------
SELECT f.job_id, j.title, f.model_name, f.resume_id, f.similarity_score, f.rank_position FROM workspace.is4030_gold.fact_evaluation f JOIN workspace.is4030_gold.dim_job j ON f.job_id=j.job_id ORDER BY f.job_id,f.model_name,f.rank_position;
-- COMMAND ----------
SELECT evaluation_id, COUNT(*) AS duplicate_count FROM workspace.is4030_gold.fact_evaluation GROUP BY evaluation_id HAVING COUNT(*) > 1;
-- COMMAND ----------
SELECT COUNT(*) AS invalid_scores_or_ranks FROM workspace.is4030_gold.fact_evaluation WHERE similarity_score < 0 OR similarity_score > 1 OR rank_position < 1;
-- COMMAND ----------
SELECT COUNT(*) AS orphan_evaluations FROM workspace.is4030_gold.fact_evaluation f
LEFT JOIN workspace.is4030_gold.dim_resume r ON f.resume_id=r.resume_id
LEFT JOIN workspace.is4030_gold.dim_job j ON f.job_id=j.job_id
LEFT JOIN workspace.is4030_gold.dim_model m ON f.model_name=m.model_name
LEFT JOIN workspace.is4030_gold.dim_test_condition t ON f.test_condition_id=t.test_condition_id
WHERE r.resume_id IS NULL OR j.job_id IS NULL OR m.model_name IS NULL OR t.test_condition_id IS NULL;
