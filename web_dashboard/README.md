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

1. The IS4030 workspace has an [ATS Scan job](https://dbc-4dc963bf-e25b.cloud.databricks.com/jobs/753433383365592?o=7474654738873265) and a Serverless Starter Warehouse. For another workspace, use steps 1–4 of [the Databricks setup guide](../docs/DATABRICKS-APP-SETUP.md) to create the tables and runner.
2. Sign in using the Databricks CLI. Your profile needs access to the selected SQL warehouse and prepared data tables, plus permission to start and read the runner job.
3. Set the warehouse and runner IDs in the same PowerShell window and launch live mode.

```powershell
databricks auth login --host https://dbc-4dc963bf-e25b.cloud.databricks.com --profile IS4030
$env:DATABRICKS_CONFIG_PROFILE = 'IS4030'
$env:DATABRICKS_WAREHOUSE_ID = 'b5fcad890d7d8f13'
$env:ATS_RUNNER_JOB_ID = '753433383365592'
python web_dashboard/server.py --live --port 8051
```

Open http://127.0.0.1:8051. API credentials stay on the Python server. The browser receives job labels, candidate IDs, scores, and quality checks. Run IDs are tracked for the lifetime of the server. A shared deployment needs authenticated access and a workspace identity scoped to the warehouse, tables, and scan job.

## Demo flow

1. Pick a posting and click **Find Candidates**. The app loads the latest successful saved Databricks run for that posting and method, with the time it was scored. A **Compare both models** request uses a run that scored both models.
2. Search by candidate ID or text in the prepared resume. Results include matching candidates outside the original top 20. Click a candidate ID to see their available scores, ranks, source, and tracked skill terms found in the job and resume.
3. Open **Charts** to see the score distribution and sample mix for the current ranking method. These charts use the full scored cohort.
4. Open **Data Quality** and click **Fix Data** to trim leading and trailing spaces in usable prepared text. It checks for leftover spaces, missing inputs, and duplicate IDs. Missing fields and duplicates stay available for review. The app does not write to the raw tables.
5. Use **Re-run scoring** to request a fresh Databricks job. Keep the warehouse available and open the dashboard shortly before presenting so you can confirm both jobs have saved results.
