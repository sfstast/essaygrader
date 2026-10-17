# Reasoning Studio

A lightweight HTML/CSS/JavaScript writing workspace served by FastAPI. Typing, word counts, settings and feedback rendering happen in the browser; only assignment generation and grading make AI requests. No frontend build or JavaScript dependencies are required.

## Run

Use Python 3.12 or newer from the repository directory:

```sh
python -m pip install -r requirements.txt
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Open port 8000 through your host's preview or port forwarding. For local development, open `http://localhost:8000`. Choose a model provider and enter its key in the settings panel. The key stays in the current tab's memory and is sent to the backend over the deployment's HTTPS connection. It is never stored in browser storage or included in feedback downloads. Refreshing clears the current work and manual key. The API does not persist submissions or keys.

Select grade and class, supply or generate assignment material, then submit a paragraph. Only empty fields are generated. Feedback persists while editing and is marked stale when its inputs change.

## Deploy

[Deploy the HTML version on Render](https://render.com/deploy?repo=https://github.com/sfstast/essaygrader) using the included `render.yaml` blueprint. Review the hosting plan in Render before creating the service. No saved API key is required.

The HTML version needs a Python web host (for example Render or Railway); Streamlit Community Cloud runs the earlier `app.py` interface instead. Configure:

- Build: `pip install -r requirements.txt`
- Start: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/health`
- Python: 3.12 or newer

Use HTTPS and allow outbound requests to `api.anthropic.com` for Claude or `integrate.api.nvidia.com` for hosted NVIDIA models. No saved API key is required: each user enters their own. `app.py` is retained for existing Streamlit deployments.

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m playwright install chromium
python tests/browser_smoke.py
```

API and browser tests use mocked Anthropic responses, never a real key or paid requests. Browser tests start their own isolated local server. Live model access must be checked separately with your key.

## Open models, teacher-data collection and tutoring

The HTML app supports Claude, hosted NVIDIA Nemotron, and a server-configured OpenAI-compatible model (including a separately served fine-tuned adapter). Pick the provider in **Your classroom**, enter its key, and select a model available to your account. Switching providers clears the key. A separate writing-tutor panel offers hints and follow-up questions; its effectiveness still needs independent teacher evaluation.

See [the model development guide](model_work/README.md) for teacher-review templates, protected train/validation/test splits, reproducible comparisons, and an opt-in Qwen LoRA/QLoRA recipe. No real training or model-quality benchmark has been completed: there is no teacher-reviewed dataset, GPU, or live inference credential in this environment. Synthetic fixtures only test software behavior.
