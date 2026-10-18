import json
import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from server import app
from vocabulary import VocabularyAnswer, grade_vocabulary


def vocab_fixture():
    return {'results': [
        {'word':'resilient','meaning_score':2,'usage_score':1,'feedback':'The meaning is accurate; add context to demonstrate recovery.',
         'suggested_definition':'Able to recover after difficulty.','example_sentence':'After losing the match, the resilient team returned to practice.'},
        {'word':'meticulous','meaning_score':2,'usage_score':2,'feedback':'The definition and careful-work example both fit.',
         'suggested_definition':'Very careful and attentive to detail.','example_sentence':'The meticulous editor checked every date twice.'},
    ]}


def answers():
    return [VocabularyAnswer(word='resilient',definition='able to recover',sentence='The resilient child kept trying.'),
            VocabularyAnswer(word='meticulous',definition='very careful',sentence='The meticulous chef weighed each ingredient.')]


class VocabularyTests(unittest.TestCase):
    def test_batch_uses_one_call_and_app_calculates_transparent_scores(self):
        request=Mock(return_value=json.dumps(vocab_fixture()))
        result=grade_vocabulary(request,'key','model','Grade 7',answers(),'Learn this week’s words.')
        self.assertEqual(request.call_count,1)
        self.assertEqual((result['earned'],result['possible'],result['percentage']),(7,8,88))
        self.assertEqual(result['review_words'],['resilient'])
        self.assertIn('learning_goal',request.call_args.args[3])

    def test_missing_duplicate_or_extra_results_are_rejected(self):
        for results in [vocab_fixture()['results'][:1],vocab_fixture()['results']+[vocab_fixture()['results'][0]]]:
            with self.assertRaisesRegex(ValueError,'match'):
                grade_vocabulary(lambda *args:json.dumps({'results':results}),'key','model','Grade 7',answers())

    @patch('server.request_text',return_value=json.dumps(vocab_fixture()))
    def test_api_routes_batch_to_haiku_without_sending_essay_context(self,request):
        response=TestClient(app).post('/api/vocabulary/grade',headers={'X-Model-Key':'fake-key'},json={
            'answers':[a.model_dump() for a in answers()], 'learning_goal':'Learn these words'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(request.call_args.args[1],'claude-haiku-5-5')
        self.assertEqual(request.call_count,1)
        self.assertIn('VocabularyAssessment',str(request.call_args.kwargs['output_schema']))
        self.assertNotIn('source',json.loads(request.call_args.args[3]))

    @patch('server.request_text')
    def test_incomplete_or_duplicate_input_is_rejected_before_paid_call(self,request):
        client=TestClient(app)
        for rows in [[answers()[0].model_dump()]*2,[{**answers()[0].model_dump(),'definition':'   '}],[]]:
            self.assertEqual(client.post('/api/vocabulary/grade',json={'answers':rows}).status_code,422)
        request.assert_not_called()
