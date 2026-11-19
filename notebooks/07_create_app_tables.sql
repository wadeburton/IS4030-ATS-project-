-- Run once before deploying app/app.py. Existing preview and gold tables are untouched.
CREATE SCHEMA IF NOT EXISTS workspace.is4030_ops;
CREATE SCHEMA IF NOT EXISTS workspace.is4030_silver;

CREATE TABLE IF NOT EXISTS workspace.is4030_silver.ats_study_resumes (
  resume_id STRING,
  text STRING,
  source_dataset STRING,
  domain_group STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS workspace.is4030_silver.ats_study_jobs (
  job_id STRING,
  source_id STRING,
  title STRING,
  company STRING,
  text STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS workspace.is4030_ops.ats_run_metadata (
  run_id STRING,
  status STRING,
  job_id STRING,
  model_name STRING,
  quality_status STRING,
  resume_count INT,
  skipped_resume_count INT,
  score_count INT,
  started_at STRING,
  completed_at STRING,
  error_message STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS workspace.is4030_ops.ats_quality_checks (
  run_id STRING,
  check_name STRING,
  status STRING,
  severity STRING,
  input_count INT,
  fail_count INT,
  detail STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS workspace.is4030_ops.ats_run_scores (
  run_id STRING,
  evaluation_id STRING,
  resume_id STRING,
  job_id STRING,
  model_name STRING,
  similarity_score DOUBLE,
  rank_position INT,
  test_condition_id STRING
) USING DELTA;
