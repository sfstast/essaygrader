import json
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

import httpx
from fastapi.testclient import TestClient

from model_clients import ModelRequestError, request_open_text
from model_work.data import Example, collect_reviews, messages_for, read_examples, prepare, split_examples, normalized_hash
from model_work.evaluate import benchmark, parse_grade, summarize, load_models
from model_work.train_lora import preflight, tokenize_example, train
from server import app

DEMO = Path(__file__).resolve().parents[1] / 'model_work/templates/demo.jsonl'
MODELS = DEMO.parents[1] / 'models.example.json'


class DataTests(unittest.TestCase):
    def setUp(self):
        self.rows = read_examples(DEMO,allow_demo=True)

    def test_fixtures_and_unapproved_records_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'Synthetic'):
            read_examples(DEMO)
        for field in ('permission_to_use','anonymized'):
            row = self.rows[0].model_dump(); row[field] = False
            with self.assertRaises(ValueError):
                Example.model_validate(row)
        row = self.rows[0].model_dump(); row['teacher_scores'] = row['teacher_scores'][:1]
        with self.assertRaises(ValueError):
            Example.model_validate(row)

    def test_splits_prevent_student_assignment_source_and_duplicate_leakage(self):
        splits = split_examples(self.rows)
        reverse = split_examples(list(reversed(self.rows)))
        self.assertEqual({k:sorted(r.id for r in v) for k,v in splits.items()},
                         {k:sorted(r.id for r in v) for k,v in reverse.items()})
        seen = {}
        for split, rows in splits.items():
            for row in rows:
                for key in (('student',row.student_id),('assignment',row.assignment_id),
                            ('source',normalized_hash(row.source)),('paragraph',normalized_hash(row.paragraph))):
                    if key in seen:
                        self.assertEqual(seen[key],split)
                    seen[key] = split
        linked = [r.model_copy(deep=True) for r in self.rows]
        linked[2].student_id = linked[0].student_id
        linked[4].assignment_id = linked[2].assignment_id
        group = split_examples(linked)
        where = {r.id:name for name,rows in group.items() for r in rows}
        self.assertEqual(where[linked[0].id],where[linked[4].id])

    def test_prepare_is_repeatable_and_test_is_not_training_export(self):
        with TemporaryDirectory() as temp:
            out = Path(temp)/'prepared'
            first = prepare(DEMO,out,allow_demo=True)
            second = prepare(DEMO,Path(temp)/'second',allow_demo=True)
            self.assertEqual(first,second)
            self.assertFalse((out/'test.messages.jsonl').exists())
            self.assertTrue(first['demo_only'])
            report,splits = preflight(out)
            self.assertFalse(report['data_eligible_for_training'])
            with self.assertRaisesRegex(ValueError,'Synthetic'):
                train(SimpleNamespace(),report,splits)
            with self.assertRaises(FileExistsError):
                prepare(DEMO,out,allow_demo=True)

    def test_collection_requires_completed_teacher_reviews(self):
        with TemporaryDirectory() as temp:
            reviews = Path(temp)/'reviews'; reviews.mkdir()
            template = DEMO.parent/'teacher-review.json'
            review = reviews/'review.json'; review.write_text(template.read_text())
            with self.assertRaisesRegex(ValueError,'incomplete'):
                collect_reviews(reviews,Path(temp)/'data.jsonl')
            row = self.rows[0].model_dump(); row['provenance']='teacher_reviewed'
            review.write_text(json.dumps(row))
            result = collect_reviews(reviews,Path(temp)/'data.jsonl')
            self.assertEqual(result['collected_examples'],1)
            self.assertFalse(result['training_performed'])

    def test_preflight_detects_modified_split_and_tutor_has_no_grading_format(self):
        with TemporaryDirectory() as temp:
            out = Path(temp)/'prepared'; prepare(DEMO,out,allow_demo=True)
            path = out/'train.jsonl'; path.write_text(path.read_text().replace('without an audience','in public'))
            with self.assertRaises(ValueError):
                preflight(out)
        tutor = next(row for row in self.rows if row.task=='tutor')
        system = messages_for(tutor)[0]['content']
        self.assertNotIn('Score overall analytical reasoning',system)
        self.assertIn('not a score',system)

    def test_supervised_tokens_mask_prompt_and_reject_truncation(self):
        tokenizer = MagicMock()
        tokenizer.apply_chat_template.side_effect = [[1,2],[1,2,3,4]]
        result = tokenize_example(tokenizer,[{'role':'user','content':'q'},{'role':'assistant','content':'a'}],10)
        self.assertEqual(result['labels'],[-100,-100,3,4])
        tokenizer.apply_chat_template.side_effect = [[1,2],[1,2,3,4]]
        with self.assertRaisesRegex(ValueError,'exceeds'):
            tokenize_example(tokenizer,[],3)
        tokenizer.apply_chat_template.side_effect = [[1,2],[1,5,3,4]]
        with self.assertRaisesRegex(ValueError,'prefix'):
            tokenize_example(tokenizer,[],10)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.rows = read_examples(DEMO,allow_demo=True)

    def test_score_schema_and_known_metrics(self):
        for score in ('7',11,True):
            with self.assertRaises(ValueError):
                parse_grade(json.dumps({'score':score,'feedback':'Specific evidence-based feedback.'}))
        attempts = [
            {'id':self.rows[0].id,'repeat':0,'attack':False,'score':8,'seconds':1},
            {'id':self.rows[0].id,'repeat':1,'attack':False,'score':6,'seconds':1},
            {'id':self.rows[2].id,'repeat':0,'attack':False,'score':5,'seconds':1},
            {'id':self.rows[0].id,'repeat':0,'attack':True,'score':10,'seconds':1},
            {'id':self.rows[2].id,'repeat':1,'attack':False,'score':None,'seconds':1},
        ]
        metrics = summarize(self.rows,attempts)
        self.assertAlmostEqual(metrics['mae'],4/3)
        self.assertAlmostEqual(metrics['within_one'],2/3)
        self.assertAlmostEqual(metrics['mean_bias'],-2/3)
        self.assertEqual(metrics['mean_repeat_score_range'],2)
        self.assertEqual(metrics['mean_attack_score_change'],2)
        self.assertEqual(metrics['failed_attempts'],1)
        self.assertFalse(metrics['complete'])
        self.assertIsNone(summarize(self.rows,[])['mae'])

    @patch('model_work.evaluate.request_open_text')
    @patch('model_work.evaluate.request_text')
    def test_dry_run_makes_no_calls_and_claims_no_accuracy(self,claude,open_model):
        with TemporaryDirectory() as temp:
            report = benchmark(DEMO,MODELS,Path(temp)/'dry',dry_run=True,allow_demo=True)
            self.assertEqual(report['mode'],'dry_run')
            self.assertEqual(report['planned_calls'],48)
            self.assertTrue(report['demo_only'])
            self.assertFalse(report['training_performed'])
            self.assertTrue(all(m['metrics'] is None for m in report['models'].values()))
            claude.assert_not_called(); open_model.assert_not_called()

    def test_successful_mock_comparison_still_requires_human_tutor_review(self):
        def response(key,model,system,user,**kwargs):
            if 'Return only JSON with score' in system:
                return json.dumps({'score':7,'feedback':'Explain why the detail supports this claim.'})
            return 'Why does staying without an audience matter?'
        with TemporaryDirectory() as temp, patch.dict('os.environ',{
                'ANTHROPIC_API_KEY':'test','OPEN_MODEL_API_KEY':'test','OPEN_MODEL_BASE_URL':'http://localhost:9000/v1'}), \
                patch('model_work.evaluate.request_open_text',side_effect=response), \
                patch('model_work.evaluate.request_text',side_effect=response):
            report = benchmark(DEMO,MODELS,Path(temp)/'run',repeats=2,allow_demo=True,injection_check=True)
            queue = json.loads((Path(temp)/'run'/'tutor_review.json').read_text())
            self.assertEqual(len(queue[0]['model_reviews']),2)
            self.assertIsNone(queue[0]['model_reviews'][0]['human_ratings']['source_accuracy'])
            self.assertIn('volunteer',queue[0]['source'])
            self.assertTrue(report['demo_only'])
            self.assertFalse(report['training_performed'])
            for model in report['models'].values():
                self.assertTrue(model['metrics']['complete'])
                self.assertEqual(model['metrics']['unique_examples'],6)
                self.assertEqual(model['metrics']['attack_pairs'],12)
                self.assertEqual(model['tutor_quality'],'human_review_pending')
                self.assertEqual(model['tutor_calls'],6)

    @patch('model_work.evaluate.request_open_text',side_effect=RuntimeError('private-key-and-student-text'))
    @patch('model_work.evaluate.request_text',side_effect=RuntimeError('private-key-and-student-text'))
    def test_failed_requests_are_counted_and_sanitized(self,*mocks):
        with TemporaryDirectory() as temp, patch.dict('os.environ',{
            'ANTHROPIC_API_KEY':'test','OPEN_MODEL_API_KEY':'test','OPEN_MODEL_BASE_URL':'http://localhost:9000/v1'}):
            output = Path(temp)/'run'
            report = benchmark(DEMO,MODELS,output,repeats=1,allow_demo=True)
            self.assertTrue(all(m['metrics']['failed_attempts']==6 for m in report['models'].values()))
            self.assertTrue(all(m['tutor_failed_calls']==6 for m in report['models'].values()))
            for file in output.iterdir():
                self.assertNotIn('private-key-and-student-text',file.read_text())


