# Claude grading references

The live grader uses `writing_rubric.py` as its scoring authority and loads both
user style comparisons from `model_work/examples/user_style_preferences.json`.
The original percentages are preferences, not six-category teacher labels.
These materials guide prompts; Claude's model weights are not retrained.

The user supplied the Amplify Student Work Collection PDF on 2026-10-18.
The private deployment bundle retains teacher pages 1–60: nine mastery essays
and 32 criterion-scored samples (41 distinct examples). Student-facing pages
61–120 repeat the collection and are not counted again. Native publisher scores,
assignment context, commentary, and source PDF page numbers are preserved.
Structural checks cover all indexed examples; visual spot-checks cover pages 2,
47, and 50. No publisher/student text is committed here.

To import a newly supplied PDF, run:

```
python reference_materials/import_amplify.py /path/to/Student_Work_Collection__Essay_Scoring.pdf
```

The importer requires `pypdf` locally. Review extracted pages against the PDF,
set `extraction_reviewed` to true, and save the reviewed JSON as Render’s secret `AMPLIFY_REFERENCE_JSON`, or use `AMPLIFY_REFERENCE_B64` for a base64-encoded zlib-compressed JSON bundle. Compression keeps the reference library within environment-value size limits without dropping the retained pages. The importer writes to ignored `reference_materials/private/amplify_pages.json`; do not commit the PDF or its extracted student work. Render reads the secret directly, and the public config exposes only whether references are loaded.
Original scores and commentary remain in page-linked text; do not convert them
to scores under the user's different rubric. Only reviewed references are used.
The indexed bundle selects a lower/higher evidence example pair for the requested grade (nearest middle-school grade outside grades 6–8), limited to 6,000 excerpt characters per request. Selection is stable within a grade to support prompt caching. The whole private library remains available for selection; not all examples are sent on every request. Page-only imports use a bounded fallback. Amplify word-count cutoffs and narrative Showing requirements do not become user-rubric rules. These examples guide prompts qualitatively; they do not establish independent score calibration or retrain model weights.


A malformed or unreviewed bundle is not used. Without a reviewed bundle, the app reports Amplify as not loaded. Merely preparing this importer
does not incorporate publisher content or retrain Claude.
