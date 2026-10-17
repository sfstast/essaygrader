import json
from pathlib import Path
import tempfile
import unittest
from model_work.thoughtful_learning import parse_page, messages, digest, preflight

class ThoughtfulTests(unittest.TestCase):
    def row(self):
        html='''<div class="assessmentModelDesc assessmentQualPoor"><h1>Poor Essay</h1></div>
        <div class="field-name-body"><h3>A title</h3><p>My <em>actual</em> writing.</p><p>Second paragraph.</p></div>
        <div class="views-field-field-grade-level"><a>Grade 11</a></div>
        <div class="views-field-field-form"><a>Literary Analysis</a></div>
        <a href="/assessmentmodels/related">Strong alternative</a><aside>Not student writing</aside>'''
        return parse_page(html,'https://k12.thoughtfullearning.com/assessmentmodels/example')
    def test_extracts_only_student_body_and_native_rating(self):
        row=self.row()
        self.assertEqual(row['writing'],'My actual writing.\n\nSecond paragraph.')
        self.assertEqual(row['rating'],'Poor')
        self.assertEqual(row['grades'],['Grade 11'])
        self.assertEqual(json.loads(messages(row)[-1]['content']),{'rating':'Poor'})
        self.assertNotIn('Poor',messages(row)[1]['content'])
        self.assertIsNone(row['numeric_rubric_scores'])
    def test_unknown_rating_fails_closed(self):
        with self.assertRaises(ValueError): parse_page('<div></div>','test')
    def test_preflight_rejects_related_groups_and_modified_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m={'schema':'thoughtful-native-ratings-v1','permission':{'basis':'user_attestation_in_chat'},'sha256':{},'splits':{}}
            for i,name in enumerate(('train','validation','test')):
                row={**self.row(),'id':str(i),'group':'same-related-assignment','writing':str(i)}
                data=(json.dumps(row)+'\n').encode();(root/(name+'.jsonl')).write_bytes(data)
                m['sha256'][name]=digest(data);m['splits'][name]=[str(i)]
            (root/'manifest.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'contamination'):preflight(root)
            (root/'train.jsonl').write_text('changed')
            with self.assertRaisesRegex(ValueError,'checksum'):preflight(root)

    def test_colab_notebook_compiles_and_requires_no_uploaded_bundle(self):
        notebook=json.loads(Path('notebooks/thoughtful_learning_training.ipynb').read_text())
        sources=[]
        for i,cell in enumerate(notebook['cells']):
            if cell['cell_type']=='code':
                source=''.join(cell['source']);compile(source,f'cell-{i}','exec');sources.append(source)
        setup=sources[0]
        self.assertNotIn('files.upload',setup)
        self.assertIn('model_work.thoughtful_learning',setup)
        self.assertIn('tempfile.mkdtemp',setup)
