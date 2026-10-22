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
        self.assertEqual(status,'exclude')

    def test_case_by_case(self):
        status,_=refresh.classify('Visa sponsorship will be considered on a case-by-case basis.')
        self.assertEqual(status,'conditional')

    def test_no_false_history(self):
        self.assertIsNone(refresh.history_for('An Employer That Has No Verified History'))

if __name__=='__main__':
    unittest.main()
