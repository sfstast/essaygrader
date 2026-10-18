import json
import unittest
from unittest.mock import Mock

from grading import generate_material


class PassageLengthTests(unittest.TestCase):
    def generate(self, request, source='', need_source=True, grade='Grade 11'):
        return generate_material('key', 'model', grade, 'On-level / regular',
                                 '', source, '', need_source, True, request_fn=request)

    def test_retries_short_passage_and_accepts_complete_replacement(self):
        full = 'A detailed original practice passage. ' * 40
        request = Mock(side_effect=[
            json.dumps({'source': 'One sentence.', 'question': 'Why?'}),
            json.dumps({'source': full, 'question': 'How does the choice shape the outcome?'}),
        ])
        self.assertEqual(self.generate(request)['source'], full)
        self.assertEqual(request.call_count, 2)

    def test_persistent_short_output_is_not_returned(self):
        request = Mock(return_value=json.dumps({'source': 'One sentence.', 'question': 'Why?'}))
        with self.assertRaisesRegex(ValueError, 'too short'):
            self.generate(request)
        self.assertEqual(request.call_count, 2)

    def test_user_supplied_short_source_is_preserved(self):
        request = Mock(return_value=json.dumps({'source': 'Ignored', 'question': 'Why?'}))
        self.generate(request, source='An intentionally short quotation.', need_source=False)
        self.assertEqual(request.call_count, 1)

    def test_younger_grade_accepts_120_word_passage(self):
        request = Mock(return_value=json.dumps({'source': 'A clear practice passage. ' * 30, 'question': 'Why?'}))
        self.generate(request, grade='Grade 7')
        self.assertEqual(request.call_count, 1)
