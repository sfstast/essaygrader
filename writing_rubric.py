"""User-supplied six-category rubric, transcribed from the uploaded image."""
import json
from pydantic import BaseModel, ConfigDict, Field, StrictInt

RUBRIC_ID = 'user_analytical_writing_1_to_4_v1'
CRITERIA = {
    'thesis': ('Thesis', 'Responds to prompt with specificity; is arguable and insightful; contains an interesting "so what" or makes space for a concluding "so what?"'),
    'evidence': ('Evidence', 'Allows for inference and discussion of language; aligns with your argument and moves it forward; represents logical and rich selection that sufficiently supports the thesis'),
    'organization': ('Organization', 'Introduction and conclusion provide a frame for the argument; has clear and focused topic sentences and sub-arguments that support and develop the idea presented in the thesis; uses effective transitions between ideas and paragraphs; uses concluding sentences that effectively pull the paragraph together; shows deliberate organization of paragraphs and evidence within paragraphs'),
    'analysis': ('Analysis', 'Supports and/or advances the argument; features intentional examination of language and techniques; offers valid and insightful interpretation; avoids plot summary, paraphrasing, and repetition'),
    'control_of_language': ('Control of language', 'Establishes appropriate academic voice; uses precise word choice and varied sentence types; contextualizes and elegantly incorporates quotations'),
    'mechanics_conventions': ('Mechanics/conventions', 'Avoids spelling, punctuation, and grammatical errors; formats MLA/parenthetical correctly; avoids mechanical errors'),
}
LEVELS = {4:'Exemplary', 3:'Proficient', 2:'Emerging', 1:'Beginning'}

class RubricScores(BaseModel):
    model_config = ConfigDict(extra='forbid')
    thesis: StrictInt = Field(ge=1, le=4)
    evidence: StrictInt = Field(ge=1, le=4)
    organization: StrictInt = Field(ge=1, le=4)
    analysis: StrictInt = Field(ge=1, le=4)
    control_of_language: StrictInt = Field(ge=1, le=4)
    mechanics_conventions: StrictInt = Field(ge=1, le=4)


def rubric_text():
    return ('User-provided rubric: '+RUBRIC_ID+'\n'
            +'\n'.join(label+': '+description for label,description in CRITERIA.values())
            +'\nScale for each category: '+json.dumps(LEVELS)
            +'\nThe image supplies category descriptions and level names, not separate descriptors for each level. '
            'Do not claim additional level descriptors were supplied. Score categories independently. '
            'Adapt expectations to the selected grade and assignment scope; for a single paragraph, assess '
            'its opening, progression and closure rather than demanding a whole-essay introduction/conclusion. '
            'Do not penalize missing MLA details that the assignment does not require or that cannot be checked. '
            'Polished mechanics must not raise the analysis score. Do not infer teacher scores from an overall grade.')
