import json
import unittest
from pathlib import Path
from model_work.data import Example, messages_for, read_examples
from writing_rubric import RUBRIC_ID, CRITERIA, RubricScores

class UserRubricTests(unittest.TestCase):
    def row(self):
        row=read_examples(Path('model_work/templates/demo.jsonl'),allow_demo=True)[0].model_dump()
        row['rubric_id']=RUBRIC_ID
        for r in row['teacher_scores']:
            r['criterion_scores']={k:2 for k in CRITERIA}
            r['criterion_scores']['analysis']=1
            r['criterion_scores']['mechanics_conventions']=4
        return row

    def test_separate_teacher_labels_reach_training_target(self):
        target=json.loads(messages_for(Example.model_validate(self.row()),True)[-1]['content'])
        self.assertEqual(target['criterion_scores']['analysis'],1)
        self.assertEqual(target['criterion_scores']['mechanics_conventions'],4)
        self.assertEqual(target['rubric_id'],RUBRIC_ID)

    def test_no_derived_or_missing_category_labels(self):
        row=self.row();row['teacher_scores'][0].pop('criterion_scores')
        with self.assertRaises(ValueError):Example.model_validate(row)
        for bad in (0,5,True,2.5):
            scores={k:2 for k in CRITERIA};scores['analysis']=bad
            with self.assertRaises(ValueError):RubricScores.model_validate(scores)
