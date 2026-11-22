"""Standalone ATS dashboard. Run on localhost with demo data or Databricks."""
import argparse
import logging
import os
import re
from functools import cached_property
from random import Random
from threading import Lock, Thread
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4

from flask import Flask, jsonify, request

JOBS = "workspace.is4030_silver.ats_study_jobs"
RESUMES = "workspace.is4030_silver.ats_study_resumes"
OPS = "workspace.is4030_ops"
MODELS = {"tfidf", "minilm", "both"}
AUDIT_NAMES = ("Greg Baker", "Lakisha Washington", "Jamal Robinson", "Maria Hernandez", "Wei Chen")
SKILLS = ("SQL", "Python", "Power BI", "Tableau", "Excel", "R", "ETL", "statistics",
          "dashboards", "data visualization", "data modeling", "machine learning", "Spark", "Databricks")
DEMO_JOBS = [
    {"job_id": "demo-1", "title": "Data Analyst", "company": "Example Company",
     "text": "Analyze business data to support decisions across the company. Build dashboards and "
             "recurring reports using SQL, Python, and Power BI. Familiarity with statistics and data "
             "visualization is preferred; Excel skills are a must."},
    {"job_id": "demo-2", "title": "Business Intelligence Analyst", "company": "Example Company",
     "text": "Design BI dashboards and reporting pipelines for stakeholders across the business. Strong "
             "SQL and Tableau skills required; Python and ETL experience is a plus. Partner with teams "
             "to define and track key metrics."},
    {"job_id": "demo-3", "title": "Data Engineer", "company": "Example Company",
     "text": "Build and maintain ETL pipelines on Databricks and Spark. Strong Python and SQL required. "
             "Experience with data modeling and machine learning pipelines is a plus."},
    {"job_id": "demo-4", "title": "Data Scientist", "company": "Example Company",
     "text": "Apply machine learning and statistics to real-world business datasets. Proficiency in "
             "Python, SQL, and data visualization tools required. Spark or Databricks experience is a plus."},
    {"job_id": "demo-5", "title": "Reporting Analyst", "company": "Northwind Retail",
     "text": "Build recurring sales and inventory reports in Power BI and Excel. SQL experience is "
             "required; Python is a plus for automating recurring extracts."},
    {"job_id": "demo-6", "title": "Marketing Analyst", "company": "Brightpath Media",
     "text": "Measure campaign performance using SQL and Tableau. Build dashboards that track funnel "
             "metrics and support budget decisions for the marketing team."},
    {"job_id": "demo-7", "title": "Financial Analyst", "company": "Meridian Capital",
     "text": "Analyze financial datasets using Excel and SQL. Build forecasting models and present "
             "findings to leadership; Python experience is a plus."},
    {"job_id": "demo-8", "title": "Operations Analyst", "company": "Harborline Logistics",
     "text": "Monitor operational KPIs across the supply chain using SQL and dashboards. Identify "
             "process bottlenecks and recommend data-backed improvements."},
    {"job_id": "demo-9", "title": "Analytics Manager", "company": "Clearwater Health",
     "text": "Lead a small analytics team building dashboards and statistical models in Python and "
             "Power BI. Strong SQL skills and stakeholder communication are required."},
    {"job_id": "demo-10", "title": "Machine Learning Engineer", "company": "Vertex Robotics",
     "text": "Build and deploy machine learning models using Python and Spark. Experience with "
             "Databricks pipelines and data modeling is preferred."},
    {"job_id": "demo-11", "title": "Data Visualization Specialist", "company": "Lumen Insights",
     "text": "Design clear dashboards and visual reports in Tableau and Power BI. Strong SQL skills and "
             "an eye for data storytelling are required."},
    {"job_id": "demo-12", "title": "ETL Developer", "company": "Ferrous Systems",
     "text": "Build and maintain ETL pipelines moving data between systems using SQL, Python, and "
             "Spark. Databricks experience is a plus."},
    {"job_id": "demo-13", "title": "Research Analyst", "company": "Academix Group",
     "text": "Apply statistics and R to analyze survey and research datasets. SQL and data "
             "visualization skills are required."},
    {"job_id": "demo-14", "title": "Product Analyst", "company": "Nimbus Apps",
     "text": "Analyze product usage data using SQL and Python. Build dashboards tracking engagement "
             "and retention metrics for the product team."},
    {"job_id": "demo-15", "title": "Sales Analyst", "company": "Keystone Distributors",
     "text": "Track sales performance using Excel and Power BI. SQL skills are required to query the "
             "data warehouse directly."},
    {"job_id": "demo-16", "title": "Healthcare Data Analyst", "company": "Willowbrook Medical",
     "text": "Analyze patient outcomes data using SQL and statistics. Experience with dashboards and "
             "data modeling is preferred."},
    {"job_id": "demo-17", "title": "Supply Chain Analyst", "company": "Anchor Freight",
     "text": "Analyze logistics and inventory data using SQL and Excel. Build dashboards to track "
             "delivery performance across the network."},
    {"job_id": "demo-18", "title": "Data Governance Analyst", "company": "Trustline Bank",
     "text": "Document data quality rules and lineage across SQL data models. Experience with ETL "
             "pipelines and dashboards is preferred."},
    {"job_id": "demo-19", "title": "Business Analyst", "company": "Summit Consulting",
     "text": "Gather requirements and build reporting solutions using SQL, Excel, and Power BI. Strong "
             "stakeholder communication skills are required."},
    {"job_id": "demo-20", "title": "Database Administrator", "company": "Granite Systems",
     "text": "Maintain and optimize SQL databases supporting analytics workloads. Experience with ETL "
             "and Databricks is a plus."},
]
AGENTS = [
    {"id": "scoring", "name": "Scoring Agent",
     "description": "Reads the prepared Silver study tables and runs TF-IDF and/or MiniLM "
                     "similarity scoring through the Databricks ATS runner job, then writes "
                     "the run, quality-check, and score rows to the ops tables."},
    {"id": "fix_data", "name": "Data Quality Agent",
     "description": "Trims extra spaces from prepared resume and job text and reports missing "
                     "fields or duplicate IDs in the Silver study tables for review."},
]


