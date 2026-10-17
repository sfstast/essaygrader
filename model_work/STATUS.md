# Status — October 17, 2026

The user requires commercial use and comprehensive analytical-reasoning assessment. Language-proficiency scoring and crowd convincingness must not be presented as teacher-validated analytical grades.

## Completed

- Found and audited author-published datasets. Excluded NC-licensed ELLIPSE, PERSUADE and argumentative microtexts from commercial training. Removed the exploratory ELLIPSE downloads; no model was trained on them.
- Downloaded/pinned/hash-verified UKPConvArg1 (CC BY 4.0), with original-source attribution. Prepared 11,642 human-judged argument pairs across 16 topics; 2,662 have agreeing high-competence human explanations. Labels are crowdsourced relative preferences, not teacher grades or source-fidelity judgments.
- Actually trained and tested a CPU TF-IDF/logistic argument-quality candidate. Training: 7,355 pairs / 10 topics. Validation: 2,416 / 3. Test: 1,871 / 3. Held-out accuracy: 71.8%; majority baseline: 50.8%; longer-argument baseline: 73.9%. The candidate is rejected for analytical grading and is not wired into the app's grading decisions.
- Added two attributed, commercially licensed human-preference examples, explicitly labeled as not teacher/source-based analytical grades.
- Added an original six-criterion analytical rubric with grade/class calibration, checkable source/student excerpts, evidence-to-claim commentary, complexity limits, and revision questions. Overall grades are computed from criterion scores; missing/fabricated quotation links are rejected. Summary-only, off-task, unsupported central inferences, missing evidence and major misreadings limit grades. These are output/guardrail policies, not validated model accuracy.
- Teacher-review export/collection, split protection, provider selection, tutoring and LoRA preflight remain available. Commercial LoRA requires explicit commercial-use data permissions and a pinned Qwen weight-license check. No copyrighted exam sample or AI-generated label was silently relabeled as commercially licensed teacher data.

Software verification: 36 unit/API/data/rubric tests passed. Chromium desktop/mobile checks passed with mocked provider responses. The saved CPU candidate hash and a persisted prediction were replay-verified. These checks do not establish analytical-grading accuracy.

## Remaining limits

- No commercially cleared, task-matched, teacher-scored source-based analytical-writing dataset has been established in this search. Do not pretend crowd preferences fill that gap.
- No NVIDIA/Qwen/Claude analytical-reasoning inference benchmark or large-model fine-tuning ran. There is no CUDA GPU or inference credential in this environment.
- Hugging Face model-card/weight-license access is blocked. The future Qwen GPU training script checks the actual pinned card/license instead of assuming its framework license applies to weights. NVIDIA model/service terms also need checking for the chosen product; the code does not claim that arbitrary selected weights are commercially cleared.
- The API rubric's semantic judgments, score calibration, grade-level appropriateness and tutoring effectiveness still need independent human validation. Checking whether a quotation exists does not prove its interpretation is correct.
- No public deployment or commercial release is claimed. Hosted provider calls need the user's account/key, network access and appropriate provider terms. The unavailable cloud configuration draft was not changed.

See [COMMERCIAL_USE.md](COMMERCIAL_USE.md), [the real experiment report](reports/argument-quality-commercial-v1.json), and the main README for exact reproduction steps. Private raw data, vocabularies and model artifacts are ignored by Git; only the cleared attributed examples and aggregate results are published.

Additional collection: historical CC-BY OpenStax release, 11 annotated student sample modules, 98 qualitative excerpt/comment pairs (53 train / 23 validation / 22 test). Reproducible collector and auxiliary LoRA path added. No numeric rubric scores invented. Preflight ran; full LLM training remains blocked by missing CUDA/training stack/model access. See OPENSTAX_ANNOTATIONS.md and reports/openstax-annotations-v1.json. The uploaded six-category rubric is separately supported for collecting genuine independent teacher ratings.

Free-GPU notebook: `notebooks/free_gpu_commentary.ipynb` prepares a Qwen2.5-1.5B QLoRA experiment and base-versus-adapter held-out review packet. It requires user Colab sign-in/GPU allocation; no notebook training has executed here. User style comparisons are preserved separately as unverified preferences, not teacher labels. Thoughtful Learning assessment source requested by user is registered but network-blocked; content and commercial-training rights remain unverified and no samples were imported.
