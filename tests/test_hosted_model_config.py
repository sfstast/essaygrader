import os
import unittest
from unittest.mock import patch

from model_clients import providers
from server import Assignment, requester


class HostedModelConfigTests(unittest.TestCase):
    def test_generation_requests_base_model(self):
        data = Assignment(provider='open_model', model='essaygrader-experimental')
        with patch('server.request_open_text', return_value='response') as request:
            requester(data, generation=True)('key', data.model, 'system', 'message')
        self.assertTrue(request.call_args.kwargs['use_base_model'])

    def test_feedback_keeps_adapter_enabled(self):
        data = Assignment(provider='open_model', model='essaygrader-experimental')
        with patch('server.request_open_text', return_value='response') as request:
            requester(data)('key', data.model, 'system', 'message')
        self.assertFalse(request.call_args.kwargs['use_base_model'])

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
