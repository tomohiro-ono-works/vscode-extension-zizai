"""Normal form selection, safe data loading and placeholder generation."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'apps/core/src'))
from zizai.form_definition import load_definition, parse_definition
from zizai.form_model import FormModel


class FormModelTests(unittest.TestCase):
    def setUp(self):
        self.definition = load_definition()
        self.model = FormModel(self.definition)

    def choose(self, connector='csv', action='export'):
        self.model.set_connector(connector)
        self.model.set_action(action)

    def test_placeholder_uses_ids_and_does_not_execute_business_code(self):
        self.choose()
        self.model.set_value('folder', 'C:/データ/保存先')
        self.assertEqual(self.model.generate(), '{csv.exportのコードを生成}')
        self.assertEqual(self.model.values['folder'], 'C:/データ/保存先')

    def test_required_input_and_unselected_action_prevent_generation(self):
        with self.assertRaises(ValueError):
            self.model.generate()
        self.choose()
        with self.assertRaises(ValueError):
            self.model.generate()
        self.model.set_value('folder', '   ')
        with self.assertRaises(ValueError):
            self.model.generate()

    def test_parent_change_keeps_valid_action_and_compatible_settings(self):
        self.choose()
        self.model.set_value('folder', 'C:/keep')
        self.model.set_connector('excel')
        self.assertEqual(self.model.action, 'export')
        self.assertEqual(self.model.values['folder'], 'C:/keep')

    def test_parent_change_clears_invalid_action_and_disables_generation(self):
        self.choose(action='import')
        self.model.set_connector('excel')
        self.assertIsNone(self.model.action)
        self.assertEqual(self.model.values, {})
        with self.assertRaises(ValueError):
            self.model.generate()

    def test_invalid_choice_and_integer_are_rejected_without_changing_values(self):
        self.choose(action='import')
        before = copy.deepcopy(self.model.values)
        with self.assertRaises(ValueError):
            self.model.set_value('encoding', 'not-a-choice')
        with self.assertRaises(ValueError):
            self.model.set_value('start_row', 0)
        self.assertEqual(self.model.values, before)

    def test_custom_yaml_changes_candidates_fields_and_message(self):
        config = parse_definition('''version: 1
output_template: "{connector}.{action} の準備"
connectors:
  local:
    label: ローカル
    actions:
      inspect:
        label: 確認
        fields:
          name: {label: 名前, type: text, required: true}
''')
        model = FormModel(config)
        model.set_connector('local')
        model.set_action('inspect')
        model.set_value('name', '\"; dangerous() #')
        self.assertEqual(model.generate(), '{local.inspect の準備}')

    def test_yaml_is_data_only_and_rejects_ambiguous_or_invalid_definitions(self):
        for text in ['!!python/object/apply:os.system [echo bad]',
                     'version: 1\nversion: 2',
                     'version: 1\nx: &x [1]\ny: *x',
                     'version: 1\nconnectors: {}',
                     'x' * (1024 * 1024 + 1)]:
            with self.subTest(text=text[:50]), self.assertRaises(ValueError):
                parse_definition(text)
        invalid = copy.deepcopy(self.definition)
        invalid['output_template'] = '{connector.__class__}'
        import yaml
        with self.assertRaises(ValueError):
            parse_definition(yaml.safe_dump(invalid))


if __name__ == '__main__':
    unittest.main()
