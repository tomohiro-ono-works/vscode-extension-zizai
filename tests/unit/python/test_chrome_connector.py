"""Exercise the Chrome form and launch policy without opening user Chrome."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class ChromeConnectorTests(unittest.TestCase):
    def setUp(self):
        shared = source_test_support.REPO / 'connectors'
        path = patch.object(sys, 'path', [str(shared / 'chrome'), *sys.path])
        path.start()
        self.addCleanup(path.stop)
        self.model = FormModel(load_definition(shared))
        self.model.set_connector('chrome')
        self.model.set_action('open_in_chrome')

    def test_form_dispatches_the_configured_url_only_when_executed(self):
        import chrome_connector
        with tempfile.TemporaryDirectory(prefix='zizai-chrome-') as root:
            policy = Path(root) / 'security_policies.yml'
            executable = Path(root) / 'chrome.exe'
            with patch.object(chrome_connector, 'POLICY_PATH', policy), \
                 patch.object(chrome_connector, '_find_chrome', return_value=executable), \
                 patch.object(chrome_connector.subprocess, 'Popen') as launch:
                with self.assertRaises(ValueError):
                    self.model.generate()
                self.model.set_value('url', 'https://test.example/docs/?id=1')
                code = self.model.generate()
                self.assertIn('result = chrome_connector.open_in_chrome(url=url)', code)
                launch.assert_not_called()
                self.assertFalse(policy.exists())
                policy.write_text('web:\n  allowlist:\n    - domain: test.example\n'
                                  '      path_prefixes: [/docs/]\n', encoding='utf-8')
                namespace = {}
                exec(compile(code, '<generated-open>', 'exec'), namespace)
                launch.assert_called_once()
                self.assertEqual(launch.call_args.args[0], [str(executable), 'https://test.example/docs/?id=1'])
                self.assertEqual(namespace['result']['status'].iat[0], 'launch_requested')

    def test_policy_blocks_missing_configuration_and_excluded_urls(self):
        import chrome_connector
        with tempfile.TemporaryDirectory(prefix='zizai-chrome-policy-') as root:
            policy = Path(root) / 'security_policies.yml'
            with patch.object(chrome_connector, 'POLICY_PATH', policy), \
                 patch.object(chrome_connector, '_find_chrome', return_value='chrome.exe'), \
                 patch.object(chrome_connector.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(ValueError, '許可リスト'):
                    chrome_connector.open_in_chrome('https://one.test.example/docs/guide')
                policy.write_text('web:\n  allowlist:\n    - domain: "*.test.example"\n'
                                  '      path_prefixes: [/docs/]\n', encoding='utf-8')
                for url in ('file:///C:/sample.txt', 'https://test.example/docs/guide',
                            'https://one.two.test.example/docs/guide', 'https://one.test.example.bad/docs/',
                            'https://one.test.example/private/', 'https://one.test.example/docs/%2e%2e/private',
                            'https://secret@one.test.example/docs/', 'https://127.0.0.1/docs/'):
                    with self.subTest(url=url), self.assertRaises(ValueError):
                        chrome_connector.open_in_chrome(url)
                launch.assert_not_called()
                chrome_connector.open_in_chrome('https://one.test.example/docs/guide')
                launch.assert_called_once()
