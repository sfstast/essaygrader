"""Regression: the real SDK parses truncated JSON before stop_reason is checked."""
import json
import unittest
from unittest.mock import patch
import httpx2 as httpx
from anthropic import Anthropic
from fastapi.testclient import TestClient
from grading import request_text
from sentence_lab import SentenceAssessment
from server import app
from tests.test_sentence_lab import sentence_fixture

class StructuredResponseTests(unittest.TestCase):
    def client(self,body,stop_reason='max_tokens'):
        recorded=[]
        def respond(request):
            recorded.append(json.loads(request.content))
            return httpx.Response(200,json={
                'id':'msg_test','type':'message','role':'assistant','model':'claude-haiku-5-5',
                'stop_reason':stop_reason,'stop_sequence':None,
                'content':[{'type':'text','text':body}],
                'usage':{'input_tokens':500,'output_tokens':2048}})
        return Anthropic(api_key='fake',http_client=httpx.Client(transport=httpx.MockTransport(respond))),recorded

    def test_sdk_parse_failures_are_safe_without_partial_results_or_hidden_retry(self):
        for reason in ['max_tokens','end_turn']:
            client,calls=self.client('{"target_id":"participial","explanation":"PRIVATE_STUDENT_TEXT',reason)
            with patch('grading.Anthropic',return_value=client):
                with self.assertRaisesRegex(ValueError,'incomplete review') as error:
                    request_text('key','claude-haiku-5-5','system','student',output_schema=SentenceAssessment,max_tokens=2048)
            self.assertNotIn('PRIVATE_STUDENT_TEXT',str(error.exception))
            self.assertNotIn('json_invalid',str(error.exception))
            self.assertEqual(len(calls),1)

    def test_sentence_endpoint_safely_handles_truncation_and_can_succeed_on_next_attempt(self):
        client,calls=self.client('{"target_id":"participial","explanation":"PRIVATE_STUDENT_TEXT')
        with patch('grading.Anthropic',return_value=client):
            response=TestClient(app).post('/api/sentence-lab/review',headers={'X-Model-Key':'fake'},json={
                'target_id':'participial','sentence':'Exhausted by the climb, Mara rested.'})
        self.assertEqual(response.status_code,502)
        self.assertIn('work is kept',response.json()['detail'])
        self.assertNotIn('PRIVATE_STUDENT_TEXT',response.text)
        self.assertEqual(calls[0]['max_tokens'],2048)
        self.assertEqual(len(calls),1)
        client,calls=self.client(json.dumps(sentence_fixture()),'end_turn')
        with patch('grading.Anthropic',return_value=client):
            response=TestClient(app).post('/api/sentence-lab/review',headers={'X-Model-Key':'fake'},json={
                'target_id':'participial','sentence':'Exhausted by the climb, Mara rested.'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['score_out_of_10'],10)
        self.assertEqual(len(calls),1)
