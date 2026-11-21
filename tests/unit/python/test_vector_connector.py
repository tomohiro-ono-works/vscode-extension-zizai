"""Exercise generated Vector calls with a local model substitute and real storage."""
import sys
import tempfile
import unittest
from math import sqrt
from pathlib import Path
from unittest.mock import patch

import source_test_support
from zizai.form_definition import load_definition
from zizai.form_model import FormModel


class VectorConnectorTests(unittest.TestCase):
    def test_generated_registration_search_and_comparison(self):
        import numpy as np
        import pandas as pd

        shared = source_test_support.REPO / 'connectors'
        form = FormModel(load_definition(shared))
        form.set_connector('vector')
        with tempfile.TemporaryDirectory() as directory, patch.object(sys, 'path', [str(shared / 'vector'), *sys.path]):
            folder = Path(directory) / '日本語'
            import vector_connector

            def embed(model_name, texts, *, query):
                self.assertEqual(model_name, vector_connector.DEFAULT_MODEL_NAME)
                self.assertEqual(query, texts == ['query'])
                vectors = {'query': [1, 1], '近い': [0, 0.5], '対角': [0, 0], '一直線': [2, 2],
                           '強い': [4, 3], '更新': [1, 1]}
                return np.array([vectors[text] for text in texts])

            source = pd.DataFrame({
                'id': ['a', 'b', 'c', 'd'], 'text': ['近い', '対角', '一直線', '強い'],
                'group': ['alpha', 'beta', 'beta', 'alpha'],
            })
            namespace = {'source': source}
            form.set_action('embedding_vector_db')
            for name, value in dict(db_folder=str(folder), input_variable='source',
                                    enable_correction=True, density_k='2', penalty_weight='0.25').items():
                form.set_value(name, value)
            registration = form.generate()
            self.assertFalse(folder.exists())
            self.assertIn('import vector_connector', registration)
            self.assertIn('input_data = source', registration)
            self.assertNotIn('metric', registration)
            with patch.object(vector_connector, '_encode', side_effect=embed):
                exec(compile(registration, '<registration>', 'exec'), namespace)
                self.assertEqual(namespace['result']['registered_records'].iat[0], 4)
                self.assertNotIn('metric', namespace['result'])
                form.set_action('search_vector_db')
                form.set_value('query_text', 'query')
                form.set_value('search_mode', 'マンハッタン距離')
                self.assertEqual(form.values['output_variable'], 'df')
                exec(compile(form.generate(), '<search>', 'exec'), namespace)
                self.assertEqual(namespace['df']['id'].iat[0], 'a')
                self.assertAlmostEqual(namespace['df']['score'].iat[0], 1.5)
                self.assertEqual(namespace['df']['vector'].iat[0], '[0.0,0.5]')
                default_result = vector_connector.search_vector_db(folder, 'default', 'query')
                self.assertEqual(default_result['id'].iat[0], 'c')
                form.set_value('search_mode', 'コサイン類似度（補正前後を比較）')
                exec(compile(form.generate(), '<comparison>', 'exec'), namespace)
                self.assertEqual(namespace['df']['cosine_id'].iat[0], 'c')
                self.assertEqual(set(namespace['df']['corrected_id']), set(source['id']))
                self.assertEqual(namespace['df']['rank'].tolist(), [1, 2, 3, 4])
                self.assertTrue({'cosine_vector', 'corrected_vector'} <= set(namespace['df'].columns))
                # The reference compares centered vectors using the inverse covariance directly.
                originals = embed(vector_connector.DEFAULT_MODEL_NAME, source['text'].tolist(), query=False)
                centered = originals - originals.mean(axis=0)
                inverse_covariance = np.linalg.inv(np.cov(originals.T) + 0.001 * np.eye(2))

                def similarity(left, right):
                    return left @ inverse_covariance @ right / sqrt(
                        (left @ inverse_covariance @ left) * (right @ inverse_covariance @ right))

                scores = {}
                for position, (record_id, vector) in enumerate(zip(source['id'], centered)):
                    neighbors = sorted(similarity(vector, other) for index, other in enumerate(centered) if index != position)
                    scores[record_id] = similarity(vector, np.array([1, 1]) - originals.mean(axis=0)) - 0.25 * np.mean(neighbors[-2:])
                comparison = namespace['df']
                np.testing.assert_allclose(comparison['corrected_score'], comparison['corrected_id'].map(scores))
                self.assertEqual(comparison['corrected_id'].tolist(), sorted(scores, key=scores.get, reverse=True))

                modified = pd.DataFrame({'id': ['a'], 'text': ['更新']})
                with patch.object(vector_connector, '_fit_correction', side_effect=ValueError('failed correction')):
                    with self.assertRaisesRegex(ValueError, 'failed correction'):
                        vector_connector.embedding_vector_db(folder, 'default', modified)
                unchanged = vector_connector.search_vector_db(folder, 'default', 'query', search_mode='corrected')
                self.assertEqual(unchanged.loc[unchanged['id'] == 'a', 'text'].iat[0], '近い')
                vector_connector.embedding_vector_db(folder, 'default', modified)
                result = vector_connector.search_vector_db(folder, 'default', 'query', search_mode='corrected')
                self.assertEqual(result.loc[result['id'] == 'a', 'text'].iat[0], '更新')
                self.assertEqual(len(result), 4)
                self.assertEqual(source['text'].iat[0], '近い')

    def test_saved_standard_metrics_control_ranking(self):
        import numpy as np
        import pandas as pd

        ids = ['aligned', 'near', 'large', 'spread']
        source = pd.DataFrame({'id': ids, 'text': ids})
        originals = np.array([[4, 4], [1, 0.5], [8, 6], [1.28, 1.32]])
        shared = source_test_support.REPO / 'connectors'
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, 'path', [str(shared / 'vector'), *sys.path]):
            import vector_connector

            def embed(_name, _texts, *, query):
                return np.array([[1, 1]]) if query else originals

            with patch.object(vector_connector, '_encode', side_effect=embed):
                for metric, expected, score in (('cosine', 'aligned', 1.0), ('inner_product', 'large', 14),
                                                ('l2', 'spread', sqrt(0.28**2 + 0.32**2)), ('l1', 'near', 0.5)):
                    with self.subTest(metric=metric):
                        vector_connector.embedding_vector_db(folder, metric, source, metric=metric)
                        result = vector_connector.search_vector_db(folder, metric, 'query', top_k=1)
                        self.assertEqual(result['id'].iat[0], expected)
                        self.assertAlmostEqual(result['score'].iat[0], score)
                with self.assertRaises(ValueError):
                    vector_connector.embedding_vector_db(folder, 'l1', source, metric='cosine')
                with self.assertRaises(ValueError):
                    vector_connector.search_vector_db(folder, 'l1', 'query', search_mode='corrected')
                legacy_path = Path(folder) / 'l1.vector.duckdb'
                before = legacy_path.read_bytes()
                for metric, expected in (('cosine', 'aligned'), ('l2', 'spread'), ('l1', 'near')):
                    explicit = vector_connector.search_vector_db(folder, 'l1', 'query', top_k=1, metric=metric)
                    self.assertEqual(explicit['id'].iat[0], expected)
                default = vector_connector.search_vector_db(folder, 'l1', 'query', top_k=1)
                self.assertEqual(default['id'].iat[0], 'near')
                self.assertEqual(legacy_path.read_bytes(), before)
