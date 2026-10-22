import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("single_details",ROOT/"scripts"/"enrich_other_ats.py")
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class DetailJobsTests(unittest.TestCase):
    def test_smart_url(self):
        x=p.parse_target("https://jobs.smartrecruiters.com/ExampleLtd/744000010540845-account-manager?oga=true")
        self.assertEqual(x[:3],("smart","ExampleLtd","744000010540845"))
    def test_workday_url(self):
        x=p.parse_target("https://sanofi.wd3.myworkdayjobs.com/SanofiCareers/job/Reading/Student-Project-Assistant_R2871368")
        self.assertEqual(x[:4],("workday","sanofi","SanofiCareers","sanofi.wd3.myworkdayjobs.com"))
    def test_malicious_non_ats_link_rejected(self):
        self.assertIsNone(p.parse_target("https://evil.example/hcmUI/job/42"))
    def test_workday_locale(self):
        x=p.parse_target("https://example.wd3.myworkdayjobs.com/en-US/External/job/London/Analyst_R1234")
        self.assertEqual(x[2],"External")
    def test_smart_description_fields(self):
        original=p.json_get
        try:
            p.json_get=lambda u,h:{"active":True,"jobAd":{"sections":{
                "jobDescription":{"text":"<p>Support long-term client relationships, maintain the sales pipeline and handle customer follow-ups.</p>"},
                "qualifications":{"text":"<p>At least three years of relationship management experience are desirable.</p>"}
            }}}
            kind,key,status,data=p.fetch_one(("smart","example","744000001","jobs.smartrecruiters.com","jobs.smartrecruiters.com/example/744000001"))
            self.assertEqual(status,"ok")
            self.assertIn("three years",data["description_excerpt"])
        finally:p.json_get=original

if __name__=="__main__":
    unittest.main()
