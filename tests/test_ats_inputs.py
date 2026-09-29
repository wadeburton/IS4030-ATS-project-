import unittest
from ats_inputs import prepare_records


class MissingInputTests(unittest.TestCase):
    def test_missing_markers_and_job_descriptions_follow_the_selected_policy(self):
        for value in [None, float('nan'), '', '  ', 'NULL', 'None', 'N/A', 'NaN', '[]', '[null, "N/A"]', [None, 'N/A']]:
            with self.subTest(value=value):
                rows = [{'job_id': 'j1', 'description': value}]
                with self.assertRaisesRegex(ValueError, 'missing selected fields'):
                    prepare_records(rows, 'job_id', ['description'])
                prepared, audit = prepare_records(rows, 'job_id', ['description'], missing_policy='skip_missing')
                self.assertEqual(prepared, [])
                self.assertEqual(audit[0]['reason'], 'no_usable_text')
        prepared, _ = prepare_records([{'job_id': 'j2', 'description': 'Use C++ and Power BI'}], 'job_id', ['description'])
        self.assertEqual(prepared[0]['text'], 'description: Use C++ and Power BI')

    def test_invalid_settings_and_ids_fail_instead_of_silently_skipping(self):
        valid = [{'id': '1', 'skills': 'SQL'}]
        with self.assertRaisesRegex(ValueError, 'missing_policy'):
            prepare_records(valid, 'id', ['skills'], missing_policy='typo')
        with self.assertRaisesRegex(ValueError, 'text_fields'):
            prepare_records(valid, 'id', [])
        with self.assertRaisesRegex(ValueError, 'identifier'):
            prepare_records([{'id': None, 'skills': 'SQL'}], 'id', ['skills'], missing_policy='skip_missing')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            prepare_records(valid * 2, 'id', ['skills'], missing_policy='skip_missing')

    def test_skip_mode_keeps_available_qualifications_and_audits_empty_rows(self):
        rows = [
            {'resume_id': 'r1', 'skills': "['SQL', None, 'C++', 'N/A']", 'experience': '  '},
            {'resume_id': 'r2', 'skills': None, 'experience': 'N/A'},
            {'resume_id': 'r3', 'skills': 'Power BI', 'experience': 'Built reports'},
        ]
        prepared, audit = prepare_records(rows, 'resume_id', ['skills', 'experience'], missing_policy='skip_missing')
        self.assertEqual([r['resume_id'] for r in prepared], ['r1', 'r3'])
        self.assertEqual(prepared[0]['text'], 'skills: SQL, C++')
        self.assertEqual(prepared[0]['missing_fields'], ['experience'])
        self.assertEqual(prepared[0]['input_status'], 'provisional')
        self.assertEqual(audit[1]['action'], 'skipped')
        self.assertEqual(audit[1]['reason'], 'no_usable_text')
        self.assertEqual(audit[0]['action'], 'kept_partial')
        self.assertEqual(audit[2]['action'], 'kept')
        self.assertEqual(rows[0]['skills'], "['SQL', None, 'C++', 'N/A']")


if __name__ == '__main__':
    unittest.main()
