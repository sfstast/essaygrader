"""Server-configured OpenAI-compatible providers. No endpoint comes from user input."""
import os
from urllib.parse import urlsplit

import httpx

NVIDIA_MODEL = 'nvidia/nemotron-3-ultra-550b-a55b'
SMALL_MODEL = 'Qwen/Qwen2.5-7B-Instruct'


class ModelRequestError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def providers():
    return [
        {'id': 'anthropic', 'label': 'Claude', 'model': 'claude-haiku-4-5', 'key_label': 'Anthropic key'},
        {'id': 'nvidia', 'label': 'NVIDIA Nemotron (hosted)', 'model': NVIDIA_MODEL, 'key_label': 'NVIDIA API key'},
        {'id': 'open_model', 'label': 'Open model / fine-tuned adapter',
         'model': os.getenv('OPEN_MODEL_NAME', SMALL_MODEL), 'key_label': 'Model server key',
         'configured': bool(os.getenv('OPEN_MODEL_BASE_URL'))},
    ]


def request_open_text(key, model, system, message, *, provider, max_tokens=4096):
    if provider == 'nvidia':
        base_url = 'https://integrate.api.nvidia.com/v1'
    elif provider == 'open_model':
        base_url = os.getenv('OPEN_MODEL_BASE_URL', '').rstrip('/')
        if not base_url:
            raise ModelRequestError('The site owner needs to configure an open-model server first.', 400)
    else:
        raise ModelRequestError('Choose a supported provider.', 400)
    url = urlsplit(base_url)
    local = url.hostname in ('127.0.0.1', 'localhost', '::1')
    if (url.scheme != 'https' and not (url.scheme == 'http' and local)) or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise ModelRequestError('The model server URL is not configured correctly.', 400)
    try:
        with httpx.Client(timeout=90.0, follow_redirects=False) as client:
            response = client.post(base_url + '/chat/completions', headers={'Authorization': 'Bearer ' + key},
                                   json={'model': model, 'temperature': 0, 'max_tokens': max_tokens,
                                         'messages': [{'role': 'system', 'content': system},
                                                      {'role': 'user', 'content': message}]})
    except httpx.HTTPError:
        raise ModelRequestError('Could not connect to the selected model provider.') from None
    if response.status_code in (401, 403):
        raise ModelRequestError('The provider did not accept this key or model access.', 401)
    if response.status_code == 429:
        raise ModelRequestError('The provider request limit was reached. Try again later.', 429)
    if not response.is_success:
        raise ModelRequestError('The provider could not complete the request. Check model availability.')
    try:
        choice = response.json()['choices'][0]
        if choice.get('finish_reason') == 'length':
            raise ModelRequestError('The response was cut short. Try a shorter passage or a model with more output capacity.')
        text = choice['message']['content']
        if not isinstance(text, str) or not text.strip():
            raise ValueError()
        # Some hosted reasoning models include private thinking in content instead
        # of a separate reasoning field. Never show it as grading or tutoring.
        if text.lstrip().startswith('<think>'):
            if '</think>' not in text:
                raise ValueError()
            text = text.split('</think>', 1)[1]
        if not text.strip():
            raise ValueError()
        return text.strip()
    except (ValueError, TypeError, KeyError, IndexError):
        raise ModelRequestError('The provider returned an empty or unsupported response.') from None
