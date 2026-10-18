"""Private reference loading with synthetic text, never publisher samples."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import grading_guidance as guidance

class ReferenceTests(unittest.TestCase):
    def bundle(self):
        return {'source':'Synthetic test reference','extraction_reviewed':True,
                'pages':[{'page':1,'text':'Synthetic commentary: distinguish evidence from summary.'}]}

    def test_reviewed_private_secret_is_used_without_exposing_content_in_status(self):
        with patch.dict(os.environ,{'AMPLIFY_REFERENCE_JSON':json.dumps(self.bundle())}):
            self.assertTrue(guidance.reference_status()['amplify_loaded'])
            self.assertNotIn('Synthetic commentary',str(guidance.reference_status()))
            prompt=guidance.reference_guidance('Grade 8')
            self.assertIn('Synthetic commentary',prompt)
            self.assertIn('Never translate publisher scores',prompt)

    def test_missing_invalid_or_unreviewed_references_are_not_claimed_as_loaded(self):
        with TemporaryDirectory() as temp, patch.object(guidance,'AMPLIFY',Path(temp)/'missing.json'):
            values=['','not json','[]',json.dumps({'extraction_reviewed':True,'pages':[]})]
            bundle=self.bundle();bundle['extraction_reviewed']=False;values.append(json.dumps(bundle))
            for value in values:
                with patch.dict(os.environ,{'AMPLIFY_REFERENCE_JSON':value}):
                    self.assertFalse(guidance.reference_status()['amplify_loaded'])

    def test_private_reference_excerpts_are_bounded(self):
        bundle=self.bundle();bundle['pages']=[{'page':i+1,'text':'x'*5000} for i in range(5)]
        with patch.dict(os.environ,{'AMPLIFY_REFERENCE_JSON':json.dumps(bundle)}):
            text=guidance.reference_guidance()
        self.assertLess(len(text),13000)
        self.assertIn('"excerpt_truncated": true',text)

    def test_compressed_private_bundle_is_supported_and_malformed_data_rejected(self):
        import base64,zlib
        packed=base64.b64encode(zlib.compress(json.dumps(self.bundle()).encode())).decode()
        with patch.dict(os.environ,{'AMPLIFY_REFERENCE_JSON':'','AMPLIFY_REFERENCE_B64':packed}):
            self.assertTrue(guidance.reference_status()['amplify_loaded'])
        for bad in ['not valid base64',base64.b64encode(b'not zlib').decode(),
                    base64.b64encode(zlib.compress(b'x'*1000001)).decode()]:
            with patch.dict(os.environ,{'AMPLIFY_REFERENCE_JSON':'','AMPLIFY_REFERENCE_B64':bad}):
                self.assertFalse(guidance.reference_status()['amplify_loaded'])

    def test_indexed_selection_retains_complete_contrasting_examples_and_original_scores(self):
        bundle=self.bundle();bundle['pages']=[];bundle['examples']=[]
        for grade in [6,7,8]:
            for score in [1,4]:
                number=grade*10+score
                bundle['pages'].append({'page':number,'text':f'Synthetic grade {grade} commentary, publisher score {score}.'})
                bundle['examples'].append({'grade':grade,'skill':'use_of_evidence','publisher_score':score,'pages':[number]})
        for grade,expected in [('Grade 6',6),('Grade 7',7),('Grade 8',8),('Grade 11',8)]:
            selected=guidance.amplify_selection(bundle,grade)
            self.assertEqual([row['publisher_score'] for row in selected],[1,4])
            self.assertTrue(all(row['reference_grade']==expected for row in selected))
        with patch.dict(os.environ,{'AMPLIFY_REFERENCE_JSON':json.dumps(bundle)}):
            prompt=guidance.reference_guidance('Grade 7')
            self.assertIn('Synthetic grade 7 commentary',prompt)
            self.assertNotIn('Synthetic grade 6 commentary',prompt)
            self.assertIn('Do not apply Amplify word-count cutoffs',prompt)

    def test_private_reference_content_reaches_actual_grading_request_but_not_public_config(self):
        from unittest.mock import Mock
        from rubric_assessment import assess
        from tests.rubric_fixture import rubric_fixture
        from fastapi.testclient import TestClient
        from server import app
        private=self.bundle();private['pages'][0]['text']='PRIVATE_SYNTHETIC_REFERENCE_SENTINEL'
        request=Mock(return_value=json.dumps(rubric_fixture()))
        with patch.dict(os.environ,{'AMPLIFY_REFERENCE_JSON':json.dumps(private)}):
            result=assess(request,'key','model','Grade 8','On-level / regular','My source','My paragraph')
            config=TestClient(app).get('/api/config')
        self.assertIn('PRIVATE_SYNTHETIC_REFERENCE_SENTINEL',request.call_args.args[2])
        self.assertNotIn('PRIVATE_SYNTHETIC_REFERENCE_SENTINEL',config.text)
        self.assertTrue(result['references']['amplify_loaded'])
        self.assertEqual(result['score_out_of_10'],7.5)
        self.assertEqual(request.call_count,1)
