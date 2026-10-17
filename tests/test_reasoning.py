"""Verify rubric contracts and textual grounding, not real-world model accuracy."""
import json
from model_work.public_arguments import read_pairs
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from reasoning_assessment import assessment_prompt, parse_assessment, score_assessment, assess
from tests.assessment_fixture import assessment_fixture
from model_work.train_argument_quality import group_split


class ReasoningTests(unittest.TestCase):
    def test_relative_grade_anchors_and_reasoning_focus(self):
        prompt=assessment_prompt('Grade 7','On-level / regular')
        self.assertIn('late middle school',prompt)
        self.assertIn('Grammar, length, vocabulary',prompt)
        self.assertIn('No explanation connecting evidence to claim',prompt)
        self.assertIn('do not',prompt.lower())
        self.assertIn('source_quote',prompt)

    def test_quote_presence_rejects_fabrications_without_issuing_grade(self):
        data=assessment_fixture()
        data['evidence_checks'][0]['source_quote']='A fabricated source quotation.'
        with self.assertRaisesRegex(ValueError,'No grade was issued'):
            parse_assessment(json.dumps(data),'My source','My paragraph')
        data=assessment_fixture();data['evidence_checks'][0]['paragraph_quote']='Not in the paragraph'
        with self.assertRaisesRegex(ValueError,'No grade was issued'):
            parse_assessment(json.dumps(data),'My source','My paragraph')

    def test_polished_summary_and_circular_warrant_cannot_score_high(self):
        for failure in ('summary','warrants'):
            data=assessment_fixture()
            for key in ('claim','task_response','evidence','source_accuracy','warrants','line_of_reasoning'):
                data[key]['score']=4
            if failure=='summary':data['analysis_type']='summary'
            else:data['warrants']['score']=1
            assessment=parse_assessment(json.dumps(data),'My source','My paragraph')
            score,caps=score_assessment(assessment)
            self.assertLessEqual(score,4)
            self.assertTrue(caps)

    def test_central_contradiction_limits_grade_even_with_polished_language(self):
        data=assessment_fixture()
        data['evidence_checks'][0]['verdict']='contradicted'
        assessment=parse_assessment(json.dumps(data),'My source','My paragraph')
        score,caps=score_assessment(assessment)
        self.assertLessEqual(score,4)
        self.assertIn('misreading',' '.join(caps))

    def test_central_overclaim_and_missing_evidence_limit_grade(self):
        data=assessment_fixture()
        data['evidence_checks'][0]['verdict']='overstated'
        result=parse_assessment(json.dumps(data),'My source','My paragraph')
        self.assertLessEqual(score_assessment(result)[0],6)
        data=assessment_fixture();data['evidence']['score']=1
        result=parse_assessment(json.dumps(data),'My source','My paragraph')
        self.assertLessEqual(score_assessment(result)[0],4)

    def test_evidence_credit_requires_a_checkable_link_and_bounds(self):
        data=assessment_fixture();data['evidence_checks']=[]
        with self.assertRaisesRegex(ValueError,'without a checkable'):
            parse_assessment(json.dumps(data),'My source','My paragraph')
        data=assessment_fixture();data['claim']['score']=5
        with self.assertRaises(ValueError):
            parse_assessment(json.dumps(data),'My source','My paragraph')

    def test_original_assessment_not_provider_controls_overall_grade(self):
        data=assessment_fixture()
        result=assess(lambda *args:json.dumps(data),'test','model','Grade 7','On-level / regular','My source','My paragraph','Why?')
        self.assertEqual(result['score'],8)
        self.assertFalse(result['teacher_calibrated'])
        self.assertIn('Evidence and inference checks',result['feedback'])
        self.assertIn('not independently verify',result['feedback'])


class PublicSplitTests(unittest.TestCase):
    def test_public_source_checksum_is_required(self):
        with TemporaryDirectory() as temp:
            (Path(temp)/'source.zip').write_bytes(b'not the reviewed source archive')
            with self.assertRaisesRegex(ValueError,'integrity'):
                read_pairs(temp)

    def test_topics_and_exact_argument_text_are_disjoint(self):
        rows=[]
        for i in range(10):
            for j in range(2):
                rows.append({'id':f'{i}-{j}','topic':f'topic-{i}','a1':f'A unique statement for topic {i} side A.','a2':f'A unique statement for topic {i} side B.','label':'a1'})
        splits,removed=group_split(rows)
        seen_topics={};seen_text={}
        for split, records in splits.items():
            for row in records:
                self.assertEqual(seen_topics.setdefault(row['topic'],split),split)
                for key in ('a1','a2'):self.assertEqual(seen_text.setdefault(row[key],split),split)
        self.assertTrue(all(len(v)>0 for v in splits.values()))


if __name__=='__main__':unittest.main()
