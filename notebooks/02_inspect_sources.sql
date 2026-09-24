-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Inspect data before cleaning
-- COMMAND ----------
SELECT * FROM workspace.is4030_ops.source_manifest;
-- COMMAND ----------
SELECT title, COUNT(*) AS records FROM workspace.is4030_bronze.linkedin_jobs GROUP BY title ORDER BY records DESC;
-- COMMAND ----------
SELECT job_roles, COUNT(*) AS records FROM workspace.is4030_bronze.recruitment_dataset GROUP BY job_roles ORDER BY records DESC;
-- COMMAND ----------
SELECT COUNT(*) AS raw_records, COUNT(DISTINCT description) AS unique_descriptions FROM workspace.is4030_bronze.linkedin_jobs;
-- COMMAND ----------
SELECT COUNT(*) AS raw_records, COUNT(DISTINCT resume) AS unique_resume_texts FROM workspace.is4030_bronze.recruitment_dataset;
-- COMMAND ----------
SELECT COUNT(*) AS raw_records, COUNT_IF(skills IS NULL OR TRIM(skills) = '') AS missing_skills FROM workspace.is4030_bronze.resume_dataset;
