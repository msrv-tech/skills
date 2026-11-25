import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('deploy_test_bridge', Path(__file__).resolve().parents[1] / 'scripts/deploy_test_bridge.py')
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


class DeploymentTests(unittest.TestCase):
    def record(self):
        return {'Ref': 'demo', 'Srvr': 'server.example.invalid', 'User': 'test-user',
                'Password': '', 'Bridge': {'BaseUrl': 'http://server.example.invalid/hs/codex-test'},
                'BridgeCompatibilityMode': 'Version8_5_1'}

    def run_with_mocks(self, records, arguments):
        calls = []
        with tempfile.NamedTemporaryFile() as platform:
            with patch.object(deploy, 'resolve_registry', return_value=Path('unused')), \
                 patch.object(deploy.bridge, 'load_registry', return_value=records), \
                 patch.object(deploy.bridge, 'sync_local_skills', side_effect=lambda *a, **k: calls.append('sync')), \
                 patch.object(deploy.bridge, 'install_database', side_effect=lambda *a: calls.append('install')), \
                 patch.object(deploy, 'enable_publication', side_effect=lambda *a: calls.append('publication')), \
                 patch.object(deploy.bridge, 'verify_bridge', side_effect=lambda *a: calls.append('verify')), \
                 patch.object(deploy.bridge, 'assert_no_bootstrap_users', side_effect=lambda *a: calls.append('audit')), \
                 patch('sys.argv', ['deploy', '--platform', platform.name, *arguments]):
                try:
                    result = deploy.main()
                except deploy.bridge.UpdateError:
                    result = 'invalid'
        return result, calls

    def test_first_install_does_not_require_existing_bridge(self):
        result, calls = self.run_with_mocks([self.record()], ['--database', 'demo'])
        self.assertEqual(result, 0)
        self.assertEqual(calls, ['sync', 'install', 'publication', 'verify', 'audit'])

    def test_invalid_second_target_prevents_all_changes(self):
        invalid = {'Ref': 'missing'}
        result, calls = self.run_with_mocks([self.record(), invalid], ['--database', 'demo', '--database', 'missing'])
        self.assertEqual(result, 'invalid')
        self.assertEqual(calls, [])

    def test_verify_only_has_no_mutations(self):
        result, calls = self.run_with_mocks([self.record()], ['--database', 'demo', '--verify-only'])
        self.assertEqual(result, 0)
        self.assertEqual(calls, ['verify', 'audit'])


if __name__ == '__main__':
    unittest.main()
