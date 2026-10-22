import importlib.util
import json
import unittest
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('refresh', repo/'scripts'/'refresh.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)

class RefreshTests(unittest.TestCase):
    def test_json_structure(self):
        for name in ('jobs.json','sponsors.json','sources.json'):
            json.loads((repo/'data'/name).read_text(encoding='utf-8'))

    def test_offline_validator(self):
        self.assertIsInstance(refresh.read('jobs.json')['jobs'], list)

    def test_greenhouse_location_as_object(self):
        src={'company':'Example','legal_name':'','board':'example'}
        job={'title':'Account Executive', 'location':{'name':'London, England'},
             'absolute_url':'https://job-boards.greenhouse.io/example/jobs/12345',
             'content':'Visa sponsorship is available for this role.'}
        parsed=refresh.listing(src,job)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['location'],'London, England')
        self.assertEqual(parsed['sponsorship'],'stated')

    def test_non_uk_excluded(self):
        src={'company':'Example','legal_name':'','board':'example'}
        job={'title':'Account Executive', 'location':'New York, USA',
             'jobUrl':'https://jobs.ashbyhq.com/example/xyz','descriptionPlain':'visa sponsorship: Yes'}
        self.assertIsNone(refresh.listing(src,job))

    def test_no_sponsorship_excluded(self):
        status,_=refresh.classify('We do not offer visa sponsorship for this role.')
        self.assertEqual(status,'unavailable')

    def test_case_by_case(self):
        status,_=refresh.classify('Visa sponsorship will be considered on a case-by-case basis.')
        self.assertEqual(status,'conditional')

    def test_marshmallow_explicit_sponsorship(self):
        for text in (
            'We are able to offer visa sponsorship for this position.',
            'We are in a position to offer sponsorship and/or a visa for this position.',
        ):
            status, evidence = refresh.classify(text)
            self.assertEqual(status, 'stated', text)
            self.assertTrue(evidence)

    def test_no_sponsorship_with_negative_qualifier(self):
        for text in (
            'We are not able to offer visa sponsorship for this position.',
            "We aren't able to offer sponsorship for this role.",
        ):
            status, _ = refresh.classify(text)
            self.assertEqual(status, 'unavailable', text)

    def test_insurance_vacancy_title_parsed(self):
        src = {'company':'Flock','legal_name':'','board':'flock',
               'sector':'Insurance / insurtech'}
        job = {'title':'Claims Handler','location':'London',
               'jobUrl':'https://jobs.ashbyhq.com/flock/example',
               'descriptionPlain':'We are able to offer visa sponsorship for this position.'}
        parsed = refresh.listing(src, job)
        self.assertIsNotNone(parsed)
        self.assertIn('Insurance', parsed['category'])
        self.assertEqual(parsed['sponsorship'], 'stated')

    def test_sponsorship_not_mentioned_still_imported(self):
        src={'company':'Example','legal_name':'','board':'example','industry':'Insurance'}
        job={'title':'Internal Auditor','location':'London',
             'jobUrl':'https://jobs.ashbyhq.com/example/openjob',
             'descriptionPlain':'Work with our insurance audit team.'}
        parsed=refresh.listing(src,job)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['sponsorship'],'unknown')
        self.assertEqual(parsed['industry'],'Insurance')

    def test_explicit_no_sponsorship_is_still_searchable(self):
        src={'company':'Example','legal_name':'','board':'example'}
        job={'title':'Senior Consultant','location':'Manchester',
             'jobUrl':'https://jobs.ashbyhq.com/example/role',
             'descriptionPlain':'We do not offer visa sponsorship for this role.'}
        parsed=refresh.listing(src,job)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['sponsorship'],'unavailable')

    def test_non_uk_with_similar_city_is_rejected(self):
        src={'company':'Example','legal_name':'','board':'example'}
        job={'title':'Engineer','location':'Cambridge, MA',
             'jobUrl':'https://jobs.ashbyhq.com/example/usa'}
        self.assertIsNone(refresh.listing(src,job))

    def test_unknown_job_titles_are_not_silently_excluded(self):
        src={'company':'Example','legal_name':'','board':'example'}
        job={'title':'Research Librarian','location':'Glasgow',
             'jobUrl':'https://jobs.ashbyhq.com/example/library'}
        parsed=refresh.listing(src,job)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['job_function'],'Other')

    def test_no_false_history(self):
        self.assertIsNone(refresh.history_for('An Employer That Has No Verified History'))

if __name__=='__main__':
    unittest.main()
