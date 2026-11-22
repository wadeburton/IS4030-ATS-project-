import unittest

from ats_audits import REFERENCE_NAME, SWAP_NAMES, name_variants, paired_audit, stuffed_variants, stuffing_terms, tfidf_scorer, with_name

RESUMES = [
    {"resume_id": "r1", "text": "sql python dashboards reporting analyst"},
    {"resume_id": "r2", "text": "sql excel reporting"},
    {"resume_id": "r3", "text": "registered nurse patient care hospital"},
]
JOB = "data analyst sql python tableau dashboards"


class PairedAuditTests(unittest.TestCase):
    def test_rank_is_recomputed_against_the_other_resumes_unchanged_scores(self):
        scores = {"a": 0.9, "b": 0.5, "c": 0.1, "c-boosted": 0.7}
        resumes = [{"resume_id": key, "text": key} for key in ("a", "b", "c")]
        rows = paired_audit(resumes, [("c", "stuffed", "c-boosted")], lambda texts: [scores[t] for t in texts])
        self.assertEqual(rows, [{"resume_id": "c", "test_condition": "stuffed", "base_score": 0.1,
                                 "test_score": 0.7, "base_rank": 3, "test_rank": 2}])

    def test_an_unchanged_variant_keeps_its_score_and_rank(self):
        resumes = [{"resume_id": key, "text": key} for key in ("a", "b")]
        rows = paired_audit(resumes, [("b", "same", "b")], lambda texts: [{"a": 0.4, "b": 0.4}[t] for t in texts])
        self.assertEqual((rows[0]["base_rank"], rows[0]["test_rank"]), (1, 1), "ties share a rank both times")


class VariantTests(unittest.TestCase):
    def test_every_resume_gets_every_swap_name_with_identical_qualifications(self):
        variants = name_variants(RESUMES)
        self.assertEqual(len(variants), len(RESUMES) * len(SWAP_NAMES))
        self.assertNotIn(REFERENCE_NAME, SWAP_NAMES)
        self.assertEqual(with_name(RESUMES)[0]["text"], f"name: {REFERENCE_NAME}\n{RESUMES[0]['text']}")
        for resume_id, name, text in variants:
            original = next(r["text"] for r in RESUMES if r["resume_id"] == resume_id)
            self.assertEqual(text, f"name: {name}\n{original}")

    def test_stuffing_terms_come_from_the_posting_and_are_appended(self):
        terms = stuffing_terms(JOB, [r["text"] for r in RESUMES], n=3)
        self.assertEqual(len(terms), 3)
        self.assertTrue(set(terms) <= set(JOB.split()))
        self.assertIn("tableau", terms, "a term no resume uses is the most distinctive")
        (resume_id, condition, text), = stuffed_variants(RESUMES[2:], terms)
        self.assertEqual((resume_id, condition), ("r3", "stuffed"))
        self.assertTrue(text.startswith(RESUMES[2]["text"]) and text.endswith(", ".join(terms)))


class TfidfAuditTests(unittest.TestCase):
    def setUp(self):
        self.score = tfidf_scorer([r["text"] for r in RESUMES], JOB)

    def test_stuffing_job_keywords_lifts_an_unrelated_resume(self):
        terms = stuffing_terms(JOB, [r["text"] for r in RESUMES], n=5)
        row, = paired_audit(RESUMES, stuffed_variants(RESUMES[2:], terms), self.score)
        self.assertEqual(row["base_rank"], 3)
        self.assertGreater(row["test_score"], row["base_score"])
        self.assertLess(row["test_rank"], 3)

    def test_a_name_the_fitted_vocabulary_never_saw_cannot_move_the_keyword_score(self):
        for row in paired_audit(with_name(RESUMES), name_variants(RESUMES), self.score):
            self.assertAlmostEqual(row["test_score"], row["base_score"], places=9)
            self.assertEqual(row["test_rank"], row["base_rank"])


if __name__ == "__main__":
    unittest.main()
