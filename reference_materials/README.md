# Claude grading references

The live grader uses `writing_rubric.py` as its scoring authority and loads both
user style comparisons from `model_work/examples/user_style_preferences.json`.
The original percentages are preferences, not six-category teacher labels.
These materials guide prompts; Claude's model weights are not retrained.

The Amplify PDF and the previously extracted 41 samples are absent from this
workspace. The publisher URL returned HTTP 403 on 2026-10-18. No Amplify sample
content is claimed as loaded. After the user supplies the PDF, run:

```
python reference_materials/import_amplify.py /path/to/Student_Work_Collection__Essay_Scoring.pdf
```

The importer requires `pypdf` locally. Review extracted pages against the PDF,
set `extraction_reviewed` to true, and save the reviewed JSON as Render’s secret `AMPLIFY_REFERENCE_JSON`. The importer writes to ignored `reference_materials/private/amplify_pages.json`; do not commit the PDF or its extracted student work. Render reads the secret directly, and the public config exposes only whether references are loaded.
Original scores and commentary remain in page-linked text; do not convert them
to scores under the user's different rubric. Only reviewed references are used.
Bounded page excerpts guide scoring qualitatively, not as independent validation.


A malformed or unreviewed bundle is not used. Until a real reviewed bundle is
provided, the app reports Amplify as not loaded. Merely preparing this importer
does not incorporate publisher content or retrain Claude.
