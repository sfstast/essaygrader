"""Synthetic API-contract fixture, not human scoring ground truth."""
from reasoning_assessment import DIMENSIONS


def assessment_fixture(source='My source',paragraph='My paragraph'):
    dimension={'score':3,'explanation':'The writing connects its central claim to the provided evidence.'}
    return {'summary':'A synthetic response for testing the analytical assessment contract.',
        **{key:dimension.copy() for key in DIMENSIONS}, 'analysis_type':'analysis',
        'evidence_checks':[{'source_quote':source,'paragraph_quote':paragraph,
                           'connection':'The specific detail supports the interpretation through the stated connection.',
                           'verdict':'supported','central_to_claim':True}],
        'strengths':['The paragraph has a focused interpretive claim.'],
        'revision_moves':['Explain the link between this detail and the claim more precisely.','State the limit of the inference.'],
        'complexity_note':'Assess nuance only when the student’s level and assignment call for it.',
        'limitations':['This is a synthetic software fixture, not a teacher judgment.'],
        'next_question':'Why does this particular detail support your interpretation?'}
