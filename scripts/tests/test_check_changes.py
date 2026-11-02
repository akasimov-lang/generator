import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('check_changes',Path(__file__).parents[1]/'check_changes.py')
checks=importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class ScopedChecks(unittest.TestCase):
    def test_report_change_only_checks_report_and_frontend(self):
        result=checks.plan(['backend/app/auto_pilot.py','frontend/src/AutoPilot.tsx'])
        self.assertEqual(result['backend_tests'],['backend/tests/test_auto_pilot.py'])
        self.assertTrue(result['frontend_build'])
        self.assertFalse(result['browser'])

    def test_related_recheck_contract_is_included(self):
        result=checks.plan(['backend/app/reglue_title_h1.py'])
        self.assertEqual(result['backend_tests'],['backend/tests/test_reglue_recheck.py','backend/tests/test_reglue_title_h1.py'])

    def test_docs_and_browser_fixtures_start_no_processes(self):
        result=checks.plan(['AGENTS.md','docs/TESTING.md','frontend/tests/auto_pilot_browser.py'])
        self.assertEqual(result['commands'],[])
        self.assertEqual(result['unresolved'],[])

    def test_unknown_module_requires_explicit_test(self):
        self.assertEqual(checks.plan(['backend/app/new_feature.py'])['unresolved'],['backend/app/new_feature.py'])
        result=checks.plan(['backend/app/new_feature.py'],['backend/tests/test_auto_pilot.py'])
        self.assertFalse(result['unresolved'])
        self.assertEqual(len(result['backend_tests']),1)

    def test_shared_model_change_is_not_under_tested(self):
        expected={p.relative_to(checks.ROOT).as_posix() for p in (checks.ROOT/'backend/tests').glob('test_*.py')}
        self.assertEqual(set(checks.plan(['backend/app/models.py'])['backend_tests']),expected)

    def test_unrelated_frontend_does_not_run_node_helpers(self):
        self.assertEqual(checks.plan(['frontend/src/AutoPilot.tsx'])['node_tests'],[])
        self.assertEqual(checks.plan(['frontend/src/alternateDiff.mjs'])['node_tests'],['frontend/tests/alternateDiff.test.mjs'])


if __name__=='__main__':unittest.main()
