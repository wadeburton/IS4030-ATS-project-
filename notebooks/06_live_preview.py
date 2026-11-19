# Databricks notebook source
# MAGIC %md
# MAGIC # ATS live-data preview
# MAGIC Uses skip_missing, 300 resumes and two jobs. Creates new preview tables only.
# MAGIC Preview scores are not hiring probabilities or validated accuracy.

# COMMAND ----------
# MAGIC %pip install sentence-transformers==6.1.0 scikit-learn==1.9.1

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
from ats_semantic import load_model
from ats_preview import build_preview

model=load_model()
structured=[r.asDict() for r in spark.sql("""SELECT skills,positions,responsibilities,degree_names,major_field_of_studies
 FROM workspace.is4030_bronze.resume_dataset WHERE lower(positions) RLIKE 'data|analyst|software|developer|engineer|business intelligence'
 ORDER BY sha2(concat_ws('|',skills,positions,responsibilities),256) LIMIT 500""").collect()]
recruitment=[r.asDict() for r in spark.sql("""SELECT resume,job_roles AS role,job_applicant_name AS applicant_name FROM workspace.is4030_bronze.recruitment_dataset
 WHERE lower(job_roles) RLIKE 'data|analyst|software|developer|engineer|business intelligence|nurse|sales|health'
 ORDER BY sha2(concat_ws('|',resume,job_roles),256) LIMIT 1200""").collect()]
jobs=[r.asDict() for r in spark.sql("""SELECT id AS source_id,title,company,description FROM workspace.is4030_bronze.linkedin_jobs
 WHERE lower(title) RLIKE 'data analyst|business intelligence' AND length(description)>150
 ORDER BY sha2(description,256) LIMIT 20""").collect()]
resumes,jobs,results,quality=build_preview(structured,recruitment,jobs,model)

# COMMAND ----------
# Unique run suffix avoids replacing teammates' work or final study tables.
from datetime import datetime, timezone
suffix=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
tables={}
for name,rows in [('resumes',resumes),('jobs',jobs),('scores',results),('quality',quality)]:
    table=f'workspace.is4030_silver.preview_{name}_{suffix}'
    spark.createDataFrame(rows).write.format('delta').mode('errorifexists').saveAsTable(table)
    tables[name]=table
assert len(results)==1200
assert len({r['evaluation_id'] for r in results})==1200
display(spark.createDataFrame(results).orderBy('job_id','model_name','rank_position'))
dbutils.notebook.exit(json.dumps({'tables':tables,'resumes':len(resumes),'jobs':len(jobs),'scores':len(results)}))
