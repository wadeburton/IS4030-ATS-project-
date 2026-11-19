"""Standalone ATS dashboard. Run on localhost with demo data or Databricks."""
import argparse
import logging
import os
from functools import cached_property
from random import Random
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4

from flask import Flask, jsonify, request

JOBS = "workspace.is4030_silver.ats_study_jobs"
OPS = "workspace.is4030_ops"
MODELS = {"tfidf", "minilm", "both"}
DEMO_JOBS = [
    {"job_id": "demo-1", "title": "Data Analyst", "company": "Example Company"},
    {"job_id": "demo-2", "title": "Business Intelligence Analyst", "company": "Example Company"},
]


class Databricks:
    @cached_property
    def client(self):
        from databricks.sdk import WorkspaceClient
        return WorkspaceClient()

    def query(self, statement, parameters=None):
        from databricks import sql
        config = self.client.config
        with sql.connect(
            server_hostname=urlsplit(config.host).hostname,
            http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
            credentials_provider=lambda: config.authenticate,
        ) as connection, connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return [row.asDict() for row in cursor.fetchall()]

    def jobs(self):
        return self.query(f"SELECT job_id, title, company FROM {JOBS} ORDER BY title, job_id")

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
        params = {"run_id": run_id}
        metadata = self.query(
            f"SELECT status, quality_status, resume_count, skipped_resume_count "
            f"FROM {OPS}.ats_run_metadata WHERE run_id = :run_id", params
        )
        if not metadata:
            return {"status": "failed", "error": "Databricks finished without saving results."}
        checks = self.query(
            f"SELECT check_name, status, fail_count, detail FROM {OPS}.ats_quality_checks "
            "WHERE run_id = :run_id ORDER BY status, check_name", params
        )
        scores = self.query(
            f"SELECT resume_id, model_name, rank_position, similarity_score FROM {OPS}.ats_run_scores "
            "WHERE run_id = :run_id AND rank_position <= 20 ORDER BY model_name, rank_position", params
        )
        return {**metadata[0], "checks": checks, "scores": scores}


def demo_result(job_id, model):
    scores = []
    for method in ("tfidf", "minilm") if model == "both" else (model,):
        random = Random(f"{job_id}:{method}")
        for rank, candidate in enumerate(random.sample(range(1, 301), 20), 1):
            scores.append({"resume_id": f"DEMO-{candidate:03d}", "model_name": method,
                           "rank_position": rank, "similarity_score": round(.94 - rank * .018, 3)})
    return {"status": "succeeded", "quality_status": "warning", "resume_count": 300,
            "skipped_resume_count": 2, "scores": scores, "checks": [
                {"check_name": "Required fields", "status": "passed", "fail_count": 0,
                 "detail": "All retained demo records contain qualification text."},
                {"check_name": "Missing resume text", "status": "warning", "fail_count": 2,
                 "detail": "Two synthetic records were excluded from this example."},
            ]}


def create_app(live=False):
    app = Flask(__name__, static_url_path="/assets")
    app.config["MAX_CONTENT_LENGTH"] = 4096
    app.config["TRUSTED_HOSTS"] = ["127.0.0.1", "localhost"]
    database = Databricks() if live else None
    runs = {}

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api/jobs")
    def jobs():
        return jsonify(mode="live" if live else "demo", jobs=database.jobs() if live else DEMO_JOBS)

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
        return jsonify(demo_result(job_id, model))

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