class Databricks:
    _connection = None

    @cached_property
    def _runs(self):
        return {}

    @cached_property
    def client(self):
        from databricks.sdk import WorkspaceClient
        return WorkspaceClient()

    @cached_property
    def _lock(self):
        return Lock()

    def _connect(self):
        from databricks import sql
        config = self.client.config
        return sql.connect(
            server_hostname=urlsplit(config.host).hostname,
            http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
            credentials_provider=lambda: config.authenticate,
        )

    def query(self, statement, parameters=None):
        # One warehouse connection is kept open and reused: opening one per query cost
        # roughly half a second each, and a saved-run load makes three queries.
        with self._lock:
            for attempt in (1, 2):
                try:
                    if self._connection is None:
                        self._connection = self._connect()
                    with self._connection.cursor() as cursor:
                        cursor.execute(statement, parameters)
                        return [row.asDict() for row in cursor.fetchall()]
                except Exception:
                    connection, self._connection = self._connection, None
                    try:
                        if connection is not None:
                            connection.close()
                    except Exception:
                        pass
                    if attempt == 2:
                        raise

    def jobs(self):
        return self.query(f"SELECT job_id, title, company, text FROM {JOBS} ORDER BY title, job_id")

    def history(self, limit=10):
        return self.query(
            f"SELECT run_id, job_id, model_name, status, quality_status, resume_count, "
            f"skipped_resume_count, completed_at FROM {OPS}.ats_run_metadata "
            f"ORDER BY completed_at DESC LIMIT {int(limit)}"
        )

    def start(self, job_id, model, run_id):
        waiter = self.client.jobs.run_now(
            job_id=int(os.environ["ATS_RUNNER_JOB_ID"]),
            idempotency_token=run_id,
            job_parameters={"job_id": job_id, "model_name": model,
                            "missing_policy": "skip_missing", "ats_run_id": run_id},
        )
        return waiter.response.run_id

    def status(self, run_id, job_run_id):
        state = self.client.jobs.get_run(run_id=job_run_id).state
        lifecycle = state.life_cycle_state.value if state and state.life_cycle_state else "PENDING"
        if lifecycle not in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
            return {"status": lifecycle.lower()}
        return self.saved(run_id=run_id) or {
            "status": "failed", "error": "Databricks finished without saving results."
        }

    def saved(self, *, job_id=None, model=None, run_id=None):
        if run_id:
            condition = "run_id = :run_id"
            parameters = {"run_id": run_id}
        else:
            condition = "job_id = :job AND status = 'succeeded' AND model_name IN (:model, 'both')"
            parameters = {"job": job_id, "model": model}
        metadata = self.query(
            f"SELECT run_id, job_id, status, quality_status, resume_count, skipped_resume_count, completed_at "
            f"FROM {OPS}.ats_run_metadata WHERE {condition} ORDER BY completed_at DESC, run_id LIMIT 1",
            parameters
        )
        if not metadata:
            return None
        params = {"run_id": metadata[0]["run_id"]}
        # A succeeded run's rows never change, so its checks and scores are fetched once.
        cached = self._runs.get(params["run_id"])
        if cached:
            return {**metadata[0], **cached}
        checks = self.query(
            f"SELECT check_name, status, fail_count, detail FROM {OPS}.ats_quality_checks "
            "WHERE run_id = :run_id ORDER BY status, check_name", params
        )
        scores = self.query(
            f"SELECT s.resume_id, s.model_name, s.rank_position, s.similarity_score, "
            f"r.source_dataset, r.domain_group FROM {OPS}.ats_run_scores s "
            f"LEFT JOIN {RESUMES} r ON s.resume_id = r.resume_id "
            "WHERE s.run_id = :run_id ORDER BY s.model_name, s.rank_position", params
        )
        if metadata[0]["status"] == "succeeded":
            if len(self._runs) >= 64:
                self._runs.pop(next(iter(self._runs)))
            self._runs[params["run_id"]] = {"checks": checks, "scores": scores}
        return {**metadata[0], "checks": checks, "scores": scores}

    def search(self, run_id, term):
        rows = self.query(
            f"SELECT DISTINCT s.resume_id FROM {OPS}.ats_run_scores s "
            f"JOIN {RESUMES} r ON s.resume_id = r.resume_id WHERE s.run_id = :run "
            "AND (contains(lower(s.resume_id), lower(:term)) OR contains(lower(r.text), lower(:term)))",
            {"run": run_id, "term": term}
        )
        return [row["resume_id"] for row in rows]

    def evidence(self, run_id, candidate):
        rows = self.query(
            f"SELECT DISTINCT r.text AS resume_text, j.text AS job_text FROM {OPS}.ats_run_scores s "
            f"JOIN {RESUMES} r ON s.resume_id = r.resume_id JOIN {JOBS} j ON s.job_id = j.job_id "
            "WHERE s.run_id = :run AND s.resume_id = :candidate LIMIT 1",
            {"run": run_id, "candidate": candidate}
        )
        if not rows:
            return None
        def terms(text):
            return [skill for skill in SKILLS if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", text or "", re.I)]
        job_terms = terms(rows[0]["job_text"])
        resume_terms = terms(rows[0]["resume_text"])
        return {"matched": [term for term in job_terms if term in resume_terms],
                "not_found": [term for term in job_terms if term not in resume_terms]}

    def audits(self, job_id=None):
        """Aggregated name-swap and keyword-stuffing results (notebook 10), for one job or all."""
        key = ("audits", job_id)
        if key not in self._runs:
            self._runs[key] = self.query(
                "SELECT audit, model_name, test_condition, count(*) AS pairs, "
                "avg(test_score - base_score) AS mean_change, max(abs(test_score - base_score)) AS max_change, "
                "count_if(abs(test_rank - base_rank) >= 5) AS moved_5, max(abs(test_rank - base_rank)) AS max_rank_move, "
                "count_if(base_rank <= 20) AS top20_before, count_if(test_rank <= 20) AS top20_after, "
                "count_if((base_rank <= 20) <> (test_rank <= 20)) AS top20_changed, "
                "median(base_rank) AS median_rank_before, median(test_rank) AS median_rank_after "
                f"FROM {OPS}.ats_audit_results " + ("WHERE job_id = :job " if job_id else "")
                + "GROUP BY audit, model_name, test_condition ORDER BY audit, model_name, test_condition",
                {"job": job_id} if job_id else None)
        return self._runs[key]

    def fix_data(self):
        summary = []
        for label, table, key in (("Resumes", RESUMES, "resume_id"), ("Jobs", JOBS, "job_id")):
            # The scorer already ignores boundary spaces. Leave blank fields and repeated IDs for review.
            changed = self.query(f"UPDATE {table} SET text = trim(text) WHERE length(trim(text)) > 0 AND text <> trim(text)")
            counts = self.query(
                f"SELECT count_if(text IS NULL OR trim(text) = '') AS missing_text, "
                f"count_if({key} IS NULL OR trim({key}) = '') AS missing_ids, "
                f"count({key}) - count(DISTINCT {key}) AS duplicate_ids, "
                f"count_if(length(trim(text)) > 0 AND text <> trim(text)) AS remaining_spaces FROM {table}"
            )[0]
            summary.append({"table": label, "trimmed": next(iter(changed[0].values())) if changed else None, **counts})
        return summary


def demo_result(job_id, model):
    scores = []
    for method in ("tfidf", "minilm") if model == "both" else (model,):
        random = Random(f"{job_id}:{method}")
        for rank, candidate in enumerate(random.sample(range(1, 301), 300), 1):
            scores.append({"resume_id": f"DEMO-{candidate:03d}", "model_name": method,
                           "rank_position": rank, "similarity_score": round(.94 - rank * .0028, 3),
                           "source_dataset": "Synthetic demo", "domain_group": "control" if candidate > 210 else "tech_data_proxy"})
    return {"status": "succeeded", "quality_status": "warning", "resume_count": 300,
            "skipped_resume_count": 2, "scores": scores, "checks": [
                {"check_name": "Required fields", "status": "passed", "fail_count": 0,
                 "detail": "All retained demo records contain qualification text."},
                {"check_name": "Missing resume text", "status": "warning", "fail_count": 2,
                 "detail": "Two synthetic records were excluded from this example."},
            ]}


def demo_audits(job_id=None):
    """Synthetic stand-in shaped like Databricks.audits(); the numbers are illustrative only."""
    jobs = 1 if job_id else len(DEMO_JOBS)
    random = Random(f"audit:{job_id}")
    rows = []
    for model in ("minilm", "tfidf"):
        keyword = model == "tfidf"
        for name in AUDIT_NAMES:
            moved = 0 if keyword else random.randint(8, 30) * jobs
            rows.append({"audit": "name_swap", "model_name": model, "test_condition": name, "pairs": 300 * jobs,
                         "mean_change": 0.0 if keyword else round(random.uniform(-.02, .004), 4),
                         "max_change": 0.0 if keyword else round(random.uniform(.03, .08), 4),
                         "moved_5": moved, "max_rank_move": 0 if keyword else random.randint(20, 60),
                         "top20_before": 20 * jobs, "top20_after": 20 * jobs,
                         "top20_changed": 0 if keyword else random.randint(0, 3) * jobs,
                         "median_rank_before": 150.5, "median_rank_after": 150.5})
        after = (random.randint(35, 60) if keyword else random.randint(3, 12)) * jobs
        rows.append({"audit": "keyword_stuffing", "model_name": model, "test_condition": "stuffed", "pairs": 90 * jobs,
                     "mean_change": .21 if keyword else .09, "max_change": .4 if keyword else .2,
                     "moved_5": 88 * jobs, "max_rank_move": 280, "top20_before": jobs, "top20_after": after,
                     "top20_changed": after - jobs, "median_rank_before": 240.0,
                     "median_rank_after": 38.0 if keyword else 120.0})
    return rows


def create_app(live=False):
    app = Flask(__name__, static_url_path="/assets")
    app.config["MAX_CONTENT_LENGTH"] = 4096
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["TRUSTED_HOSTS"] = ["127.0.0.1", "localhost"]
    database = Databricks() if live else None
    if live:
        # Sign in and open the warehouse connection in the background so the first
        # page load doesn't pay the ~4 s cold start.
        Thread(target=lambda: database.query("SELECT 1"), daemon=True).start()
    runs = {}
    scan_history = []
    recorded_runs = set()
    last_fix = {"summary": None}

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api/jobs")
    def jobs():
        return jsonify(mode="live" if live else "demo", jobs=database.jobs() if live else DEMO_JOBS, skills=SKILLS)

    @app.get("/api/saved")
    def saved():
        job_id, model = request.args.get("job_id"), request.args.get("model")
        if not job_id or model not in MODELS:
            return jsonify(error="Choose a job and scoring method."), 400
        result = database.saved(job_id=job_id, model=model) if live else demo_result(job_id, "both")
        return jsonify(result) if result else (jsonify(error="No saved rankings yet. Use Re-run scoring."), 404)

    @app.get("/api/saved/<uuid:run_id>/search")
    def search(run_id):
        term = request.args.get("q", "").strip()
        if not 2 <= len(term) <= 80:
            return jsonify(error="Enter 2 to 80 characters."), 400
        return jsonify(ids=database.search(str(run_id), term) if live else [])

    @app.get("/api/saved/<uuid:run_id>/evidence")
    def evidence(run_id):
        candidate = request.args.get("candidate", "")
        result = database.evidence(str(run_id), candidate) if live and candidate else None
        return jsonify(result) if result else (jsonify(error="No skill evidence is available."), 404)

    @app.post("/api/fix-data")
    def fix_data():
        if not request.is_json:
            return jsonify(error="Send a JSON request."), 415
        summary = database.fix_data() if live else [
            {"table": "Resumes (demo)", "trimmed": 0, "missing_text": 2, "missing_ids": 0,
             "duplicate_ids": 0, "remaining_spaces": 0}
        ]
        last_fix["summary"] = summary
        return jsonify(summary=summary)

    @app.get("/api/agents")
    def agents():
        recent = database.history(limit=10) if live else list(reversed(scan_history))[:10]
        return jsonify(agents=AGENTS, runs=recent, last_fix=last_fix["summary"])

    @app.get("/api/audits")
    def audits():
        job_id = request.args.get("job_id") or None
        fetch = database.audits if live else demo_audits
        return jsonify(job=fetch(job_id) if job_id else [], all=fetch())

    @app.post("/api/scans")
    def scan():
        if not request.is_json:
            return jsonify(error="Send a JSON request."), 415
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="Send a job and scoring method."), 400
        job_id, model = body.get("job_id"), body.get("model")
        if not isinstance(job_id, str) or not isinstance(model, str) or model not in MODELS:
            return jsonify(error="Choose a job and scoring method."), 400
        options = database.jobs() if live else DEMO_JOBS
        if job_id not in {row["job_id"] for row in options}:
            return jsonify(error="Choose an available job."), 400
        run_id = str(uuid4())
        job_run_id = database.start(job_id, model, run_id) if live else None
        runs[run_id] = (job_id, model, job_run_id, monotonic())
        return jsonify(run_id=run_id), 202

    @app.get("/api/scans/<uuid:run_id>")
    def get_scan(run_id):
        run_id = str(run_id)
        if run_id not in runs:
            return jsonify(error="This scan is no longer available. Start a new scan."), 404
        job_id, model, job_run_id, started = runs[run_id]
        if live:
            return jsonify(database.status(run_id, job_run_id))
        if monotonic() - started < 0.8:
            return jsonify(status="running")
        result = demo_result(job_id, model)
        if run_id not in recorded_runs:
            recorded_runs.add(run_id)
            scan_history.append({"run_id": run_id, "job_id": job_id, "model_name": model,
                                  "status": result["status"], "quality_status": result.get("quality_status"),
                                  "resume_count": result.get("resume_count"),
                                  "skipped_resume_count": result.get("skipped_resume_count")})
        return jsonify(result)

    @app.errorhandler(Exception)
    def api_error(error):
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return jsonify(error=error.name), error.code
        logging.exception("ATS dashboard request failed")
        return jsonify(error="Could not complete the dashboard request. Check the server log."), 502

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Connect to Databricks instead of using synthetic data")
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()
    if args.live:
        for name in ("DATABRICKS_WAREHOUSE_ID", "ATS_RUNNER_JOB_ID"):
            if not os.environ.get(name):
                parser.error(f"Set {name} before launching live mode.")
    create_app(args.live).run(host="127.0.0.1", port=args.port)
