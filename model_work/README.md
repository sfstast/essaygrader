# Writing-model development

This is an evaluation and teacher-data collection workflow, **not an already trained or validated writing model**. No real teacher-scored dataset, CUDA GPU or inference credentials were supplied during implementation. A synthetic pipeline check and mocked API/browser tests do not establish grading or tutoring quality.

Commercial use is now required. Read [COMMERCIAL_USE.md](COMMERCIAL_USE.md) for the data-license audit, the completed human argument-quality experiment, and the source-grounded analytical rubric. The CPU candidate did not beat the longer-argument baseline and was not promoted. It is not a teacher-calibrated grader.

## Model choices

- Claude Haiku 4.5 is the existing baseline.
- `Qwen/Qwen2.5-7B-Instruct` is a much smaller open-weight baseline and the supported target for this LoRA script. Check its exact model card, weight license and revision before downloading or training. The GPU script verifies the pinned Apache-2.0 weight-license declaration and refuses missing commercial-use data permissions. An OpenAI-compatible server such as vLLM can serve it or its adapter.
- NVIDIA's [official model repository](https://github.com/NVIDIA-NeMo/Nemotron) and [Ultra usage guide](https://github.com/NVIDIA-NeMo/Nemotron/tree/main/usage-cookbook/Nemotron-3-Ultra) identify Nemotron 3 Ultra as a 550B-total / 55B-active model. Its hosted NVIDIA model ID is `nvidia/nemotron-3-ultra-550b-a55b`. It is an optional benchmark comparator, not this machine's local training target. Its architecture-specific, multi-GPU training recipes are linked from the official guide. Do not apply the small Qwen LoRA configuration to Ultra.

Model IDs, access, licenses and provider availability can change. Nothing here establishes live access or quality for any model.

## 1. Collect reviewed examples

In the app, expand **Teacher instructions & grading criteria** and choose **Download teacher review template**. This exports the current assignment locally with blank teacher scores; it does not collect data on the server and never copies AI feedback into teacher labels. Alternatively, use `templates/teacher-review.json`.

Use stable anonymous student and assignment IDs, not names or contact details. Keep any re-identification key outside this repository. Remove personal information from the source, writing and feedback. Confirm appropriate permission before marking `permission_to_use` and `anonymized` true. Commercial fine-tuning additionally requires `commercial_use_allowed: true` for every record, covering the writing, source, ratings and feedback. Those flags are a required declaration, not an automatic anonymization check.

For a grading record:

- Include the actual source, analytical question, grade, class and teacher rubric with explicit 1–10 score anchors. Unsupported grade/class names are rejected.
- Have **two teachers score independently** before seeing model outputs. Enter pseudonymous rater IDs and integer scores from 1 to 10. Null template scores are not accepted.
- Adjudicate disagreements and write specific, teacher-reviewed feedback. Keep authentic variation in quality and writing style; do not only collect strong work.
- Use `task: "grade"`, `provenance: "teacher_reviewed"`. Never relabel model-generated or synthetic scores as teacher judgments.

For tutoring, create a separate `task: "tutor"` record with the same assignment context, a real `student_message`, and a teacher-written hint/follow-up question in `teacher_feedback`. `teacher_scores` can be empty. The target should help the student reason, not give them a finished paragraph. Share the same anonymous IDs across a student's related records.

An optional `subgroup` can represent a voluntarily and appropriately collected evaluation group. Do not infer sensitive traits from prose. Leave it `unspecified` when not available. Subgroup metrics and small samples do not establish fairness.

Save completed JSON files in ignored `model_work/data/reviews/`, then run:

```sh
python -m model_work.cli collect --reviews model_work/data/reviews --out model_work/data/reviews.jsonl
python -m model_work.cli validate --data model_work/data/reviews.jsonl
python -m model_work.cli prepare --data model_work/data/reviews.jsonl --out model_work/prepared/v1
```

Raw data, prepared splits, results and adapters are ignored by Git. They still contain private writing and need appropriate storage/access controls. Do not commit them or post them in chat. The collector and preparer refuse to overwrite existing outputs.

## 2. Preserve an independent test set

Preparation groups connected student IDs, assignment IDs, normalized sources and duplicate paragraphs. Entire components go into deterministic roughly 60/20/20 train/validation/test splits. There must be at least three independent components. A student connected to several assignments ties those assignments together; a tightly connected class may need new cohorts or assignments to form a real holdout. The program fails instead of weakening that protection.

`manifest.json` records the policy, source-file hash, individual split hashes and split IDs. Changing a split after preparation fails the training preflight. Test labels are not exported as training-message files. Use validation for prompt/model choices, then freeze those choices and evaluate the test set once. Repeatedly tuning against test results invalidates the holdout. More records and independent teachers/assignments are needed before making performance claims; this tool does not declare a minimum tiny sample "good enough."

