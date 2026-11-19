import unittest
from ats_semantic import score_semantic, load_model, bound_text


class SemanticTests(unittest.TestCase):
    def test_real_model_ranks_paraphrase_over_control_and_bounds_long_text(self):
        model = load_model()
        jobs = [{'job_id':'j1','text':'Analyze business data and create reports for managers.'}]
        resumes = [{'resume_id':'related','text':'Examined company performance and presented findings to leadership.'},
                   {'resume_id':'control','text':'Prepared meals and washed dishes in a restaurant kitchen.'}]
        result = score_semantic(resumes,jobs,model=model)
        self.assertEqual(result[0]['resume_id'],'related')
        self.assertEqual([r['rank_position'] for r in result],[1,2])
        self.assertTrue(all(0 <= r['similarity_score'] <= 1 for r in result))
        text, changed = bound_text('SQL C++ Power BI experience ' * 1000, model)
        self.assertTrue(changed)
        self.assertLessEqual(len(model.tokenizer.encode(text)), model.max_seq_length)
        with self.assertRaises(ValueError):
            score_semantic([{'resume_id':'r','text':None}],jobs,model=model)
