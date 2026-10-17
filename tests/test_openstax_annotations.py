import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from model_work.openstax_annotations import extract, messages, preflight, digest

class AnnotationTests(unittest.TestCase):
    def test_adjacent_comments_not_invented_scores_or_quoted_sources(self):
        root=ET.fromstring('''<document xmlns="http://cnx.rice.edu/cnxml"><title>Sample by Author</title><content>
          <para class="student-sample">An original claim connects these ideas.</para>
          <para class="annotation-text" id="a">This claim establishes the direction.</para>
          <para class="annotation-text" id="b">The opening also connects the ideas.</para>
          <para class="student-sample">A “borrowed quotation” appears here.</para>
          <para class="annotation-text" id="c">Quoted sources need careful handling.</para>
          <para>Editorial directions must not become student text.</para>
          <para class="annotation-text" id="d">This comment has no student excerpt.</para>
        </content></document>''')
        rows,omitted=extract(root,'fixture')
        self.assertEqual(len(rows),2);self.assertEqual(omitted,1)
        self.assertEqual(rows[0]['excerpt'],rows[1]['excerpt'])
        self.assertIsNone(rows[0]['numeric_rubric_scores'])
        self.assertEqual(messages(rows[0])[-1]['content'],rows[0]['comment'])
        self.assertNotIn('comment',messages(rows[0])[1]['content'])

    def test_cross_split_author_or_text_overlap_rejected(self):
        from model_work.openstax_annotations import REVISION
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);manifest={'schema':'openstax-editorial-annotations-v1','revision':REVISION,'license':'CC-BY-4.0','sha256':{},'splits':{}}
            for name in ('train','validation','test'):
                row={'id':name,'group':'same-author','excerpt':name,'comment':'Fixture feedback only.',
                     'numeric_rubric_scores':None,'provenance':'published_editorial_annotation'}
                data=(json.dumps(row)+'\n').encode();(out/f'{name}.jsonl').write_bytes(data)
                manifest['sha256'][name]=digest(data);manifest['splits'][name]=[name]
            (out/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'contamination'):preflight(out)
