-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Create the project schemas and empty star tables
-- COMMAND ----------
CREATE SCHEMA IF NOT EXISTS workspace.is4030_bronze;
-- COMMAND ----------
CREATE SCHEMA IF NOT EXISTS workspace.is4030_silver;
-- COMMAND ----------
CREATE SCHEMA IF NOT EXISTS workspace.is4030_gold;
-- COMMAND ----------
CREATE SCHEMA IF NOT EXISTS workspace.is4030_ops;
-- COMMAND ----------
CREATE VOLUME IF NOT EXISTS workspace.is4030_bronze.raw_files;
-- COMMAND ----------
CREATE TABLE IF NOT EXISTS workspace.is4030_gold.dim_resume (
resume_id STRING NOT NULL, source_dataset STRING, source_row_id STRING,
domain_group STRING, qualification_text STRING) USING DELTA;
-- COMMAND ----------
CREATE TABLE IF NOT EXISTS workspace.is4030_gold.dim_job (
job_id STRING NOT NULL, title STRING, company STRING, job_family STRING,
requirements_text STRING, source_dataset STRING, source_row_id STRING) USING DELTA;
-- COMMAND ----------
CREATE TABLE IF NOT EXISTS workspace.is4030_gold.dim_model (
model_name STRING NOT NULL, method STRING, model_version STRING) USING DELTA;
-- COMMAND ----------
CREATE TABLE IF NOT EXISTS workspace.is4030_gold.dim_test_condition (
test_condition_id STRING NOT NULL, description STRING) USING DELTA;
-- COMMAND ----------
CREATE TABLE IF NOT EXISTS workspace.is4030_gold.fact_evaluation (
evaluation_id STRING NOT NULL, resume_id STRING NOT NULL, job_id STRING NOT NULL,
model_name STRING NOT NULL, similarity_score DECIMAL(4,3) NOT NULL,
rank_position INT NOT NULL, test_condition_id STRING NOT NULL) USING DELTA
COMMENT 'Empty starter fact: one resume/job/model/condition per frozen run. Validate key uniqueness and dimension joins before loading.';
-- COMMAND ----------
CREATE TABLE IF NOT EXISTS workspace.is4030_ops.source_manifest (
source_dataset STRING, source_url STRING, filename STRING, raw_row_count BIGINT,
sha256 STRING, volume_path STRING, checked_date DATE) USING DELTA;
