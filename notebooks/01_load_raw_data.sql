-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Load the three raw sources without replacing existing tables
-- COMMAND ----------
CREATE TABLE IF NOT EXISTS workspace.is4030_bronze.resume_dataset
USING DELTA
COMMENT 'Raw source records; columns normalized by position; not cleaned candidate profiles'
AS SELECT *, 'saugataroyarghya/resume-dataset' AS source_dataset
FROM read_files('/Volumes/workspace/is4030_bronze/raw_files/resume_data.csv', format => 'csv', header => true,
  schema => '`address` STRING, `career_objective` STRING, `skills` STRING, `educational_institution_name` STRING, `degree_names` STRING, `passing_years` STRING, `educational_results` STRING, `result_types` STRING, `major_field_of_studies` STRING, `professional_company_names` STRING, `company_urls` STRING, `start_dates` STRING, `end_dates` STRING, `related_skils_in_job` STRING, `positions` STRING, `locations` STRING, `responsibilities` STRING, `extra_curricular_activity_types` STRING, `extra_curricular_organization_names` STRING, `extra_curricular_organization_links` STRING, `role_positions` STRING, `languages` STRING, `proficiency_levels` STRING, `certification_providers` STRING, `certification_skills` STRING, `online_links` STRING, `issue_dates` STRING, `expiry_dates` STRING, `job_position_name` STRING, `educational_requirements` STRING, `experiencere_requirement` STRING, `age_requirement` STRING, `responsibilities_1` STRING, `skills_required` STRING, `matched_score` STRING', enforceSchema => true,
  multiLine => true, escape => '"', mode => 'FAILFAST');
-- COMMAND ----------
CREATE TABLE IF NOT EXISTS workspace.is4030_bronze.linkedin_jobs
USING DELTA
COMMENT 'Raw source records; columns normalized by position; not cleaned candidate profiles'
AS SELECT *, 'joykimaiyo18/linkedin-data-jobs-dataset' AS source_dataset
FROM read_files('/Volumes/workspace/is4030_bronze/raw_files/clean_jobs.csv', format => 'csv', header => true,
  schema => '`id` STRING, `title` STRING, `company` STRING, `location` STRING, `link` STRING, `source` STRING, `date_posted` STRING, `work_type` STRING, `employment_type` STRING, `description` STRING', enforceSchema => true,
  multiLine => true, escape => '"', mode => 'FAILFAST');
-- COMMAND ----------
CREATE TABLE IF NOT EXISTS workspace.is4030_bronze.recruitment_dataset
USING DELTA
COMMENT 'Raw source records; columns normalized by position; not cleaned candidate profiles'
AS SELECT *, 'surendra365/recruitement-dataset' AS source_dataset
FROM read_files('/Volumes/workspace/is4030_bronze/raw_files/job_applicant_dataset.csv', format => 'csv', header => true,
  schema => '`job_applicant_name` STRING, `age` STRING, `gender` STRING, `race` STRING, `ethnicity` STRING, `resume` STRING, `job_roles` STRING, `job_description` STRING, `best_match` STRING', enforceSchema => true,
  multiLine => true, escape => '"', mode => 'FAILFAST');
