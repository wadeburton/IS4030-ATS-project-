# Databricks ATS app setup

This first app version combines the resume scan controls, run history, data-quality results, ranked matches, and model comparison. It runs the existing TF-IDF/MiniLM pipeline in a Databricks job and reads/writes Delta tables through the app's SQL warehouse resource.

## One-time workspace setup

1. Switch the Databricks Git folder to branch `codex/ats-control-dashboard`, then pull the latest project files.
2. Run `notebooks/07_create_app_tables.sql` in a SQL editor. It creates operational tables and two canonical Silver input tables; it does not replace the existing gold star schema.
3. Run `notebooks/07_prepare_study_inputs.py` on serverless compute. It prepares 300 records (210 tech/data proxies and 90 controls) and two selected Data Analyst / BI job postings from the existing Bronze tables. This refreshes only `ats_study_resumes` and `ats_study_jobs`.
4. Create a Lakeflow Job with a notebook task pointing at `notebooks/08_ats_runner.py`. Define job parameters named `job_id`, `model_name`, `missing_policy`, and `ats_run_id` with defaults of empty, `tfidf`, `skip_missing`, and empty, respectively. The app passes these values when it starts a scan.
5. In **Compute > Apps**, create a Streamlit app using the `app/` folder as its source. Add app resources with these exact keys:
   - `sql-warehouse`: the SQL warehouse used by the dashboard. The app reads its ID from this resource and asks the Databricks SDK for its HTTP path.
   - `ats-runner`: the Lakeflow Job created in step 4.
6. Grant the app access to the SQL warehouse and the Silver/ops tables. The job identity needs read access to the two Silver input tables and write access to the three ops tables. The app needs read access to those tables and permission to run the configured job.
7. Deploy the app from the project’s `app/` folder and open its App URL. Choose a job and click **Find Candidates**. The app runs the quality checks and opens the run’s **Top Candidates** view when it finishes. The table displays rank, anonymous candidate ID, and match score. If you ran both models, switch methods to see each model’s top 20.

The app uses its Databricks identity through `Config()`; do not add a personal access token or password to the app files. Grant the app `CAN USE` on the warehouse, `SELECT` on its read tables, and job `Can manage and run` so it can start the scan and read job status. Grant the job's run identity `SELECT` on Silver inputs and `MODIFY` on the ops tables. If table or resource names change, update the constants in `app/app.py` and the notebook/table setup together.

## What is in this slice

- **Data quality:** required text, unique IDs, input lengths, missing-value handling, sample counts, 70/30 composition, selected job, score bounds, ranks, and score completeness.
- **Gate:** any blocking failure saves a blocked run and no candidate scores.
- **ATS methods:** scikit-learn TF-IDF keyword matching, pretrained all-MiniLM-L6-v2 semantic matching, or both.
- **Dashboard:** run selector, status cards, quality results, candidate rankings, model comparison, and a “Why” panel that shows the prepared inputs and clearly describes the limits of each method's explanation.
- **Persistence:** run metadata, per-run quality checks, and per-run score rows are appended to Delta tables in `workspace.is4030_ops`.

This is a project-scale study tool, not a production hiring system. Similarity scores are not hiring probabilities, and the MiniLM method does not offer a causal per-word explanation. The 300-resume sample is provisional until the team reviews and freezes the inputs.
