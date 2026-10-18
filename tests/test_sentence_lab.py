import json
import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from server import app
from sentence_lab import BY_ID, EXERCISES, assess_sentence


def sentence_fixture():
    return {'target_id':'participial','matches_target':True,
            'explanation':'The opening participial phrase describes Mara without a dangling modifier.',
            'parts':[{'text':'Exhausted by the climb','role':'Participial phrase describing Mara'}],
            'next_step':'Try placing a participial phrase after the noun it modifies.',
            'example_revision':'Mara, exhausted by the climb, rested beside the path.'}


class SentenceLabTests(unittest.TestCase):
    def test_identification_bank_is_free_and_all_highlights_exist(self):
        with patch('server.request_text') as request:
            response=TestClient(app).get('/api/sentence-lab')
            self.assertEqual(response.status_code,200);request.assert_not_called()
        self.assertEqual(len(response.json()['lessons']),10)
        self.assertEqual(len(EXERCISES),20)
        for _,target,sentence,highlight,_ in EXERCISES:
            self.assertIn(target,BY_ID)
            if BY_ID[target]['group']=='phrases':
                self.assertTrue(highlight);self.assertIn(highlight,sentence)
        self.assertEqual({row[1] for row in EXERCISES},set(BY_ID))

    def test_writing_review_checks_actual_parts_and_target(self):
        request=Mock(return_value=json.dumps(sentence_fixture()))
        result=assess_sentence(request,'key','model','Grade 8','participial',
                               'Exhausted by the climb, Mara rested.')
        self.assertTrue(result['matches_target']);self.assertEqual(request.call_count,1)
        for bad in ['target','quote']:
            fixture=sentence_fixture()
            if bad=='target':fixture['target_id']='gerund'
            else:fixture['parts'][0]['text']='Words the student did not write'
            with self.assertRaisesRegex(ValueError,'match'):
                assess_sentence(lambda *args:json.dumps(fixture),'key','model','Grade 8','participial',
                                'Exhausted by the climb, Mara rested.')

    @patch('server.request_text',return_value=json.dumps(sentence_fixture()))
    def test_api_writing_review_uses_haiku_once(self,request):
        response=TestClient(app).post('/api/sentence-lab/review',headers={'X-Model-Key':'fake'},json={
            'target_id':'participial','sentence':'Exhausted by the climb, Mara rested.'})
        self.assertEqual(response.status_code,200);self.assertEqual(request.call_count,1)
        self.assertEqual(request.call_args.args[1],'claude-haiku-5-5')

    @patch('server.request_text')
    def test_invalid_target_and_blank_sentence_make_no_paid_calls(self,request):
        client=TestClient(app)
        for body in [{'target_id':'made-up','sentence':'A sentence.'},{'target_id':'simple','sentence':'   '}]:
            self.assertEqual(client.post('/api/sentence-lab/review',json=body).status_code,422)
        request.assert_not_called()

    def test_all_patterns_have_local_coaching_and_topics(self):
        with patch('server.request_text') as request:
            data=TestClient(app).get('/api/sentence-lab').json()
        request.assert_not_called()
        self.assertGreaterEqual(len(data['topics']),6)
        for lesson in data['lessons']:
            self.assertEqual(len(lesson['steps']),3)
            self.assertTrue(all(lesson[key] for key in ('frame','watch_out','starter')))

    @patch('server.request_text',return_value=json.dumps(sentence_fixture()))
    def test_optional_topic_reaches_review_without_shipping_local_guide(self,request):
        client=TestClient(app)
        response=client.post('/api/sentence-lab/review',headers={'X-Model-Key':'fake'},json={
            'target_id':'participial','sentence':'Exhausted by the climb, Mara rested.',
            'writing_topic':'A hiking adventure'})
        self.assertEqual(response.status_code,200)
        message=json.loads(request.call_args.args[3])
        self.assertEqual(message['writing_topic'],'A hiking adventure')
        self.assertNotIn('steps',message['target'])
        self.assertEqual(request.call_count,1)
        response=client.post('/api/sentence-lab/review',headers={'X-Model-Key':'fake'},json={
            'target_id':'participial','sentence':'A sentence.','writing_topic':'x'*301})
        self.assertEqual(response.status_code,422)
        self.assertEqual(request.call_count,1)
