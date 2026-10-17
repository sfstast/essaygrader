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

    def test_free_notebook_python_cells_compile_and_preferences_are_unverified(self):
        notebook=json.loads(Path('notebooks/free_gpu_commentary.ipynb').read_text())
        for i,cell in enumerate(notebook['cells']):
            if cell['cell_type']=='code':
                compile(''.join(cell['source']),f'cell-{i}','exec')
        preferences=json.loads(Path('model_work/examples/user_style_preferences.json').read_text())
        self.assertEqual(len(preferences['pairs']),2)
        self.assertFalse(preferences['used_for_numeric_grader_training'])
        self.assertFalse(preferences['used_in_free_gpu_commentary_run'])

    def test_small_model_passes_architecture_gate_but_requires_training_stack(self):
        from types import SimpleNamespace
        from model_work.train_lora import train
        args=SimpleNamespace(model='Qwen/Qwen2.5-1.5B-Instruct',revision='a'*40)
        summary={'demo_only':False,'commercial_use_permissions_confirmed':True,
                 'dependencies_present':{'torch':False}}
        with self.assertRaisesRegex(ValueError,'dependencies are missing'):
            train(args,summary,{})
