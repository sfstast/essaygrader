import unittest
from fastapi.testclient import TestClient
from server import app
from claude_models import task_model
from model_clients import providers


class ClaudeConfigTests(unittest.TestCase):
    def test_only_claude_is_offered(self):
        self.assertEqual([p['id'] for p in providers()], ['anthropic'])

    def test_removed_providers_are_rejected_before_calling_models(self):
        client = TestClient(app)
        for provider in ['open_model', 'nvidia']:
            response = client.post('/api/feedback', json={
                'provider': provider, 'source': 'source', 'paragraph': 'writing'})
            self.assertEqual(response.status_code, 422)

    def test_recommended_models_follow_task_and_explicit_choice(self):
        self.assertEqual(task_model('auto', 'grade'), 'claude-sonnet-5-5')
        self.assertEqual(task_model('auto', 'generate'), 'claude-haiku-5-5')
        self.assertEqual(task_model('auto', 'tutor'), 'claude-haiku-5-5')
        self.assertEqual(task_model('claude-sonnet-5-5', 'grade'), 'claude-sonnet-5-5')
        with self.assertRaises(ValueError):
            task_model('some-other-provider/model', 'grade')
