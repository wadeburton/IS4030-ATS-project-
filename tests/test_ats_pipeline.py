import unittest

from ats_pipeline import build_dashboard_view, run_ats


class AtsPipelineTests(unittest.TestCase):
    def setUp(self):
        self.resumes = [
            {'resume_id': 'r1', 'text': 'SQL Python Power BI'},
            {'resume_id': 'r2', 'text': 'nursing and patient care'},
            {'resume_id': 'r3', 'text': None},
        ]
        self.jobs = [
            {'job_id': 'j1', 'text': 'SQL Python Power BI analyst'},
            {'job_id': 'j2', 'text': 'business intelligence reporting'},
        ]
        self.study_resumes = [
            {'resume_id': f't{i}', 'text': 'analyst SQL reporting', 'domain_group': 'tech_data_proxy'}
            for i in range(210)
        ] + [
            {'resume_id': f'c{i}', 'text': 'patient care or sales', 'domain_group': 'control'}
            for i in range(90)
        ]

    def test_skip_missing_rows_are_reported_and_scoring_can_continue(self):
        result = run_ats(self.resumes, self.jobs, job_id='j1', model_name='tfidf',
                         missing_policy='skip_missing', run_id='run-a')

        self.assertEqual(result['run']['status'], 'succeeded')
        self.assertEqual(result['run']['skipped_resume_count'], 1)
        self.assertEqual(result['quality']['status'], 'warning')
        self.assertEqual({row['job_id'] for row in result['scores']}, {'j1'})
        self.assertTrue(all(row['run_id'] == 'run-a' for row in result['scores']))

    def test_critical_missing_input_blocks_scoring(self):
        result = run_ats(self.resumes, self.jobs, job_id='j1', model_name='tfidf',
                         missing_policy='error', run_id='run-b')

        self.assertEqual(result['run']['status'], 'blocked')
        self.assertEqual(result['quality']['status'], 'failed')
        self.assertEqual(result['scores'], [])

    def test_selected_job_and_model_are_traceable_for_dashboard(self):
        result = run_ats(self.resumes[:2], self.jobs, job_id='j2', model_name='tfidf',
                         run_id='run-c')
        view = build_dashboard_view([result['run']], result['quality']['checks'],
                                    result['scores'], selected_run_id='run-c')

        self.assertEqual(view['run']['job_id'], 'j2')
        self.assertEqual(view['run']['model_name'], 'tfidf')
        self.assertEqual(view['score_count'], 2)
        self.assertEqual(view['quality_status'], 'passed')
        self.assertTrue(all(row['job_id'] == 'j2' for row in view['scores']))

    def test_dashboard_selects_only_requested_run_and_its_quality_checks(self):
        first = run_ats(self.resumes[:2], self.jobs, job_id='j1', model_name='tfidf', run_id='run-1')
        second = run_ats(self.resumes[:2], self.jobs, job_id='j2', model_name='tfidf', run_id='run-2')
        view = build_dashboard_view(
            [first['run'], second['run']],
            first['quality']['checks'] + second['quality']['checks'],
            first['scores'] + second['scores'],
            selected_run_id='run-2',
        )

        self.assertEqual(view['run']['run_id'], 'run-2')
        self.assertEqual(view['score_count'], 2)
        self.assertTrue(all(check['run_id'] == 'run-2' for check in view['quality_checks']))

    def test_generator_inputs_keep_original_count_for_quality_audit(self):
        result = run_ats((row for row in self.resumes), self.jobs, job_id='j1',
                         model_name='tfidf', run_id='run-generator')

        self.assertEqual(result['quality']['resume_input_count'], 3)

    def test_character_limit_counts_qualification_text_without_field_label(self):
        text = 'SQL ' * 249 + 'ETL.'
        resumes = [{'resume_id': 'r1', 'text': text}]
        self.assertEqual(len(text), 1000)
        self.assertEqual(run_ats(resumes, self.jobs, job_id='j1')['run']['status'], 'succeeded')
        resumes[0]['text'] += ' SQL'
        self.assertEqual(run_ats(resumes, self.jobs, job_id='j1')['run']['status'], 'blocked')

    def test_study_mode_checks_the_planned_70_30_domain_mix(self):
        result = run_ats(self.study_resumes, self.jobs, job_id='j1', model_name='tfidf',
                         run_id='run-study', study_mode=True)

        mix_check = next(check for check in result['quality']['checks']
                         if check['check_name'] == 'study_domain_ratio')
        self.assertEqual(mix_check['status'], 'passed')
        self.assertEqual(result['run']['status'], 'succeeded')

    def test_study_mode_allows_up_to_20_job_postings(self):
        jobs = [{'job_id': f'j{i}', 'text': f'analyst role number {i}'} for i in range(20)]
        result = run_ats(self.study_resumes, jobs, job_id='j0', model_name='tfidf',
                         run_id='run-study-20-jobs', study_mode=True)

        job_count_check = next(check for check in result['quality']['checks']
                               if check['check_name'] == 'study_job_count')
        self.assertEqual(job_count_check['status'], 'passed')
        self.assertEqual(result['run']['status'], 'succeeded')

    def test_study_mode_still_blocks_more_than_20_job_postings(self):
        jobs = [{'job_id': f'j{i}', 'text': f'analyst role number {i}'} for i in range(21)]
        result = run_ats(self.study_resumes, jobs, job_id='j0', model_name='tfidf',
                         run_id='run-study-21-jobs', study_mode=True)

        job_count_check = next(check for check in result['quality']['checks']
                               if check['check_name'] == 'study_job_count')
        self.assertEqual(job_count_check['status'], 'failed')
        self.assertEqual(result['run']['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
