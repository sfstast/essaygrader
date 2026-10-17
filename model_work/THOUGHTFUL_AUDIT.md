# Thoughtful Learning data audit

The first Colab run completed QLoRA training on 124 examples. It achieved 18/44 exact matches (40.9%) versus the base model's 14/44 (31.8%). These uploaded results establish an experimental improvement, not reliable student grading. The adapter recognized only 2/11 Poor and 2/12 Good examples.

An offline audit of all 208 saved source pages and index ratings found:

- `iron-summary-okay` is Okay in the source index but Good in the page's description and quality class. It is now quarantined, with both ratings retained in the manifest; neither is silently substituted.
- The four Iron Summary pages contain an original reading selection and a separate student summary. The original importer concatenated both as student prose. This was an importer defect. The corrected importer retains the reading separately and clearly distinguishes it from student writing in the model prompt.
- All 208 index entries have explicit four-level ratings; the one conflict above is excluded. The corrected snapshot contains 207 eligible records: 124 train, 40 validation and 43 test. Related assessment groups and duplicate writing remain isolated across splits.

A comparison of complete model messages confirms training and validation inputs/targets are identical before and after the audit. Only three retained test inputs changed, and one disputed test record was removed. Repeating training solely for this correction is unnecessary; the prior adapter can be retained. Corrected predictions would require rerunning evaluation, not recomputing accuracy from old predictions for changed inputs.

The original downloaded snapshot and Colab results are preserved. The corrected local dataset is under ignored `model_work/prepared/thoughtful-audited-v2`. Data, source HTML and model weights are not committed. The notebook collects a new audited snapshot directly when run.

Regression checks exercise source/student separation, independent index labels, contamination and checksum rejection, and notebook syntax. Corrected GPU training has not executed. Existing test examples have now informed diagnosis; subsequent results on them must be treated as diagnostic. Independent confirmation needs additional unseen, teacher-rated writing, preferably with assignment and author separation and a prespecified rubric. Do not repeatedly tune on these examples and claim an independent accuracy estimate.
