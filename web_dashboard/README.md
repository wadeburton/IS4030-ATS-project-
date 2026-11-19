# Standalone screening dashboard

Run this dashboard in a regular browser outside Databricks. The demo shows how to pick a job, launch a scan, and review the top 20 anonymous matches. Demo scores and checks are synthetic. In live mode Databricks runs the models and supplies the saved scores and quality checks.

## Launch the demo

From the repository root:

```powershell
python -m pip install -r web_dashboard/requirements.txt
python web_dashboard/server.py
```

Open http://127.0.0.1:8050 and select a job. The server binds to localhost for local use.

## Connect to Databricks

1. Follow steps 1–4 of [the Databricks setup guide](../docs/DATABRICKS-APP-SETUP.md) to prepare the tables and runner job with the four job parameters. The Databricks App steps are for the older workspace interface.
2. Sign in using the Databricks CLI. Your profile needs access to the selected SQL warehouse and prepared data tables, plus permission to start and read the runner job.
3. Set the warehouse and runner IDs in the same PowerShell window and launch live mode.

```powershell
databricks auth login --host https://dbc-4dc963bf-e25b.cloud.databricks.com --profile IS4030
$env:DATABRICKS_CONFIG_PROFILE = 'IS4030'
$env:DATABRICKS_WAREHOUSE_ID = '<SQL warehouse ID>'
$env:ATS_RUNNER_JOB_ID = '<runner job ID>'
python web_dashboard/server.py --live
```

API credentials are resolved on the Python server. The browser only receives curated job labels, rank and score rows, and quality checks. Run IDs are tracked for the lifetime of the server. To share a live deployment with teammates, host the server externally behind authenticated access with an appropriately scoped workspace identity.
