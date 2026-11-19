# IS 4030 dashboard handoff for Claude

The team is building a standalone browser dashboard for a resume matching study. Databricks runs scoring and stores the results. The dashboard is a Flask app with plain HTML, CSS, and JavaScript.

## Open the right checkout

- GitHub: [wadeburton/IS4030-ATS-project-](https://github.com/wadeburton/IS4030-ATS-project-)
- Active branch: `codex/ats-control-dashboard`. The descriptive analytics landed in `f758858`.
- Existing checkout on Wade’s PC: `C:\Users\wades\OneDrive\Documents\ChatGPT\IS 4030 project\.build-databricks\repo`. Open Claude Code in that folder. Check `git status -sb` before editing.
- To work from a fresh checkout, run:

```powershell
git clone --branch codex/ats-control-dashboard https://github.com/wadeburton/IS4030-ATS-project-.git
cd IS4030-ATS-project-
```

## Connect to the existing workspace

Use Claude Code on the same Windows account to reuse its Databricks CLI OAuth profile. The profile `IS4030` was valid on November 19, 2026. On another machine or if expired, sign in in the browser when prompted:

```powershell
databricks auth profiles
databricks auth login --host https://dbc-4dc963bf-e25b.cloud.databricks.com --profile IS4030
```

Credentials stay in the CLI's local authentication store. A GitHub checkout alone grants no access to the workspace. For a teammate's login, check SQL warehouse access, `SELECT` on the Silver and ops tables, and permission to run the scan job. **Fix Data** also requires `MODIFY` on the two Silver study tables. The dashboard uses the Databricks Python SDK and SQL connector. An MCP connection is optional for agent queries.

## Launch and verify

Run these commands from the repo root. Use the existing `.venv\Scripts\python.exe` in place of `python` if you are working in Wade’s checkout.

```powershell
python -m pip install -r web_dashboard/requirements.txt
$env:DATABRICKS_CONFIG_PROFILE = 'IS4030'
$env:DATABRICKS_WAREHOUSE_ID = 'b5fcad890d7d8f13'
$env:ATS_RUNNER_JOB_ID = '753433383365592'
python web_dashboard/server.py --live --port 8051
```

Open [the local dashboard](http://127.0.0.1:8051/). If Wade's live server is already running on 8051, reuse it for frontend edits or launch a separate instance on 8052 to test Python changes. Refresh the browser for frontend edits. Restart the corresponding server for Python edits.

Read-only smoke check in a second PowerShell window:

```powershell
$base = 'http://127.0.0.1:8051'
$jobs = Invoke-RestMethod "$base/api/jobs"
$job = $jobs.jobs | Where-Object title -eq 'Data Analyst'
$result = Invoke-RestMethod "$base/api/saved?job_id=$($job.job_id)&model=both"
$result | Select-Object status, resume_count, quality_status, completed_at
$result.scores | Where-Object rank_position -le 20 | Group-Object model_name | Select-Object Name, Count
```

Expect live mode, two job postings, a successful saved run with 300 resumes, and 20 ranked rows per model after filtering. In the browser choose **Data Analyst → Find Candidates → Analytics**. The November 19 saved run showed nine candidates in both models’ top 20. Retest after a scoring change since the result can change.

## Where to edit

| Change | File |
| --- | --- |
| Layout, sections, and labels | `web_dashboard/static/index.html` |
| Black, white, gray, and red styling | `web_dashboard/static/style.css` |
| Search, candidate details, charts, and controls | `web_dashboard/static/workbench.js` |
| Databricks SQL queries and job calls | `web_dashboard/server.py` |
| Quality gate and scoring logic | `ats_pipeline.py`, `ats_scoring.py`, `ats_semantic.py` |
| Notebook run and table definitions | `notebooks/08_ats_runner.py`, `notebooks/07_create_app_tables.sql` |

**Workspace objects.** The [live job](https://dbc-4dc963bf-e25b.cloud.databricks.com/jobs/753433383365592?o=7474654738873265) runs `/Shared/IS4030-ATS-runner/notebooks/08_ats_runner`. That folder contains uploaded copies of the Python modules from this branch. Dashboard edits run locally. If you edit scoring code, update the corresponding deployed workspace files explicitly after reviewing the change. A GitHub push does not sync those copies.

**Data flow.** Inputs are `workspace.is4030_silver.ats_study_jobs` and `workspace.is4030_silver.ats_study_resumes`. Saved runs use `workspace.is4030_ops.ats_run_metadata`, `ats_run_scores`, and `ats_quality_checks`. Those are the dashboard’s operational tables. The course Gold star schema is separate.

**Keep the demo fast.** Both existing postings have successful TF-IDF and MiniLM results. **Find Candidates** reads them in about three seconds on a warm warehouse. **Re-run scoring** starts a fresh job and can take about three minutes. There is no plan to add more data for this demo. Keep raw resume text, credentials, and tokens out of GitHub and the browser. **Fix Data** trims spaces in prepared text and reports missing values and duplicate IDs for review.
