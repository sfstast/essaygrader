import unittest
import json
from tests.rubric_fixture import rubric_fixture
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.headers = {'X-Anthropic-Key': 'test-key'}

    def test_static_and_config(self):
        self.assertEqual(self.client.get('/api/health').json(), {'status': 'ok'})
        self.assertIn('Analytical question', self.client.get('/').text)
        self.assertIn('Grade 7', self.client.get('/api/config').json()['grades'])
        for path in ('app.js', 'styles.css'):
            self.assertEqual(self.client.get('/static/' + path).status_code, 200)

    def test_invalid_levels_and_missing_inputs(self):
        self.assertEqual(self.client.post('/api/feedback', json={'grade': 'invalid'}).status_code, 422)
        self.assertEqual(self.client.post('/api/feedback', json={}).status_code, 400)
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}):
            response = self.client.post('/api/feedback', json={'source': 's', 'paragraph': 'p'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('key', response.json()['detail'])

    @patch('server.generate_material')
    def test_generation_preserves_existing_question(self, generate):
        generate.return_value = {'source': 'Original practice.', 'question': 'Replacement'}
        response = self.client.post('/api/generate', headers=self.headers,
            json={'mode': 'both', 'question': 'My question?', 'grade': 'Grade 7'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['question'], 'My question?')
        self.assertEqual(response.json()['source'], 'Original practice.')
        args = generate.call_args.args
        self.assertEqual(args[2], 'Grade 7')
        self.assertEqual(args[-2:], (True, False))

    @patch('server.generate_material')
    def test_generation_preserves_source_and_blocks_overwrite(self, generate):
        generate.return_value = {'source': 'Replacement', 'question': 'New question?'}
        response = self.client.post('/api/generate', headers=self.headers,
            json={'mode': 'question', 'source': 'My source'})
        self.assertEqual(response.json()['source'], 'My source')
        self.assertEqual(response.json()['question'], 'New question?')
        response = self.client.post('/api/generate', headers=self.headers,
            json={'mode': 'both', 'source': 's', 'question': 'q'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(generate.call_count, 1)

    @patch('server.request_text')
    def test_feedback_includes_question_and_grade(self, request):
        request.return_value = json.dumps(rubric_fixture('My source','My paragraph'))
        response = self.client.post('/api/feedback', headers=self.headers,
            json={'source': 'My source', 'paragraph': 'My paragraph', 'question': 'Why?', 'grade': 'Grade 8'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['criterion_scores']['analysis'],3)
        self.assertNotIn('score',response.json())
        self.assertIn('Analysis: 3/4',response.json()['feedback'])
        self.assertTrue(response.json()['quotation_presence_verified'])
        self.assertFalse(response.json()['teacher_calibrated'])
        self.assertIn('Why?', request.call_args.args[3])
        self.assertIn('Grade 8', request.call_args.args[3])
        self.assertIn('early high school', request.call_args.args[2])

    @patch('server.request_text', side_effect=RuntimeError('sensitive-detail'))
    def test_api_error_does_not_expose_details(self, request):
        response = self.client.post('/api/feedback', headers=self.headers,
            json={'source': 's', 'paragraph': 'p'})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('sensitive-detail', response.text)
        self.assertNotIn('test-key', response.text)


if __name__ == '__main__':
    unittest.main()
