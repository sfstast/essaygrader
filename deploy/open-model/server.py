"""Private, single-request OpenAI-compatible inference endpoint."""
import os
import secrets
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

MODEL_ID = 'Qwen/Qwen2.5-1.5B-Instruct'
MODEL_REVISION = '989aa7980e4cf806f80c7fef2b1adb7bc71aa306'
lock = threading.Lock()
state = {}


@asynccontextmanager
async def lifespan(app):
    if len(os.environ.get('MODEL_SERVER_KEY', '')) < 32:
        raise RuntimeError('Set MODEL_SERVER_KEY to a random secret of at least 32 characters.')
    import torch
    torch.set_num_threads(int(os.environ.get('MODEL_CPU_THREADS', '2')))
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, torch_dtype=torch.float32,
        low_cpu_mem_usage=True)
    adapter = os.environ.get('ADAPTER_PATH')
    if os.environ.get('ADAPTER_REPO'):
        from huggingface_hub import snapshot_download
        adapter = snapshot_download(os.environ['ADAPTER_REPO'],
                                    allow_patterns=['adapter_config.json', 'adapter_model.safetensors'])
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    state.update(model=model, tokenizer=tokenizer)
    yield
    state.clear()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


def authorize(authorization: str = Header(default='')):
    expected = 'Bearer ' + os.environ.get('MODEL_SERVER_KEY', '')
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(401, 'Invalid model server key.')


class Message(BaseModel):
    role: str = Field(pattern='^(system|user|assistant)$')
    content: str = Field(max_length=100000)


class Completion(BaseModel):
    model: str
    messages: list[Message] = Field(min_length=1, max_length=20)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0, ge=0, le=2)


@app.get('/health')
def health():
    return {'status': 'ok' if state else 'loading',
            'adapter_loaded': bool(os.environ.get('ADAPTER_PATH') or os.environ.get('ADAPTER_REPO'))}


@app.post('/v1/chat/completions', dependencies=[Depends(authorize)])
def completion(body: Completion):
    if body.model != os.environ.get('SERVED_MODEL_NAME', 'essaygrader-experimental'):
        raise HTTPException(400, 'Unknown model.')
    if not lock.acquire(blocking=False):
        raise HTTPException(429, 'Model busy; try again shortly.')
    try:
        import torch
        tokenizer = state['tokenizer']
        tokens = tokenizer.apply_chat_template(
            [m.model_dump() for m in body.messages], tokenize=True,
            add_generation_prompt=True, return_tensors='pt')
        if tokens.shape[-1] + body.max_tokens > 8192:
            raise HTTPException(400, 'Input is too long; shorten the writing or source.')
        with torch.inference_mode():
            output = state['model'].generate(
                tokens, attention_mask=torch.ones_like(tokens),
                max_new_tokens=body.max_tokens, do_sample=False,
                pad_token_id=tokenizer.eos_token_id)
        generated = output[0, tokens.shape[-1]:]
        finished = generated[-1].item() == tokenizer.eos_token_id
        return {'choices': [{'index': 0, 'message': {
            'role': 'assistant', 'content': tokenizer.decode(generated, skip_special_tokens=True)},
            'finish_reason': 'stop' if finished else 'length'}]}
    finally:
        lock.release()
