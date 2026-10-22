import importlib.util
import unittest
from pathlib import Path

p=Path(__file__).resolve().parents[1]/"scripts"/"enrich_descriptions.py"
spec=importlib.util.spec_from_file_location("enrich_descriptions",p)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class EnrichmentTests(unittest.TestCase):
    def test_url_identity(self):
        self.assertEqual(module.identify("https://job-boards.greenhouse.io/acme/jobs/12345"),("greenhouse","acme","12345"))
        self.assertEqual(module.identify("https://jobs.ashbyhq.com/acme/DEADBEEF/application"),("ashby","acme","deadbeef"))
        self.assertEqual(module.identify("https://jobs.lever.co/acme/ABC123"),("lever","acme","abc123"))
        self.assertIsNone(module.identify("https://example.invalid/private"))
        self.assertIsNone(module.identify("http://job-boards.greenhouse.io/acme/jobs/12345"))
    def test_canonical_application_urls(self):
        a=module.canonical("https://jobs.ashbyhq.com/acme/123/application")
        b=module.canonical("https://jobs.ashbyhq.com/acme/123")
        self.assertEqual(a,b)
    def test_html_advert_preserves_bullets(self):
        x=module.plain("<h2>About the job</h2><ul><li>Manage clients</li><li>Support sales</li></ul>")
        self.assertIn("About the job",x)
        self.assertIn("• Manage clients",x)
        self.assertIn("• Support sales",x)
    def test_public_board_description_matches_job_id(self):
        orig=module.source_jobs
        try:
            module.source_jobs=lambda provider,slug:[{
                "id":12345,"title":"Relationship Manager",
                "content":"<h3>About the role</h3><p>Manage long-term client relationships and support insurance renewals.</p><p>Coordinate applications with underwriting specialists.</p>",
                "absolute_url":"https://job-boards.greenhouse.io/acme/jobs/12345",
            }]
            p,t,n,rows,error=module.source_board(("greenhouse","acme",[
                ("job-boards.greenhouse.io/acme/jobs/12345","12345")]))
            self.assertFalse(error)
            self.assertIn("job-boards.greenhouse.io/acme/jobs/12345",rows)
            self.assertIn("Coordinate applications",rows["job-boards.greenhouse.io/acme/jobs/12345"]["description_excerpt"])
        finally:
            module.source_jobs=orig

if __name__=="__main__":
    unittest.main()
