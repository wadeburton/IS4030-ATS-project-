import os
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from web_dashboard.server import Databricks, create_app


class WebDashboardServerTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(live=False).test_client()

    def test_jobs_endpoint_lists_demo_postings_in_demo_mode(self):
        data = self.client.get("/api/jobs").get_json()
        self.assertEqual(data["mode"], "demo")
        self.assertEqual(len(data["jobs"]), 20)
        self.assertEqual(len({job["job_id"] for job in data["jobs"]}), 20, "job IDs must be unique")
        self.assertIn("Data Analyst", [job["title"] for job in data["jobs"]])
        self.assertTrue(all(job["text"] for job in data["jobs"]), "every demo job should have posting text")

    def test_jobs_endpoint_also_lists_the_tracked_skill_terms(self):
        data = self.client.get("/api/jobs").get_json()
        self.assertIn("SQL", data["skills"])
        self.assertGreater(len(data["skills"]), 5)

    def test_saved_endpoint_requires_a_job_and_a_known_model(self):
        self.assertEqual(self.client.get("/api/saved").status_code, 400)
        self.assertEqual(self.client.get("/api/saved?job_id=demo-1&model=bogus").status_code, 400)
        response = self.client.get("/api/saved?job_id=demo-1&model=both")
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "succeeded")
        self.assertEqual(data["resume_count"], 300)

    def test_scan_runs_to_completion_and_can_then_be_polled_again(self):
        start = self.client.post("/api/scans", json={"job_id": "demo-1", "model": "tfidf"})
        self.assertEqual(start.status_code, 202)
        run_id = start.get_json()["run_id"]
        time.sleep(0.9)
        result = self.client.get(f"/api/scans/{run_id}").get_json()
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(self.client.get(f"/api/scans/{run_id}").get_json()["status"], "succeeded")

    def test_scan_requires_a_known_job_and_model(self):
        self.assertEqual(self.client.post("/api/scans", json={"job_id": "demo-1", "model": "bogus"}).status_code, 400)
        self.assertEqual(self.client.post("/api/scans", json={"job_id": "nope", "model": "tfidf"}).status_code, 400)

    def test_fix_data_endpoint_returns_a_table_by_table_summary(self):
        data = self.client.post("/api/fix-data", json={}).get_json()
        self.assertEqual([row["table"] for row in data["summary"]], ["Resumes (demo)"])

    def test_agents_endpoint_lists_both_agents_and_reflects_a_completed_scan(self):
        before = self.client.get("/api/agents").get_json()
        self.assertEqual({agent["id"] for agent in before["agents"]}, {"scoring", "fix_data"})
        self.assertEqual(before["runs"], [])
        start = self.client.post("/api/scans", json={"job_id": "demo-1", "model": "tfidf"})
        run_id = start.get_json()["run_id"]
        time.sleep(0.9)
        self.client.get(f"/api/scans/{run_id}")
        after = self.client.get("/api/agents").get_json()
        self.assertEqual(after["runs"][0]["run_id"], run_id)
        self.assertEqual(after["runs"][0]["job_id"], "demo-1")
        self.assertEqual(after["runs"][0]["status"], "succeeded")

    def test_agents_endpoint_reflects_the_most_recent_fix_data_run(self):
        self.assertIsNone(self.client.get("/api/agents").get_json()["last_fix"])
        self.client.post("/api/fix-data", json={})
        data = self.client.get("/api/agents").get_json()
        self.assertEqual([row["table"] for row in data["last_fix"]], ["Resumes (demo)"])

    def test_audits_endpoint_reports_both_tests_for_both_models(self):
        data = self.client.get("/api/audits?job_id=demo-1").get_json()
        for scope, jobs in (("job", 1), ("all", 20)):
            rows = data[scope]
            self.assertEqual({(r["audit"], r["model_name"]) for r in rows},
                             {(a, m) for a in ("name_swap", "keyword_stuffing") for m in ("tfidf", "minilm")})
            self.assertEqual(sum(r["audit"] == "name_swap" and r["model_name"] == "minilm" for r in rows), 5,
                             "one row per swapped-in synthetic name")
            stuffed = next(r for r in rows if r["audit"] == "keyword_stuffing" and r["model_name"] == "tfidf")
            self.assertEqual(stuffed["pairs"], 90 * jobs)
        self.assertEqual(self.client.get("/api/audits").get_json()["job"], [])


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, parameters=None):
        if self.connection.broken:
            raise RuntimeError("connection dropped")

    def fetchall(self):
        return [SimpleNamespace(asDict=lambda: {"n": 1})]


class FakeConnection:
    def __init__(self, broken=False):
        self.broken = broken
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


class DatabricksConnectionTests(unittest.TestCase):
    def setUp(self):
        self.database = Databricks()
        self.database.__dict__["client"] = SimpleNamespace(
            config=SimpleNamespace(host="https://example.cloud.databricks.com", authenticate=lambda: {}))
        patcher = mock.patch.dict(os.environ, {"DATABRICKS_WAREHOUSE_ID": "abc"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_queries_reuse_one_warehouse_connection(self):
        with mock.patch("databricks.sql.connect", side_effect=lambda **kwargs: FakeConnection()) as connect:
            self.assertEqual(self.database.query("SELECT 1"), [{"n": 1}])
            self.assertEqual(self.database.query("SELECT 1"), [{"n": 1}])
        self.assertEqual(connect.call_count, 1)

    def test_a_dropped_connection_is_replaced_and_the_query_retried_once(self):
        connections = [FakeConnection(broken=True), FakeConnection()]
        with mock.patch("databricks.sql.connect", side_effect=lambda **kwargs: connections.pop(0)) as connect:
            self.assertEqual(self.database.query("SELECT 1"), [{"n": 1}])
        self.assertEqual(connect.call_count, 2)


class SavedRunCacheTests(unittest.TestCase):
    def make(self, status):
        database = Databricks()
        database.statements = []

        def query(statement, parameters=None):
            database.statements.append(statement)
            if "ats_run_metadata" in statement:
                return [{"run_id": "run-1", "job_id": "j", "status": status, "quality_status": "passed",
                         "resume_count": 1, "skipped_resume_count": 0, "completed_at": "t"}]
            return [{"resume_id": "r1"}]
        database.query = query
        return database

    def test_a_succeeded_runs_checks_and_scores_are_fetched_once(self):
        database = self.make("succeeded")
        first = database.saved(job_id="j", model="both")
        second = database.saved(job_id="j", model="both")
        self.assertEqual(first, second)
        self.assertEqual(sum("ats_run_scores" in s for s in database.statements), 1)
        self.assertEqual(sum("ats_run_metadata" in s for s in database.statements), 2,
                         "the latest-run lookup must still run so a newer scan is picked up")

    def test_an_unfinished_run_is_never_cached(self):
        database = self.make("running")
        database.saved(run_id="run-1")
        database.saved(run_id="run-1")
        self.assertEqual(sum("ats_run_scores" in s for s in database.statements), 2)

    def test_audit_aggregates_are_fetched_once_per_scope(self):
        database = self.make("succeeded")
        database.audits("j"), database.audits("j"), database.audits()
        statements = [s for s in database.statements if "ats_audit_results" in s]
        self.assertEqual(len(statements), 2)
        self.assertEqual(sum("WHERE job_id = :job" in s for s in statements), 1)


if __name__ == "__main__":
    unittest.main()
