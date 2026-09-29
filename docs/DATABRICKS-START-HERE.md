# Start here in Databricks

Open **Workspace > Shared > IS4030-ATS-project > notebooks**. Use the existing **Serverless Starter Warehouse** for the SQL notebooks. The warehouse has a 10-minute automatic stop setting.

## What is set up

| Location | Purpose |
| --- | --- |
| `workspace.is4030_bronze` | Original source tables and the `raw_files` volume |
| `workspace.is4030_silver` | Space for cleaned, deduplicated study inputs; currently empty |
| `workspace.is4030_gold` | Empty reporting star tables, ready for validated study results |
| `workspace.is4030_ops.source_manifest` | Source links, filenames, raw row counts, checksums, and download-check date |

The original CSVs are stored at `/Volumes/workspace/is4030_bronze/raw_files/`. Raw records stay in Databricks and are excluded from GitHub. The repository contains notebooks, instructions, and source metadata only.

## Notebook order

1. **00_setup.sql:** creates schemas, the volume, and empty star tables if missing. It does not drop or replace tables.
2. **01_load_raw_data.sql:** loads original files into Bronze tables if the tables do not already exist. The initial load is performed during setup. Column names are normalized; source values are not cleaned. The exact mapping is in `docs/source-manifest.json`.
3. **02_inspect_sources.sql:** inspect role distributions, missing skills, repeated job descriptions, and repeated resume text. These queries support source review; they do not select the final study pool.
4. **03_reporting_starters.sql:** starter queries for scores, ranks, duplicate evaluation IDs, and orphan dimension keys. Score queries are empty until valid study results are loaded.
5. **04_test_missing_inputs.py:** Python notebook for testing incomplete data. Select serverless notebook compute, choose `missing_policy = skip_missing`, then run the cells. `error` is the default strict setting. The notebook reads a maximum of 100 rows per source and displays an audit without writing any tables. It prepares inputs only; it does not run model scoring.

### Optional missing-value handling

The reusable `ats_inputs.prepare_records` function accepts `missing_policy="skip_missing"` to omit blank or missing selected fields and skip records with no usable text. It recognizes nulls, NaN, blanks, `None`, `N/A`, and empty lists, including missing values inside lists. Available qualifications retain their wording and technical punctuation. Missing or duplicate IDs still raise an error.

Use `missing_policy="error"` to stop on missing selected fields. Both modes label inputs as provisional. This switch handles missing values only; it does not certify cleansing, deduplication, relevance, or model token budgets. Preserve its audit when comparing runs, since skipping records changes the evaluated population.

Local verification: `python -m unittest discover -s tests -v`. The option was also exercised on the downloaded source files: 1,288 structured resume rows retained partial qualifications and four job rows had no usable description and were skipped. These checks do not establish final study eligibility.

Run one cell at a time when learning. Keep screenshots of loading results and checks for Deliverable 2 and the final tutorial. Never use `CREATE OR REPLACE` or overwrite existing study results without reviewing what will be lost.

## Team handoffs

- **Data Engineer:** inspect the three Bronze tables, review source quality, and build cleaned inputs in Silver. Select 2 or 3 Data Analyst / Business Intelligence jobs and 300 to 500 resumes with the agreed 70/30 relevant/control split. Deduplicate before sampling. Do not put demographic data or applicant names into normal model inputs.
- **BI Data Architect:** review the starter star schema, draw the ERD, and define loading and key-validation rules. Required fact fields reject null values. This workspace rejected SQL CHECK constraints, so score bounds, positive ranks, uniqueness, and dimension relationships require explicit validation queries before results are accepted. The starter schema represents one frozen study run; agree on a run key or separate storage before retaining multiple runs.
- **Project Manager / AI and Testing Lead:** build and test the keyword and MiniLM scoring pipeline, perform the controlled name audit, and export the agreed fact columns. No AI scoring has been run as part of workspace setup.
- **Business Strategist:** develop the independent 1–5 human-review rubric, coordinate review, and write the business case and research. Synthetic source records and labels cannot establish real hiring discrimination.
- **Dashboard Developer:** begin the three page layouts and review query needs with the Architect. Build the final visuals once verified model and review results exist. The reporting notebook is not a finished dashboard.

All roles contribute screenshots, tutorial steps, and actual AI verification entries. The Project Manager leads formal testing and integrates submissions.

## GitHub workflow

The Git folder is connected to the team's repository. Use **Pull** to get repository updates. Use a task branch, review changes, then commit and push code or notebook changes. Changes in Databricks do not automatically appear in GitHub.

Each teammate should link their own GitHub account and use their own Git folder for development. Use the shared folder for the agreed baseline; coordinate changes there so teammates do not switch each other's branches. Workspace users, table permissions, and GitHub collaborator invitations are separate setup steps and have not been granted automatically.

Do not commit raw CSVs, resume text, personal access tokens, `.databrickscfg`, OAuth credentials, or local environment folders. Source downloads and metadata do not mean the data is fully quality-verified.

## What remains

Cleaning and final sampling, AI scoring, human ratings, controlled name experiments, star-table population, and the interactive dashboard are still work tracked by the five GitHub issues. The current setup supports the data foundation and early software-use evidence without inventing results.
