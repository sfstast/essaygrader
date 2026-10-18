"""Claude choices verified against Anthropic's model overview on 2026-10-18."""
MODEL_DOCS = 'https://platform.claude.com/docs/en/models/overview'
MODELS = [
    {'id': 'auto', 'label': 'Efficient default: Sonnet grading · Haiku practice & tutoring'},
    {'id': 'claude-haiku-5-5', 'label': 'Haiku 5.5 · lowest-cost option for all tasks'},
    {'id': 'claude-sonnet-5-5', 'label': 'Sonnet 5.5 · balanced cost and speed'},
    {'id': 'claude-opus-5-5', 'label': 'Opus 5.5 · deeper review, higher cost'},
    {'id': 'claude-haiku-4-5', 'label': 'Haiku 4.5 · previous model, lower-cost option'},
]
DEFAULT_MODEL = 'auto'


def task_model(selected, task):
    if selected == 'auto':
        return 'claude-sonnet-5-5' if task == 'grade' else 'claude-haiku-5-5'
    if selected not in {row['id'] for row in MODELS}:
        raise ValueError('Choose one of the available Claude models.')
    return selected
