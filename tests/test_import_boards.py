import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("import_boards", ROOT/"scripts"/"import_boards.py")
board=importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)

class BoardDirectoryTests(unittest.TestCase):
    def test_only_safe_verified_board_tokens(self):
        rows=[
            {"platform":"greenhouse","token":"example","open_roles":10,"company":"Example"},
            {"platform":"ashby","token":"../admin","open_roles":12,"company":"Bad"},
            {"platform":"workday","token":"x","open_roles":100},
            {"platform":"lever","token":"london-test","open_roles":20,"company":"Other"},
        ]
        self.assertEqual(len(board.selected_boards(rows,set())),2)
    def test_clear_uk_location(self):
        self.assertTrue(board.loc_ok("Manchester, England"))
        self.assertTrue(board.loc_ok("London, UK"))
        self.assertFalse(board.loc_ok("New York, USA"))
        self.assertFalse(board.loc_ok("Cambridge, MA"))
        self.assertFalse(board.loc_ok("Berlin, Germany"))
    def test_greenhouse_job_only_with_original_link(self):
        source={"platform":"greenhouse","token":"example","company":"Test Employer"}
        item={"title":"Account Manager","location":{"name":"London, United Kingdom"},
              "absolute_url":"https://job-boards.greenhouse.io/example/jobs/123","content":"Visa sponsorship is available for this role."}
        result=board.adapt(source,item,"2026-10-22")
        self.assertEqual(result["sponsorship"],"stated")
        self.assertEqual(result["job_function"],"Sales & Relationships")
    def test_unknown_role_still_visible(self):
        source={"platform":"ashby","token":"example","company":"Employer"}
        item={"title":"Warehouse Associate","location":"Leeds, UK",
              "jobUrl":"https://jobs.ashbyhq.com/example/12345"}
        job=board.adapt(source,item,"2026-10-22")
        self.assertIsNotNone(job)
        self.assertEqual(job["sponsorship"],"unknown")
    def test_external_non_uk_country(self):
        source={"platform":"lever","token":"example","company":"Example"}
        item={"text":"HR Advisor","categories":{"location":"Boston, USA"},
              "country":"US","applyUrl":"https://jobs.lever.co/example/abc"}
        self.assertIsNone(board.adapt(source,item,"2026-10-22"))

if __name__=="__main__":unittest.main()
