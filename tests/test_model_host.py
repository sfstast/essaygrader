import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location(
    'model_host', Path(__file__).resolve().parents[1] / 'deploy/open-model/server.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class ModelHostTests(unittest.TestCase):
    def test_requires_private_key(self):
        with patch.dict(os.environ, {'MODEL_SERVER_KEY': 'x' * 32}):
            client = TestClient(host.app)
            response = client.post('/v1/chat/completions', json={
                'model': 'essaygrader-experimental',
                'messages': [{'role': 'user', 'content': 'Hello'}]})
            self.assertEqual(response.status_code, 401)

    def test_busy_model_rejects_concurrent_work(self):
        with patch.dict(os.environ, {'MODEL_SERVER_KEY': 'x' * 32}):
            client = TestClient(host.app)
            host.lock.acquire()
            try:
                response = client.post('/v1/chat/completions',
                    headers={'Authorization': 'Bearer ' + 'x' * 32}, json={
                        'model': 'essaygrader-experimental',
                        'messages': [{'role': 'user', 'content': 'Hello'}]})
                self.assertEqual(response.status_code, 429)
            finally:
                host.lock.release()
