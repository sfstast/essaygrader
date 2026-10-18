# Reasoning Studio

A lightweight writing workspace served by FastAPI, using bring-your-own-key
Claude for assignment generation, rubric ratings and tutoring. The website no
longer offers Nemotron or an open-model/LoRA provider. Historical model research
and notebooks are retained as archives, not active website providers.

## Run and deploy

Use Python 3.12 or newer:

```
python -m pip install -r requirements.txt
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

[Deploy on Render](https://render.com/deploy?repo=https://github.com/sfstast/essaygrader)
using `render.yaml`. The existing service uses `pip install -r requirements.txt`,
`uvicorn server:app --host 0.0.0.0 --port $PORT`, and `/api/health`.
Only outbound Anthropic access is required; no Colab or model server is needed.
The user enters an Anthropic API key. It stays in the tab's memory, is sent over
HTTPS for AI requests, and is not saved in browser storage or feedback exports.
The backend does not persist submissions or keys. Refreshing clears the work.
An optional server-side `ANTHROPIC_API_KEY` is supported for private deployments;
restrict access before enabling shared paid API usage on a public site.

## Claude models and consumption

The efficient default routes grading to **Sonnet 5.5** and practice/tutoring to
**Haiku 5.5**. Users can choose Haiku for all tasks, Sonnet for all tasks, optional
Opus 5.5 for deeper review, or the former Haiku 4.5 for compatibility. These are
recommendations from Anthropic's published lineup, not a measured essay-grading
ranking. Account access and live model behavior still need verification with a
real Anthropic key. All API usage is billed to that key.

The stable rubric prompt uses an explicit five-minute prompt-cache breakpoint.
Cache hits depend on repeated identical prefixes within Anthropic's cache rules;
initial cache writes carry overhead, so savings are not guaranteed on isolated
requests. Structured outputs enforce the response shape without duplicating its
JSON schema in the prompt. The grading API makes one model request and does not
silently repair semantic failures with another paid call. Feedback is concise,
with at most two evidence checks and two revision steps. Output budgets are
2,048 tokens for generation, 4,096 for rubric assessment (including any thinking),
and 768 for tutoring. Effort is low for generation/tutoring and medium for grading.
Budgets are ceilings, not predicted usage. Actual grading token counts, including
cache reads/writes, are returned and displayed when available.

Repeated clicks reuse the current feedback until writing or settings change.
Tutor context is limited to four turns with 1,800 characters per turn. Source
text is not silently truncated. Generation preserves existing fields and retries
at most once if a passage is below its grade-appropriate minimum length.

Official sources checked on 2026-10-18:

- [Models and IDs](https://platform.claude.com/docs/en/models/overview)
- [Haiku](https://platform.claude.com/docs/en/models/haiku-5-5/overview)
- [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Effort](https://platform.claude.com/docs/en/build-with-claude/effort)
- [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)

## Rubric and reference materials

The live grader uses the uploaded rubric transcribed in `writing_rubric.py`:
thesis, evidence, organization, analysis, control of language and
mechanics/conventions. Each category uses 1 Beginning through 4 Exemplary.
The user did not supply weights or an overall conversion, so the site does not
invent a percentage, 1–10 score, or total. Explanations are scope- and grade-aware.
Quotation-presence checks reject invented source/student quotations. Semantic
checks reject evidence credit without a source link and summary-only writing
scored as developed analysis. These checks do not establish teacher calibration.

Both user-supplied style comparisons guide the prompt. Their percentages are
preferences, not six-category teacher labels. Strong prose cannot substitute for
evidence or reasoning, and narrative imagery is not mandatory in analysis.

**Amplify is not loaded:** the original PDF/extractions are missing here and the
publisher download returns HTTP 403. The page-linked import path is prepared;
see [reference material instructions](reference_materials/README.md). Native
publisher scores will remain separate from the user's rubric. Prompt guidance
is not Claude fine-tuning, and no independently validated custom grader is claimed.

## Checks

```
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m playwright install chromium
python tests/browser_smoke.py
```

Checks mock API responses; they verify software, schema, textual grounding,
provider removal and interface behavior, not real grading accuracy. `app.py` is
an archived Streamlit interface. The deployed product is `server.py` and `static/`.
