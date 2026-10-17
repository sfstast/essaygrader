# Commercial use and analytical-reasoning scope

The product must assess analytical reasoning and permit commercial use. A dataset being publicly readable does not establish training rights. Code licenses do not establish model-weight or underlying text licenses.

## Data review

| Source | Authors' stated data license | Decision | What the labels actually assess |
|---|---|---|---|
| [UKPConvArg1](https://github.com/UKPLab/acl2016-convincing-arguments) | CC BY 4.0; original CreateDebate arguments CC BY 3.0 and ConvinceMe arguments public domain, as documented by corpus authors | Eligible for commercial reuse with attribution; source and author notices are preserved | Human crowd preferences between arguments, with some human explanations; **not teacher grades** |
| [ELLIPSE](https://github.com/scrosseye/ELLIPSE-Corpus) | CC BY-NC-SA 4.0 | Excluded; exploratory downloads removed; no training performed on them | Language proficiency, not analytical reasoning |
| [PERSUADE 2.0](https://github.com/scrosseye/persuade_corpus_2.0) | CC BY-NC-SA 4.0 | Excluded from commercial training | Argumentative essays and discourse effectiveness |
| [Argumentative microtexts](https://github.com/peldszus/arg-microtexts) | CC BY-NC-SA 4.0 | Excluded from commercial training | Argumentation structures |
| [Cross-rubric critical-thinking research](https://github.com/umass-ml4ed/generalization-in-essay-scoring) | Repository code CC0; underlying dataset permission not established by that code license | Do not import/relabel the underlying essays as commercially licensed | Human critical-thinking rubric labels; LLM-generated traits/justifications must not be called human labels |
| Public exam sample essays/scoring commentaries | No general commercial ML training permission established | Do not scrape them into a commercial training set just because they can be read online | Potentially useful references, but not cleared training data |

UKPConvArg1 was collected from the authors' pinned release, with an archive hash, original human votes, corpus attribution and original-source author links. Neither annotator identifiers nor author profiles are model input. The public repository contains provenance and aggregate metrics, not downloaded student essays or the trained vocabulary. The local artifact is accompanied by its attribution files. Retain and provide appropriate attribution when using or distributing the component and preserve the source notices. Do not describe its labels as schoolteacher assessments.

## What was actually trained

`public_arguments.py` downloads/verifies the pinned CC-BY-4.0 release and prepares its native pair task. `train_argument_quality.py` trains a CPU word/character TF-IDF logistic comparator, selects hyperparameters on validation debate topics and tests on separate debate topics. Argument texts duplicated across splits are removed. Both stances of the same topic stay together. No claim is made that authors are disjoint.

The report is [argument-quality-commercial-v1.json](reports/argument-quality-commercial-v1.json). Its 71.8% held-out pair accuracy is below the 73.9% longer-argument baseline. **The candidate is rejected for analytical grading and is not installed into the live grading route.** This is a useful negative experiment: convincingness and length are not substitutes for source-grounded reasoning.

The private local artifact is `model_work/adapters/argument-quality-commercial-v1/argument-quality.joblib`. Only load joblib artifacts you created/trust; they are executable serialization. Adjacent metadata records the artifact hash, attribution and test results. It is not a foundation model, a teacher-calibrated essay grader or a tutor.

Reproduce without Kaggle credentials or paid inference:

```sh
python -m pip install -r requirements-research-lock.txt
python -m model_work.public_arguments download --out model_work/data/public/convarg-new
python -m model_work.public_arguments prepare --source model_work/data/public/convarg-new --out model_work/data/public/convarg-new/prepared
python -m model_work.train_argument_quality --prepared model_work/data/public/convarg-new/prepared --out model_work/adapters/convarg-new
```

Always use new output directories. Do not tune repeatedly on the reported test set and present the same test as an independent validation. This small 3-topic holdout is not production certification.

## What the app now assesses

`reasoning_assessment.py` contains an original rubric, not copied copyrighted exam samples. It assesses:

1. A defensible claim (15%).
2. A focused answer to the analytical question (10%).
3. Specific, relevant evidence (20%).
4. Faithful source reading (15%).
5. Commentary and evidence-to-claim warrants (30%).
6. A developing line of reasoning (10%).

The model must return scores and explanations for each criterion plus verbatim student/source excerpts, an inference verdict, age-appropriate complexity comments and revision moves. The application verifies quotation presence and computes the overall grade; it refuses fabricated quotations rather than issuing an unsupported grade. Summary/circular inference, serious source misreading, central overclaims, missing evidence and off-task responses limit the grade. Nuance and counterarguments are judged relative to grade/class and task, not mechanically required for young students. Grammar and vocabulary are not scoring dimensions.

**These are rubric and output-contract safeguards, not proof of grading validity.** A quoted sentence can be present but misinterpreted. The model's semantic judgments, individual scores and centrality flags still need task-matched human validation. Published persuasive preferences cannot fill that gap. Unit-test fixtures are explicitly synthetic software fixtures, not teacher-scored training examples. No real provider-backed analytical-reasoning benchmark has run without inference access.

## Model weights and deployment

- The candidate CPU comparator uses our training code and scikit-learn, with the corpus/source attribution conditions above. Its weak result means it is not promoted.
- The intended smaller LLM recipe targets `Qwen/Qwen2.5-7B-Instruct`. A future GPU training run must verify the actual pinned weight LICENSE and model-card `Apache-2.0` declaration; the script fails if it cannot. License verification/download is currently blocked by network access, so this session does not claim that a model revision was verified or fine-tuned.
- Nemotron weights have their own model license; a GitHub repository's Apache code license is not a blanket weight license. Hosted NVIDIA/Anthropic use must comply with the particular service/model terms and account permissions. The UI never labels every arbitrary user-entered model as commercially cleared.
- Teacher-contributed records now need a separate `commercial_use_allowed: true` declaration before the commercial LoRA path accepts them. It must cover writing, source texts, ratings and feedback. Empty exports default to false; no permission is inferred from downloading a file or receiving an API response.
- Large-model tuning still requires a CUDA worker and actual model access. No GPU, inference credentials or purchased compute were supplied; none was fabricated or provisioned as a hidden expense. No public model or product deployment is claimed here.

The working path is a commercially cleared model plus the original analytical rubric, tested against task-matched, commercially permitted human assessments. The current changes prepare and harden that path; they do not claim a finished, commercially validated analytical grader.