## 3. Compare models before training

Copy `models.example.json` to a local configuration. It enables Claude and the smaller open model; Ultra is disabled until you have provider access and choose to include its cost. Config files contain **environment variable names**, never keys.

- Claude reads `ANTHROPIC_API_KEY`.
- NVIDIA reads `NVIDIA_API_KEY` and uses `https://integrate.api.nvidia.com/v1`.
- A smaller/self-hosted model reads `OPEN_MODEL_API_KEY` and `OPEN_MODEL_BASE_URL`, for example `http://localhost:8001/v1` on the same trusted machine. The endpoint must use HTTPS except for loopback development. Set `OPEN_MODEL_NAME` to change the app's default open-model name. Configure endpoints on the server, never through public form inputs.

Set credentials using your hosting/environment secret settings, not source files or command arguments. UI manual keys are isolated by provider, cleared when switching provider, and are never stored in browser storage. The site uses `X-Model-Key`; the old Anthropic-specific header works only for Claude. Provider redirects are not followed.

Run a no-call check first:

```sh
python -m model_work.cli benchmark --data model_work/prepared/v1/validation.jsonl --out model_work/runs/plan-v1 --dry-run --injection-check
```

Then, after data review, model access and network setup, run actual inference:

```sh
python -m model_work.cli benchmark --data model_work/prepared/v1/validation.jsonl --out model_work/runs/baselines-v1 --repeats 3 --injection-check
```

The live command makes paid/provider requests. It reports planned calls, records failures separately, and exits unsuccessfully if any model call fails. A dry run reports no accuracy metrics and performs no inference. All-failed runs have null metrics, not zero error.

Grading metrics: mean absolute error against the median teacher score, within-one agreement, signed bias, repeat score variation, per-grade/per-subgroup breakdowns, teacher disagreement, latency and paired score changes under one embedded scoring-instruction attack. There is no automatic model recommendation or deployment threshold. Costs are left unknown rather than invented. The attack check covers one explicit attack; it does not certify prompt-injection resistance. Incomplete coverage and differing samples must be resolved before comparing models.

Tutoring calls are saved separately for independent teacher review. `tutor_review.json` provides a rating queue for source accuracy, grade appropriateness, useful hints, avoiding rewrites, and subsequent revision improvement. Quality stays `human_review_pending` until people review actual outputs and student revisions. Passing a grading score benchmark is not proof of good tutoring.

## 4. Fine-tune only if the baseline warrants it

Preflight does not download weights or train:

```sh
python -m model_work.train_lora --prepared model_work/prepared/v1
```

On an appropriately sized CUDA GPU worker, review the Qwen model license and pin its actual 40-character Hugging Face revision, then install the separate training requirements and explicitly opt in:

```sh
python -m pip install -r requirements-training.txt
python -m model_work.train_lora --prepared model_work/prepared/v1 --train --model Qwen/Qwen2.5-7B-Instruct --revision ACTUAL_40_CHARACTER_MODEL_COMMIT --qlora --out model_work/adapters/qwen-writing-v1
```

Do not run this on the app's web host. GPU capacity depends on sequence length, batch size, quantization and hardware; this repo makes no verified memory/runtime promise. No GPU training or model download was possible in the development environment. The script and dependencies still need validation on your selected CUDA worker.

The script rejects demo data, checks leakage-protected splits, masks prompt/padding labels and supervises only the teacher response. Grading targets round the teacher median to the nearest integer with halves upward; evaluation uses the unrounded median. It refuses oversized examples instead of silently truncating labels. It uses validation loss for checkpoint selection, not the test set. It saves a LoRA adapter and tokenizer without merging or publishing weights. Only the Qwen baseline architecture is supported by this recipe.

Serve the adapter using your GPU host's supported OpenAI-compatible endpoint. Add that served model ID to a new benchmark configuration and compare base vs adapter on untouched holdout writing, followed by human tutoring review. Keep teacher oversight for consequential grading. Do not auto-promote an adapter just because its training loss decreases.

## Local software checks (no model-quality claims)

```sh
python -m unittest discover -s tests -v
python tests/browser_smoke.py
python -m model_work.cli prepare --data model_work/templates/demo.jsonl --out model_work/prepared/demo-check --allow-demo
python -m model_work.cli benchmark --data model_work/prepared/demo-check/test.jsonl --out model_work/runs/demo-check --dry-run --allow-demo --injection-check
python -m model_work.train_lora --prepared model_work/prepared/demo-check
```

The demo file is invented software test data with invented labels, never real teacher judgments. Preparation and benchmark commands need explicit `--allow-demo`; training rejects it unconditionally. The dry-run report contains null accuracy metrics and `training_performed: false`. Use new output directories for subsequent runs.
