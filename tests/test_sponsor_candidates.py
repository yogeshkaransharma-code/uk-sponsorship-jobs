import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("register_match",Path(__file__).resolve().parents[1]/"scripts"/"match_sponsor_names.py")
matcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(matcher)

class SponsorCandidatesTests(unittest.TestCase):
    def test_candidate_is_not_verified(self):
        register={"acme limited":[{"name":"ACME LIMITED","route":"Skilled Worker"}]}
        match=matcher.get_candidates({"ACME Ltd"},register)
        self.assertEqual(match["ACME Ltd"]["status"],"name_match")
        self.assertIn("not confirmed",match["ACME Ltd"]["note"])
    def test_unlicenced_route_excluded(self):
        register={"acme limited":[{"name":"ACME LIMITED","route":"Temporary Worker"}]}
        self.assertFalse(matcher.get_candidates({"ACME Ltd"},register))
    def test_ambiguous_names_excluded(self):
        register={
          "acme ltd":[{"name":"ACME LTD","route":"Skilled Worker"}],
          "acme plc":[{"name":"ACME PLC","route":"Skilled Worker"}],
        }
        self.assertFalse(matcher.get_candidates({"Acme"},register))
    def test_no_unsupported_generic_match(self):
        register={"services limited":[{"name":"SERVICES LIMITED","route":"Skilled Worker"}]}
        self.assertFalse(matcher.get_candidates({"Services"},register))

if __name__=="__main__":
    unittest.main()
