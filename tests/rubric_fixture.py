"""Synthetic contract fixture, not teacher-rated calibration data."""
from writing_rubric import CRITERIA


def rubric_fixture(source='My source', paragraph='My paragraph'):
    return {
        'summary': 'The writing links its interpretation to the provided source.',
        **{key: {'score': 3, 'explanation': 'A specific explanation grounded in the current writing.'} for key in CRITERIA},
        'analysis_type': 'analysis',
        'evidence_checks': [{'source_quote': source, 'paragraph_quote': paragraph,
            'connection': 'This detail supports the interpretation through an explicit because-link.',
            'verdict': 'supported', 'central_to_claim': True}],
        'strengths': ['The paragraph offers a focused interpretation.'],
        'revision_moves': ['Explain why this detail matters to the claim.', 'Clarify the limit of the inference.'],
        'limitations': ['Synthetic fixture; not a teacher judgment.'],
        'next_question': 'How does this particular detail support your claim?',
    }
