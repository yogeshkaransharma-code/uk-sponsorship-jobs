import csv
import io
import unittest
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('refresh', ROOT/'scripts'/'refresh.py')
r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
class ImportQualityTests(unittest.TestCase):
    def test_raw_register_csv_excludes_preview(self):
        html = """<a href='https://assets.publishing.service.gov.uk/media/x/sponsors.csv'>CSV</a>
        <a href='https://assets.publishing.service.gov.uk/media/x/sponsors.csv/preview'>View online</a>"""
        self.assertEqual(r.register_csv_urls(html), ['https://assets.publishing.service.gov.uk/media/x/sponsors.csv'])

    def test_raw_register_csv_excludes_other_hosts(self):
        html = "<a href='https://malicious.example/evil.csv'>CSV</a>"
        self.assertEqual(r.register_csv_urls(html), [])

    def test_sponsor_match_does_not_verify_a_brand(self):
        reg={'example': [{'name':'Example','town':'London','route':'Skilled Worker','rating':'Worker (A rating)'}]}
        d=r.sponsor_match([{'company':'Example','legal_name':''}],reg,'https://gov.uk/test.csv')
        self.assertEqual(d['Example']['status'],'name_only')
    def test_legal_identity_can_confirm_one_route(self):
        reg={'example ltd':[{'name':'Example LTD','town':'London','route':'Skilled Worker','rating':'Worker (A rating)'}]}
        d=r.sponsor_match([{'company':'Example','legal_name':'Example LTD'}],reg,'https://gov.uk/test.csv')
        self.assertEqual(d['Example LTD']['status'],'verified')
    def test_wrong_route_not_verified(self):
        reg={'example ltd':[{'name':'Example LTD','town':'London','route':'Temporary Worker - Creative Worker','rating':'Worker (A rating)'}]}
        d=r.sponsor_match([{'company':'Example','legal_name':'Example LTD'}],reg,'https://gov.uk/test.csv')
        self.assertNotEqual(d['Example LTD']['status'],'verified')
    def test_similar_name_not_exact(self):
        reg={'example ltd':[{'name':'Example LTD','town':'London','route':'Skilled Worker','rating':'Worker (A rating)'}]}
        d=r.sponsor_match([{'company':'Example','legal_name':''}],reg,'https://gov.uk/test.csv')
        self.assertNotIn('Example',d)
    def test_ambiguous_town_not_verified(self):
        reg={'example ltd':[{'name':'Example LTD','town':'London','route':'Skilled Worker','rating':'Worker (A rating)'}, {'name':'Example LTD','town':'Leeds','route':'Skilled Worker','rating':'Worker (A rating)'}]}
        d=r.sponsor_match([{'company':'Example','legal_name':'Example LTD'}],reg,'https://gov.uk/test.csv')
        self.assertNotIn('Example LTD',d)
    def test_apply_link_host_is_allowed(self):
        job={'title':'Business Development Manager','location':'London', 'jobUrl':'https://evil.example/123', 'descriptionPlain':'Visa sponsorship: Yes'}
        self.assertIsNone(r.listing({'company':'Example','board':'example'},job))
    def test_empty_history_does_not_mean_zero(self):
        self.assertIsNone(r.history_for('No record anywhere'))
if __name__=='__main__': unittest.main()
