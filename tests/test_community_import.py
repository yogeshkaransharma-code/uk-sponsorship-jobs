import importlib.util
import unittest
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('community',repo/'scripts'/'import_community.py')
community=importlib.util.module_from_spec(spec)
spec.loader.exec_module(community)

class CommunityImportTests(unittest.TestCase):
    def sample(self,location="Manchester, England, United Kingdom"):
        return {
          "company":"Sample Corp", "title":"Customer Support Specialist",
          "locations":[location],
          "applyUrl":"https://example.org/careers/123",
          "postedAt":"2026-10-21T10:00:00Z",
        }
    def test_uk_job_import(self):
        x=community.make_record(self.sample(),"2026-10-22")
        self.assertEqual(x['sponsorship'],'unknown')
        self.assertEqual(x['location'],'Manchester, England, United Kingdom')
    def test_non_uk_job_filtered(self):
        self.assertIsNone(community.make_record(self.sample("New York, USA"),"2026-10-22"))
    def test_non_uk_location_with_ambiguous_city(self):
        self.assertIsNone(community.make_record(self.sample("Cambridge, MA"),"2026-10-22"))
    def test_uk_city_allowed(self):
        self.assertIsNotNone(community.make_record(self.sample("Glasgow, Scotland"),"2026-10-22"))
    def test_unsafe_link_rejected(self):
        data=self.sample()
        data['applyUrl']='javascript:alert(1)'
        self.assertIsNone(community.make_record(data,"2026-10-22"))

if __name__=='__main__':
    unittest.main()
