# Databricks notebook source
# MAGIC %md
# MAGIC # ATS gated scoring job
# MAGIC Reads the prepared Silver study tables, records quality checks, blocks scoring on critical failures, and appends run-scoped rows to the operations tables.

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

from ats_pipeline import run_ats
from pyspark.sql.types import StructField, StructType, StringType, IntegerType, DoubleType

dbutils.widgets.text("job_id", "")
dbutils.widgets.text("model_name", "tfidf")
dbutils.widgets.text("missing_policy", "skip_missing")
job_id = dbutils.widgets.get("job_id")
model_name = dbutils.widgets.get("model_name")
missing_policy = dbutils.widgets.get("missing_policy")

if not job_id:
    raise ValueError("A selected job_id is required.")

resume_rows = [row.asDict() for row in spark.table("workspace.is4030_silver.ats_study_resumes").collect()]
job_rows = [row.asDict() for row in spark.table("workspace.is4030_silver.ats_study_jobs").collect()]
run_id = str(__import__("uuid").uuid4())

try:
    result = run_ats(resume_rows, job_rows, job_id=job_id, model_name=model_name,
                     missing_policy=missing_policy, run_id=run_id, study_mode=True)
except Exception as exc:
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "run": {"run_id": run_id, "status": "failed", "job_id": job_id,
                "model_name": model_name, "quality_status": "failed", "resume_count": 0,
                "skipped_resume_count": 0, "score_count": 0, "started_at": now,
                "completed_at": now, "error_message": str(exc)},
        "quality": {"checks": [{"run_id": run_id, "check_name": "pipeline_execution",
                                  "status": "failed", "severity": "blocking", "input_count": 0,
                                  "fail_count": 1, "detail": str(exc)}]},
        "scores": [],
    }

ops_schema = "workspace.is4030_ops"
run = dict(result["run"])
run.setdefault("error_message", None)
run_schema = StructType([StructField(name, kind, True) for name, kind in [
    ("run_id", StringType()), ("status", StringType()), ("job_id", StringType()),
    ("model_name", StringType()), ("quality_status", StringType()),
    ("resume_count", IntegerType()), ("skipped_resume_count", IntegerType()),
    ("score_count", IntegerType()), ("started_at", StringType()),
    ("completed_at", StringType()), ("error_message", StringType())]])
check_schema = StructType([StructField(name, kind, True) for name, kind in [
    ("run_id", StringType()), ("check_name", StringType()), ("status", StringType()),
    ("severity", StringType()), ("input_count", IntegerType()), ("fail_count", IntegerType()),
    ("detail", StringType())]])
score_schema = StructType([StructField(name, kind, True) for name, kind in [
    ("run_id", StringType()), ("evaluation_id", StringType()), ("resume_id", StringType()),
    ("job_id", StringType()), ("model_name", StringType()), ("similarity_score", DoubleType()),
    ("rank_position", IntegerType()), ("test_condition_id", StringType())]])

spark.createDataFrame([run], run_schema).write.format("delta").mode("append").saveAsTable(f"{ops_schema}.ats_run_metadata")
spark.createDataFrame(result["quality"]["checks"], check_schema).write.format("delta").mode("append").saveAsTable(f"{ops_schema}.ats_quality_checks")
spark.createDataFrame(result["scores"], score_schema).write.format("delta").mode("append").saveAsTable(f"{ops_schema}.ats_run_scores")

print(f"Run {run_id}: {run['status']} ({run['score_count']} scores)")
