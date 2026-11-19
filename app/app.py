"""Databricks-hosted ATS operations and analytics dashboard."""
import os
from uuid import uuid4

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config


RUNS = "workspace.is4030_ops.ats_run_metadata"
CHECKS = "workspace.is4030_ops.ats_quality_checks"
SCORES = "workspace.is4030_ops.ats_run_scores"
JOBS = "workspace.is4030_silver.ats_study_jobs"


st.set_page_config(page_title="ATS Screening Workbench", page_icon="◈", layout="wide")
st.markdown("""
<style>
  .stApp { background: #f5f7fb; }
  [data-testid="stSidebar"] { background: #101b32; }
  [data-testid="stSidebar"] * { color: #edf2ff !important; }
  .hero { padding: 1.3rem 1.5rem; border-radius: 16px; color: white;
    background: linear-gradient(115deg,#12213d,#164e63); margin-bottom: 1rem; }
  .hero h1 { margin: 0; font-size: 1.8rem; }
  .hero p { margin: .35rem 0 0; color: #c5d9e8; }
  div[data-testid="stMetric"] { background:white; padding:1rem; border-radius:12px;
    border:1px solid #e5eaf2; }
</style>
<div class="hero"><h1>ATS Screening Workbench</h1>
<p>Run a controlled resume match, check data quality, and inspect how each score was produced.</p></div>
""", unsafe_allow_html=True)


def _sql():
    cfg = Config()
    workspace = WorkspaceClient(config=cfg)
    warehouse = workspace.warehouses.get(os.environ["DATABRICKS_WAREHOUSE_ID"])
    return sql.connect(
        server_hostname=cfg.host.removeprefix("https://").removeprefix("http://"),
        http_path=warehouse.odbc_params.path,
        credentials_provider=lambda: cfg.authenticate,
    )


def query(statement):
    with _sql() as connection, connection.cursor() as cursor:
        cursor.execute(statement)
        names = [column[0] for column in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=names)


def run_statement(job_id, job_parameters):
    client = WorkspaceClient(config=Config())
    response = client.jobs.run_now(job_id=int(job_id), job_parameters=job_parameters)
    return response.run_id


def get_job_status(run_id):
    run = WorkspaceClient(config=Config()).jobs.get_run(run_id=int(run_id))
    state = run.state
    life_cycle = getattr(state.life_cycle_state, "value", state.life_cycle_state)
    result_state = getattr(state.result_state, "value", state.result_state)
    return life_cycle, result_state, state.state_message


@st.cache_data(ttl=20, show_spinner=False)
def load_jobs():
    return query(f"SELECT job_id, title, company FROM {JOBS} ORDER BY title")


@st.cache_data(ttl=20, show_spinner=False)
def load_runs():
    return query(f"SELECT * FROM {RUNS} ORDER BY started_at DESC LIMIT 100")


jobs = load_jobs()
runs = load_runs()
if jobs.empty:
    st.warning("Study job table is empty. Run the project data-preparation notebook first.")
    st.code(JOBS)
    st.stop()

job_labels = {
    row.job_id: f"{row.title}" + (f" · {row.company}" if row.company else "")
    for row in jobs.itertuples(index=False)
}
history_ids = runs["run_id"].astype(str).tolist() if not runs.empty else []
completed_run_id = st.session_state.pop("completed_run_id", None)
if completed_run_id in history_ids:
    st.session_state["inspect_run"] = completed_run_id
elif completed_run_id:
    st.error("This scan ended without saved results. Check the Databricks job run for details.")