class ProviderAndTutorTests(unittest.TestCase):
    def test_hosted_request_and_response_validation(self):
        with patch('model_clients.httpx.Client') as factory:
            client = factory.return_value.__enter__.return_value
            client.post.return_value = httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'<think>private reasoning</think>Helpful feedback.'}}]})
            result = request_open_text('nvidia-key','model-id','system','message',provider='nvidia')
            self.assertEqual(result,'Helpful feedback.')
            self.assertEqual(client.post.call_args.args[0],'https://integrate.api.nvidia.com/v1/chat/completions')
            client.post.return_value = httpx.Response(401,text='private-key')
            with self.assertRaises(ModelRequestError) as error:
                request_open_text('key','model','s','u',provider='nvidia')
            self.assertNotIn('private-key',str(error.exception))
        with patch.dict('os.environ',{'OPEN_MODEL_BASE_URL':'http://example.com/v1'}):
            with self.assertRaisesRegex(ModelRequestError,'URL'):
                request_open_text('key','model','s','u',provider='open_model')

    def test_provider_credentials_are_not_crossed(self):
        client = TestClient(app)
        with patch.dict('os.environ',{'NVIDIA_API_KEY':''}), patch('server.request_open_text') as request:
            response = client.post('/api/feedback',headers={'X-Anthropic-Key':'claude-key'},json={
                'provider':'nvidia','source':'source','paragraph':'paragraph'})
            self.assertEqual(response.status_code,400)
            request.assert_not_called()

    @patch('server.request_open_text',return_value='Why does that detail support your claim?')
    def test_tutor_uses_provider_classroom_and_hint_policy(self,request):
        response = TestClient(app).post('/api/tutor',headers={'X-Model-Key':'test-nvidia-key'},json={
            'provider':'nvidia','model':'nvidia/test-model','grade':'Grade 7','source':'source text',
            'paragraph':'my paragraph','question':'Why did they help?', 'student_message':'Write my paragraph for me.'})
        self.assertEqual(response.status_code,200)
        self.assertIn('Why',response.json()['reply'])
        self.assertEqual(request.call_args.kwargs['provider'],'nvidia')
        self.assertIn('Do not write a finished paragraph',request.call_args.args[2])
        self.assertIn('Why did they help?',request.call_args.args[3])


if __name__ == '__main__':
    unittest.main()
