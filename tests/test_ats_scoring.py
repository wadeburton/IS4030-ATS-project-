import unittest

from ats_scoring import score_keyword


class KeywordScoringTests(unittest.TestCase):
    def test_invalid_inputs_fail_and_technical_terms_remain_distinct(self):
        jobs = [{'job_id': 'j', 'text': 'C++'}]
        for resumes in ([], [{'resume_id': 'r', 'text': None}],
                        [{'resume_id': 'r', 'text': 'SQL'}] * 2,
                        [{'resume_id': 'r', 'text': ['SQL']} ]):
            with self.subTest(resumes=resumes), self.assertRaises(ValueError):
                score_keyword(resumes, jobs)
        result = score_keyword([{'resume_id': 'cpp', 'text': 'C++'},
                                {'resume_id': 'c', 'text': 'C'}], jobs)
        self.assertEqual([row['similarity_score'] for row in result], [1.0, 0.0])

    def test_exact_match_ranks_above_unrelated_and_output_is_reproducible(self):
        resumes = [{'resume_id': 'r2', 'text': 'nursing patient care'},
                   {'resume_id': 'r1', 'text': 'SQL Python Power BI'}]
        jobs = [{'job_id': 'j1', 'text': 'SQL Python Power BI'}]
        result = score_keyword(resumes, jobs)
        self.assertEqual([r['resume_id'] for r in result], ['r1', 'r2'])
        self.assertEqual([r['similarity_score'] for r in result], [1.0, 0.0])
        self.assertEqual([r['rank_position'] for r in result], [1, 2])
        self.assertEqual(set(result[0]), {'evaluation_id', 'resume_id', 'job_id',
                         'model_name', 'similarity_score', 'rank_position', 'test_condition_id'})
        self.assertEqual(result, score_keyword(list(reversed(resumes)), jobs))


if __name__ == '__main__':
    unittest.main()
