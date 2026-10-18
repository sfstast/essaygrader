import os
import unittest
from unittest.mock import patch

from model_clients import providers


class HostedModelConfigTests(unittest.TestCase):
    def test_server_key_is_advertised_without_disclosing_secret(self):
        secret = 'private-model-server-key'
        with patch.dict(os.environ, {
            'OPEN_MODEL_API_KEY': secret,
            'OPEN_MODEL_BASE_URL': 'https://example.org/v1',
            'OPEN_MODEL_NAME': 'essaygrader-experimental',
        }):
            config = next(p for p in providers() if p['id'] == 'open_model')
        self.assertTrue(config['configured'])
        self.assertTrue(config['server_key_configured'])
        self.assertEqual(config['model'], 'essaygrader-experimental')
        self.assertNotIn(secret, str(config))
