# Databricks notebook source
# MAGIC %md
# MAGIC # Keyword ranking preview
# MAGIC Synthetic examples only. This does not write to project tables.
# MAGIC Select serverless Python compute. Run the cells in order.

# COMMAND ----------
# MAGIC %pip install scikit-learn==1.9.1

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd().parent))
from ats_inputs import prepare_records
from ats_scoring import score_keyword

dbutils.widgets.dropdown('missing_policy', 'error', ['error', 'skip_missing'])
jobs = [{'job_id': 'demo-j1', 'text': 'SQL Python Power BI dashboards'},
        {'job_id': 'demo-j2', 'text': 'Excel reporting business analysis'}]
raw_resumes = [
    {'resume_id': 'demo-r1', 'text': 'SQL Python Power BI dashboards'},
    {'resume_id': 'demo-r2', 'text': 'Analyzed business performance and created interactive reports'},
    {'resume_id': 'demo-r3', 'text': 'Nursing patient care hospital'},
    {'resume_id': 'demo-r4', 'text': 'SQL Python Power BI dashboards'},
]
resumes, audit = prepare_records(raw_resumes, 'resume_id', ['text'],
                                missing_policy=dbutils.widgets.get('missing_policy'))
jobs, _ = prepare_records(jobs, 'job_id', ['text'])
results = score_keyword(resumes, jobs)
display(spark.createDataFrame(results).orderBy('job_id', 'rank_position'))
print('Provisional keyword preview only. r1/r4 are identical-text tie controls, not a name audit.')

