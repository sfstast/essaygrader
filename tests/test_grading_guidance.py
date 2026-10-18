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
