import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('headcount', ROOT / 'scripts' / 'import_headcount.py')
headcount = importlib.util.module_from_spec(spec)
spec.loader.exec_module(headcount)


def sample(overrides=None):
    record = {
        'job_id': '4a32c163-f485-4cf3-858a-07eb11075803',
        'currentness': 'current',
        'employer_name': {'state': 'known', 'value': 'A British Employer'},
        'title': {'state': 'known', 'value': 'Relationship Manager'},
        'job_first_seen_at': '2026-10-22T16:20:00Z',
        'locations': [{'state': 'known', 'value': {
            'country': 'GB', 'city': 'Manchester', 'region': 'GB-MAN',
        }}],
        'postings': [{
            'posting_status': 'listed',
            'application_url': {'state': 'known', 'value': 'https://jobs.example.org/123'},
            'pay': {'state': 'known', 'value': {
                'currency': 'GBP', 'interval': 'year', 'min': 40000, 'max': 50000,
            }},
        }],
    }
    record.update(overrides or {})
    return record


class HeadcountImportTests(unittest.TestCase):
    def test_uk_current_job(self):
        job = headcount.record(sample())
        self.assertEqual(job['company'], 'A British Employer')
        self.assertEqual(job['sponsorship'], 'unknown')
        self.assertEqual(job['salary'], '£40,000–£50,000 per year')
        self.assertEqual(job['country'], 'GB')

    def test_non_uk_rejected(self):
        self.assertIsNone(headcount.record(sample({
            'locations': [{'state':'known','value': {'country':'US','city':'Boston'}}]})))

    def test_closed_rejected(self):
        self.assertIsNone(headcount.record(sample({'currentness': 'not_current'})))

    def test_bad_link_rejected(self):
        item = sample()
        item['postings'][0]['application_url']['value'] = 'javascript:alert(1)'
        self.assertIsNone(headcount.record(item))

    def test_deduplicated_by_id(self):
        self.assertEqual(len(headcount.normalize_export([sample(), sample()])), 1)


if __name__ == '__main__':
    unittest.main()