with st.sidebar:
    st.markdown("### ATS controls")
    selected_job = st.selectbox("Target job", jobs["job_id"].tolist(), format_func=job_labels.get)
    selected_model = st.selectbox("Scoring method", ["tfidf", "minilm", "both"],
                                  format_func={"tfidf": "Keyword baseline (TF-IDF)",
                                               "minilm": "Semantic model (MiniLM)",
                                               "both": "Compare both methods"}.get)
    missing_policy = st.selectbox("Missing required text", ["skip_missing", "error"],
                                  format_func={"skip_missing": "Skip and record missing rows",
                                               "error": "Block if required text is missing"}.get)
    st.caption("Scores indicate text similarity. They are not hiring probabilities.")
    start = st.button("Find Candidates", type="primary", use_container_width=True,
                      disabled=bool(st.session_state.get("submitted_job_run_id")))
    if start:
        try:
            with st.spinner("Submitting the Databricks run…"):
                run_id = str(uuid4())
                submitted_id = run_statement(
                    os.environ["ATS_RUNNER_JOB_ID"],
                    {"job_id": str(selected_job), "model_name": selected_model,
                     "missing_policy": missing_policy, "ats_run_id": run_id},
                )
            st.session_state["submitted_job_run_id"] = submitted_id
            st.session_state["submitted_ats_run_id"] = run_id
            st.rerun()
        except Exception as exc:
            st.error(f"Could not start the ATS job: {exc}")
    st.divider()
    st.markdown("### Recent runs")
    if st.button("Refresh run history", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if not history_ids:
        st.caption("No saved runs yet.")
        selected_run = None
    else:
        selected_run = st.selectbox("Inspect run", history_ids,
                                    key="inspect_run",
                                    format_func=lambda rid: f"{rid[:8]} · " +
                                    str(runs.loc[runs.run_id.astype(str) == rid, "status"].iloc[0]))

@st.fragment(run_every=5)
def watch_scan():
    try:
        lifecycle, result_state, message = get_job_status(st.session_state["submitted_job_run_id"])
        st.info(f"Databricks job: {lifecycle}" + (f" · {result_state}" if result_state else "") +
                (f" · {message}" if message else ""))
        if lifecycle in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
            st.session_state.pop("submitted_job_run_id")
            st.session_state["completed_run_id"] = st.session_state.pop("submitted_ats_run_id")
            load_runs.clear()
            st.rerun()
    except Exception as exc:
        st.warning(f"Could not read the submitted job status: {exc}")


if st.session_state.get("submitted_job_run_id"):
    watch_scan()
    st.stop()

if selected_run is None:
    st.info("Choose a target job and run the pipeline. Saved scores and quality checks will appear here after the job finishes.")
    st.stop()

def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


run_data = runs[runs.run_id.astype(str) == selected_run]
if run_data.empty:
    st.error("The selected run is no longer available.")
    st.stop()
run_row = run_data.iloc[0]
quality = query(f"SELECT * FROM {CHECKS} WHERE run_id = {literal(selected_run)} ORDER BY severity, check_name")
scores = query(f"SELECT * FROM {SCORES} WHERE run_id = {literal(selected_run)} ORDER BY rank_position")

candidates_tab, overview, quality_tab, compare_tab = st.tabs(
    ["Top Candidates", "Overview", "Data quality", "Model comparison"]
)
with overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Run status", str(run_row.get("status", "unknown")).title())
    c2.metric("Quality gate", str(run_row.get("quality_status", "unknown")).title())
    c3.metric("Usable resumes", int(run_row.get("resume_count", 0) or 0))
    c4.metric("Scores saved", int(run_row.get("score_count", 0) or 0))
    st.subheader("Run details")
    st.write({key: run_row[key] for key in ["run_id", "job_id", "model_name", "started_at", "completed_at"]
              if key in run_row.index})
    if run_row.get("error_message"):
        st.error(str(run_row["error_message"]))
    if str(run_row.get("status")) == "blocked":
        st.error("Scoring was blocked by a critical data-quality check. Review the Data quality tab.")
    elif str(run_row.get("quality_status")) == "warning":
        st.warning("This run completed with recorded data-quality warnings. Review them before interpreting results.")

with quality_tab:
    st.subheader("Checks for this run")
    if quality.empty:
        st.info("No checks were saved for this run.")
    else:
        st.dataframe(quality, use_container_width=True, hide_index=True)
        failed = int((quality["status"] == "failed").sum())
        warned = int((quality["status"] == "warning").sum())
        st.caption(f"{failed} failed · {warned} warnings · {len(quality) - failed - warned} passed")

with candidates_tab:
    job_label = job_labels.get(run_row["job_id"], run_row["job_id"])
    st.subheader(f"Top 20 candidates for {job_label}")
    if scores.empty:
        st.info("No scores were saved. A blocked or failed run will not show candidates.")
    else:
        scores["similarity_score"] = pd.to_numeric(scores["similarity_score"], errors="coerce")
        method_options = sorted(scores["model_name"].unique())
        method = st.selectbox("Scoring method", method_options, key=f"candidate_method_{selected_run}",
                              format_func={"tfidf": "TF-IDF", "minilm": "MiniLM"}.get)
        visible = scores[scores.model_name == method].sort_values("rank_position").head(20)
        leaderboard = visible[["rank_position", "resume_id", "similarity_score"]]
        st.dataframe(leaderboard, use_container_width=True, hide_index=True,
                     column_config={"rank_position": "Rank", "resume_id": "Candidate ID",
                                    "similarity_score": st.column_config.NumberColumn(
                                        "Match score (0–1)", format="%.3f")})
        with st.expander("Why did a candidate receive this score?"):
            if not visible.empty:
                selected_resume = st.selectbox("Candidate", visible["resume_id"].tolist(), key="why_candidate")
                selected_result = visible[visible.resume_id == selected_resume].iloc[0]
                input_rows = query(
                    f"SELECT 'resume' AS text_type, text FROM {JOBS.replace('ats_study_jobs','ats_study_resumes')} "
                    f"WHERE resume_id = {literal(selected_resume)} UNION ALL "
                    f"SELECT 'job' AS text_type, text FROM {JOBS} WHERE job_id = {literal(selected_result.job_id)}"
                )
                st.write(f"**Method:** {selected_result.model_name} · **Score:** "
                         f"{float(selected_result.similarity_score):.3f} · **Rank:** "
                         f"{int(selected_result.rank_position)}")
                if selected_result.model_name == "tfidf":
                    resume_text = " ".join(input_rows.loc[input_rows.text_type == "resume", "text"].astype(str))
                    job_text = " ".join(input_rows.loc[input_rows.text_type == "job", "text"].astype(str))
                    tokens = lambda value: {word.casefold() for word in value.split() if len(word) > 2}
                    shared = sorted(tokens(resume_text) & tokens(job_text))
                    st.write("Shared text terms to inspect: " + (", ".join(shared[:40]) if shared else "No exact shared terms."))
                    st.caption("These shared terms help review the keyword match. They are not a decomposition of the TF-IDF cosine score.")
                else:
                    st.write("MiniLM converts the prepared resume and job text to embeddings, then compares them with cosine similarity.")
                    st.caption("The semantic score does not provide a reliable per-word causal explanation; inspect both inputs below.")
                for row in input_rows.itertuples(index=False):
                    with st.expander(f"Prepared {row.text_type} text"):
                        st.text(str(row.text)[:4000])

with compare_tab:
    st.subheader("Method comparison")
    if scores.empty or scores["model_name"].nunique() < 2:
        st.info("Run both methods to compare their score distributions and candidate ranks.")
    else:
        st.bar_chart(scores.pivot_table(index="rank_position", columns="model_name",
                                        values="similarity_score", aggfunc="mean"))
        st.dataframe(scores.pivot_table(index="resume_id", columns="model_name",
                                        values=["similarity_score", "rank_position"], aggfunc="first"),
                     use_container_width=True)
