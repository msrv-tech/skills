import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ui_suite import collect_ui_scenarios, run_ui_suite

class UiSuiteTests(unittest.TestCase):
    def test_collects_directory_and_preserves_separate_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('one.ui.json', 'two.ui.json'):
                (root / name).write_text('{"steps":[{"action":"assertConnected"}]}', encoding='utf-8')
            seen = {}
            def fake_worker(_config, suite_path, _artifacts):
                suite = json.loads(Path(suite_path).read_text(encoding='utf-8'))
                seen['suite'] = suite
                return {'ok': False, 'status': 'failed', 'managerResult': {'ok': False, 'scenarios': [
                    {'ok': True, 'name': 'one', 'source': suite['scenarios'][0]['source'], 'steps': []},
                    {'ok': False, 'name': 'two', 'source': suite['scenarios'][1]['source'], 'steps': [{'status': 'failed', 'error': 'boom'}]},
                ]}}
            with patch('ui_suite.run_ui_worker', side_effect=fake_worker):
                result = run_ui_suite({}, [root], root / 'artifacts')
            self.assertEqual(len(seen['suite']['scenarios']), 2)
            self.assertFalse(result['ok'])
            self.assertEqual(len(result['scenarios']), 2)
            self.assertTrue(result['suite']['warm'])

if __name__ == '__main__':
    unittest.main()
