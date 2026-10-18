---
title: EssayGrader Experimental Model
sdk: docker
app_port: 7860
---

Experimental Qwen2.5-1.5B inference server. No adapter is bundled. Without
ADAPTER_PATH it serves the original base instruction model, not a trained grader.
The previous adapter has not demonstrated reliable grading accuracy.

Create a Hugging Face Docker Space with CPU Basic hardware and copy this
directory's files into its root. This uses free CPU hardware; inference is slow
and the space may sleep. An end-to-end model run has not yet been verified.
Do not select paid hardware unless you intend to pay for it.

In Space Settings, add a secret MODEL_SERVER_KEY with a random value of at
least 32 characters. Generate one locally with
`python -c 'import secrets; print(secrets.token_urlsafe(32))'`.
Do not commit this secret or put it in the Dockerfile.

To load the trained adapter, upload adapter_config.json and
adapter_model.safetensors to an adapter directory, then set ADAPTER_PATH to
/app/adapter. A public Space exposes repository files: use a private Space for
weights you do not intend to publish. Supply both adapter files before enabling
this setting. The base-model revision must match the adapter's training run.

After the Space starts, check https://YOUR-SPACE.hf.space/health. On the existing
Render website service, set these environment variables and redeploy:

```
OPEN_MODEL_BASE_URL=https://YOUR-SPACE.hf.space/v1
OPEN_MODEL_NAME=essaygrader-experimental
OPEN_MODEL_API_KEY=<the same MODEL_SERVER_KEY secret>
```

The website already reads these settings. With OPEN_MODEL_API_KEY configured,
users can leave the model server key field blank. Keep this key on the servers.
This makes the website's public AI routes available to visitors using your
compute; restrict website access before using paid hosting.

Select Open model / fine-tuned adapter in the website. Check a short real
request before trying an essay. CPU responses may exceed the website's
90-second model timeout; this free setup is for testing and does not promise
interactive grading latency. Use a faster inference host for regular service.
