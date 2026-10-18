import json
import unittest
from unittest.mock import Mock, patch
import httpx2 as httpx
from anthropic import Anthropic

from rubric_assessment import assess, assessment_prompt, parse_assessment
from tests.rubric_fixture import rubric_fixture
from grading import request_text
from writing_rubric import CRITERIA


class RubricAssessmentTests(unittest.TestCase):
    def test_actual_rubric_and_user_examples_reach_claude_without_invented_total(self):
        request = Mock(return_value=json.dumps(rubric_fixture()))
        result = assess(request, 'key', 'claude-opus-5-5', 'Grade 7', 'On-level / regular',
                        'My source', 'My paragraph')
        system = request.call_args.args[2]
        for label in ['Thesis', 'Organization', 'Control of language', 'Mechanics/conventions']:
            self.assertIn(label, system)
        self.assertIn('slate-grey sky', system)
        self.assertIn('social comparison', system)
        self.assertIn('not independently calibrated teacher scores', system)
        self.assertNotIn('score', result)
        self.assertEqual(result['score_out_of_10'],7.5)
        self.assertIn('18/24 rubric points',result['feedback'])
        self.assertEqual(set(result['criterion_scores']), set(CRITERIA))
        self.assertIn('Analysis: 3/4', result['feedback'])
        self.assertFalse(result['teacher_calibrated'])

    def test_fluent_summary_cannot_be_rewarded_as_analysis(self):
        data = rubric_fixture()
        data['analysis_type'] = 'summary'
        data['control_of_language']['score'] = 4
        with self.assertRaisesRegex(ValueError, 'summary'):
            parse_assessment(json.dumps(data), 'My source', 'My paragraph')
        data['analysis']['score'] = 1
        result = parse_assessment(json.dumps(data), 'My source', 'My paragraph')
        self.assertEqual(result.analysis.score, 1)
        self.assertEqual(result.control_of_language.score, 4)

    def test_fabricated_quotations_and_uncheckable_evidence_are_rejected(self):
        data = rubric_fixture()
        data['evidence_checks'][0]['source_quote'] = 'Invented quotation'
        with self.assertRaisesRegex(ValueError, 'absent'):
            parse_assessment(json.dumps(data), 'My source', 'My paragraph')
        data['evidence_checks'] = []
        with self.assertRaisesRegex(ValueError, 'checkable'):
            parse_assessment(json.dumps(data), 'My source', 'My paragraph')

    def test_failure_preserves_no_partial_scores_without_hidden_repair_calls(self):
        request = Mock(return_value='Not a complete assessment')
        with self.assertRaisesRegex(ValueError, 'six rubric ratings'):
            assess(request, 'key', 'model', 'Grade 11', 'On-level / regular', 's', 'p')
        self.assertEqual(request.call_count, 1)

    def test_invalid_category_scores_are_not_coerced(self):
        for bad in [0, 5, True, 2.5]:
            data = rubric_fixture(); data['analysis']['score'] = bad
            with self.assertRaises(ValueError):
                parse_assessment(json.dumps(data), 'My source', 'My paragraph')

    @patch('grading.Anthropic')
    def test_structured_sdk_path_is_used_for_rubric(self, client):
        from rubric_assessment import UserRubricAssessment
        response = client.return_value.__enter__.return_value.messages.parse.return_value
        response.stop_reason = 'end_turn'
        response.parsed_output = UserRubricAssessment.model_validate(rubric_fixture())
        result = request_text('key', 'claude-opus-5-5', 'system', 'user', output_schema=UserRubricAssessment)
        self.assertEqual(json.loads(result)['analysis']['score'], 3)
        api = client.return_value.__enter__.return_value
        api.messages.parse.assert_called_once()
        api.messages.create.assert_not_called()

    def test_actual_sdk_serializes_cache_and_structured_output_together(self):
        from rubric_assessment import UserRubricAssessment
        recorded = []

        def respond(request):
            recorded.append(json.loads(request.content))
            return httpx.Response(200, json={
                'id': 'msg_test', 'type': 'message', 'role': 'assistant',
                'model': 'claude-sonnet-5-5', 'stop_reason': 'end_turn', 'stop_sequence': None,
                'content': [{'type': 'text', 'text': json.dumps(rubric_fixture())}],
                'usage': {'input_tokens': 1200, 'output_tokens': 500,
                          'cache_read_input_tokens': 800, 'cache_creation_input_tokens': 0},
            })

        client = Anthropic(api_key='fake-key', http_client=httpx.Client(transport=httpx.MockTransport(respond)))
        with patch('grading.Anthropic', return_value=client):
            result = request_text('fake-key', 'claude-sonnet-5-5', 'Stable rubric', 'Student writing',
                                  output_schema=UserRubricAssessment, max_tokens=4096, effort='medium')
        self.assertEqual(recorded[0]['system'][0]['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(recorded[0]['output_config']['effort'], 'medium')
        self.assertEqual(recorded[0]['output_config']['format']['type'], 'json_schema')
        self.assertEqual(result.usage['cache_read_input_tokens'], 800)
        self.assertEqual(result.usage['output_tokens'], 500)

    def test_practice_conversion_preserves_original_category_scores(self):
        for rating,expected in [(1,2.5),(2,5.0),(4,10.0)]:
            fixture=rubric_fixture()
            for key in CRITERIA:fixture[key]['score']=rating
            result=assess(lambda *args:json.dumps(fixture),'key','model','Grade 8','On-level / regular','My source','My paragraph')
            self.assertEqual(result['score_out_of_10'],expected)
            self.assertTrue(all(score==rating for score in result['criterion_scores'].values()))
