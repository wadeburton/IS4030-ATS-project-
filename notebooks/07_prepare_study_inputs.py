# Databricks notebook source
# MAGIC %md
# MAGIC # Prepare ATS study inputs
# MAGIC Samples 300 resumes and two Data Analyst / BI jobs from the Bronze tables. This creates the Silver inputs used by the dashboard's gated run job. The output is a provisional study sample and should be reviewed before final analysis.

# COMMAND ----------
# MAGIC %pip install sentence-transformers==6.1.0 scikit-learn==1.9.1

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))

from ats_semantic import load_model
from ats_preview import build_preview

model = load_model()
structured = [r.asDict() for r in spark.sql("""
 SELECT skills, positions, responsibilities, degree_names, major_field_of_studies
 FROM workspace.is4030_bronze.resume_dataset
 WHERE lower(positions) RLIKE 'data|analyst|software|developer|engineer|business intelligence'
 ORDER BY sha2(concat_ws('|', skills, positions, responsibilities), 256)
 LIMIT 500
""").collect()]
recruitment = [r.asDict() for r in spark.sql("""
 SELECT resume, job_roles AS role, job_applicant_name AS applicant_name
 FROM workspace.is4030_bronze.recruitment_dataset
 WHERE lower(job_roles) RLIKE 'data|analyst|software|developer|engineer|business intelligence|nurse|sales|health'
 ORDER BY sha2(concat_ws('|', resume, job_roles), 256)
 LIMIT 1200
""").collect()]
jobs = [r.asDict() for r in spark.sql("""
 SELECT id AS source_id, title, company, description
 FROM workspace.is4030_bronze.linkedin_jobs
 WHERE lower(title) RLIKE 'data analyst|business intelligence' AND length(description) > 150
 ORDER BY sha2(description, 256)
 LIMIT 20
""").collect()]

resumes, selected_jobs, _, prep_audit = build_preview(structured, recruitment, jobs, model, score=False)
assert len(resumes) == 300, f"Expected 300 resumes, got {len(resumes)}"
assert len(selected_jobs) == 2, f"Expected 2 jobs, got {len(selected_jobs)}"
assert sum(r['domain_group'] == 'tech_data_proxy' for r in resumes) == 210
assert sum(r['domain_group'] == 'control' for r in resumes) == 90

resume_rows = [{key: r[key] for key in ['resume_id', 'text', 'source_dataset', 'domain_group']}
               for r in resumes]
job_rows = [{key: j.get(key, '') for key in ['job_id', 'source_id', 'title', 'company', 'text']}
            for j in selected_jobs]
spark.createDataFrame(resume_rows).write.format('delta').mode('overwrite').option(
    'overwriteSchema', 'true').saveAsTable('workspace.is4030_silver.ats_study_resumes')
spark.createDataFrame(job_rows).write.format('delta').mode('overwrite').option(
    'overwriteSchema', 'true').saveAsTable('workspace.is4030_silver.ats_study_jobs')

print(f"Prepared {len(resumes)} resumes and {len(selected_jobs)} jobs.")
print(f"Preparation audit summary: {prep_audit}")
display(spark.table('workspace.is4030_silver.ats_study_resumes').groupBy(
    'source_dataset', 'domain_group').count().orderBy('domain_group', 'source_dataset'))
