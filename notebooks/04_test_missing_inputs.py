# Databricks notebook source
# MAGIC %md
# MAGIC # Test with incomplete inputs
# MAGIC This notebook reads small previews from Bronze. It does not overwrite raw,
# MAGIC cleaned, or reporting tables and does not run either scoring model.
# MAGIC Choose **skip_missing** to omit missing qualification fields and audit skipped rows.
# MAGIC Choose **error** to stop when a selected field is missing.
# MAGIC Every prepared record remains **provisional**, even when all selected fields exist.

# COMMAND ----------
dbutils.widgets.dropdown('missing_policy', 'error', ['error', 'skip_missing'])
missing_policy = dbutils.widgets.get('missing_policy')

# COMMAND ----------
import sys
from pathlib import Path

# Databricks Git notebooks run with their containing folder as the working directory.
repo_root = Path.cwd().parent
if not (repo_root / 'ats_inputs.py').exists():
    raise RuntimeError('Open this notebook inside the project Git folder so ats_inputs.py is available.')
sys.path.insert(0, str(repo_root))
from ats_inputs import prepare_records
from collections import Counter
import pandas as pd

# COMMAND ----------
# Demonstration: the first row has partial qualifications, the second has none.
mock = [
    {'resume_id': 'demo-1', 'skills': "['SQL', 'C++', None]", 'experience': 'N/A'},
    {'resume_id': 'demo-2', 'skills': None, 'experience': 'null'},
    {'resume_id': 'demo-3', 'skills': 'Power BI', 'experience': 'Built reports'},
]
try:
    prepared_demo, demo_audit = prepare_records(
        mock, 'resume_id', ['skills', 'experience'], missing_policy=missing_policy)
    print('PROVISIONAL TEST INPUTS', dict(Counter(r['action'] for r in demo_audit)))
    display(pd.DataFrame(demo_audit))
except ValueError as error:
    print(f'Strict check stopped as expected: {error}')
    print('Choose skip_missing above and rerun to continue using available qualifications.')

# COMMAND ----------
# Only candidate qualification fields are selected. No names, demographics,
# supplied match labels, or job requirements are included in resume inputs.
sources = [
    ('structured', 'workspace.is4030_bronze.resume_dataset',
     ['skills', 'positions', 'responsibilities', 'degree_names', 'major_field_of_studies']),
    ('recruitment', 'workspace.is4030_bronze.recruitment_dataset', ['resume']),
    ('jobs', 'workspace.is4030_bronze.linkedin_jobs', ['description']),
]
preview_inputs = {}
preview_audit = {}
for source, table, fields in sources:
    # This is a bounded smoke-test preview, not the final 70/30 study sample.
    rows = spark.table(table).select(*fields).orderBy(*fields).limit(100).collect()
    records = [dict(row.asDict(), record_id=f'{source}-preview-{i:04d}')
               for i, row in enumerate(rows, 1)]
    try:
        prepared, audit = prepare_records(records, 'record_id', fields,
                                          missing_policy=missing_policy)
    except ValueError as error:
        print(f'{source}: STOPPED: {error}')
        continue
    preview_inputs[source] = prepared
    preview_audit[source] = audit
    print(source, 'PROVISIONAL', dict(Counter(r['action'] for r in audit)))
    display(pd.DataFrame(audit))
    if not prepared:
        print('No usable records. Do not attempt scoring for this source.')

# COMMAND ----------
# MAGIC %md
# MAGIC ## Next step
# MAGIC `preview_inputs` holds the prepared records, and `preview_audit` explains every decision.
# MAGIC Missing values are not replaced with invented skills or zero qualification scores.
# MAGIC These previews still need boilerplate removal, deduplication, stable study IDs,
# MAGIC token-budget checks, and reviewed sampling before real evaluation.
# MAGIC Preview IDs identify rows within this preview only. They are not warehouse candidate keys.
