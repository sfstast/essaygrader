# Internet-collected qualitative training data

Collected from OpenStax / Rice University, *Writing Guide with Handbook*, historical CC BY 4.0 release `a6c95528390e3a2936f5bf87c49ac1a4995a0a6e`. Authors: Michelle Bachelor Robinson, Maria Jerskey, featuring Toby Fulwiler; individual student authors remain credited in each source title. The current NC-SA edition is not imported. Historical license evidence is retained with the source and prepared data.

Eleven annotated student sample modules yielded 98 excerpt/comment pairs after conservative omission of 66 pairs containing double quotations. These are original published qualitative editorial annotations. They do not supply the user's 1–4 rubric grades, independent teacher scores, comprehensive source passages, or representative coverage of grade levels. Most are model college writing, so they cannot establish what beginning school writers should score. No synthetic ratings have been mixed in.

Reproduce with new directories:

```sh
python -m model_work.openstax_annotations download --out model_work/data/public/openstax-annotations-source-new
python -m model_work.openstax_annotations prepare --source model_work/data/public/openstax-annotations-source-new --out model_work/prepared/openstax-annotations-new
python -m model_work.train_lora --annotations --prepared model_work/prepared/openstax-annotations-new
```

The last command performs preflight only. Existing prepared artifacts are `model_work/prepared/openstax-annotations-v1`: 53 training, 23 validation, 22 test examples, ten author/essay groups. An author or duplicate excerpt cannot cross splits. Test answers are never exported to training-message files. Training consumes the verified JSONL records, not mutable exported message files. Test data is not passed to the trainer.

On a CUDA worker with `requirements-training.txt`, the opt-in training command is:

```sh
python -m model_work.train_lora --annotations --prepared model_work/prepared/openstax-annotations-new --train --model Qwen/Qwen2.5-7B-Instruct --revision VERIFIED_40_CHARACTER_MODEL_COMMIT --out model_work/adapters/openstax-commentary-new --qlora
```

Replace the revision placeholder with an accessible, verified upstream weight revision. The trainer checks its actual Apache-2.0 license and model card before downloading weights, masks prompt tokens, and rejects overlong records. A missing dependency/GPU/license stops execution. This path has not been GPU-tested here. It trains commentary, not the live grader's structured scoring output, and any eventual adapter requires held-out commentary review and separate numeric-rubric calibration before product use. Retain and provide dataset attribution with any resulting distributed component; do not imply OpenStax endorsement.

The collection and preflight have run; **no LLM weights were updated**. This environment lacks CUDA, training libraries and a verified accessible base-model revision. The existing live grader is unchanged by this auxiliary dataset.
