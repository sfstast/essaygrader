"""Opt-in GPU training on approved examples. Preflight never downloads weights."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from urllib.request import urlopen

from model_work.data import messages_for, read_examples, split_examples


def preflight(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    splits = {name:read_examples(directory / f'{name}.jsonl',allow_demo=True) for name in ('train','validation','test')}
    records = [r for rows in splits.values() for r in rows]
    if len(set(r.id for r in records)) != len(records):
        raise ValueError('Duplicate record IDs cross dataset splits.')
    expected = split_examples(records)
    for name, rows in splits.items():
        digest = hashlib.sha256((directory / f'{name}.jsonl').read_bytes()).hexdigest()
        if digest != manifest.get('split_sha256', {}).get(name):
            raise ValueError('A split changed after preparation; review and prepare a new dataset version.')
        ids = sorted(r.id for r in rows)
        if ids != sorted(manifest['splits'][name]) or ids != sorted(r.id for r in expected[name]):
            raise ValueError('Dataset splits do not match the leakage-protected manifest.')
    demo = manifest.get('demo_only', True) or any(r.provenance != 'teacher_reviewed' for r in records)
    commercial = all(r.commercial_use_allowed for r in records)
    summary = {'training_performed':False, 'demo_only':demo, 'commercial_use_permissions_confirmed':commercial, 'examples':{k:len(v) for k,v in splits.items()},
               'data_eligible_for_training':not demo and commercial, 'test_used_for_training':False,
               'dependencies_present':{name:importlib.util.find_spec(name) is not None for name in ('torch','transformers','peft','accelerate')}}
    return summary, splits


def tokenize_example(tokenizer, messages, max_length):
    prompt = tokenizer.apply_chat_template(messages[:-1],tokenize=True,add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=False)
    if full[:len(prompt)] != prompt:
        raise ValueError('Chat template does not preserve the prompt prefix; refusing incorrect label masking.')
    if len(full) > max_length:
        raise ValueError('An example exceeds max_length. Shorten/review it or increase the length; nothing is silently truncated.')
    if len(full) <= len(prompt):
        raise ValueError('An example has no supervised assistant tokens.')
    return {'input_ids':full, 'attention_mask':[1]*len(full), 'labels':[-100]*len(prompt)+full[len(prompt):]}


def train(args, summary, splits):
    if summary['demo_only']:
        raise ValueError('Synthetic demo data cannot train a production adapter. Collect teacher-reviewed examples first.')
    if not summary.get('commercial_use_permissions_confirmed'):
        raise ValueError('Commercial training requires explicit commercial-use permission for every writing, source, score and feedback record.')
    if args.model not in ('Qwen/Qwen2.5-1.5B-Instruct','Qwen/Qwen2.5-7B-Instruct'):
        raise ValueError('This recipe supports the Qwen2.5 1.5B and 7B Instruct architectures; GPU execution remains unverified here. Nemotron Ultra requires NVIDIA’s architecture-specific multi-GPU recipe.')
    if not args.model or not args.revision or not re.fullmatch(r'[a-fA-F0-9]{40}',args.revision):
        raise ValueError('Supply a licensed model ID and a pinned 40-character Hugging Face commit revision.')
    missing = [k for k,v in summary['dependencies_present'].items() if not v]
    if missing:
        raise ValueError('Training dependencies are missing; install requirements-training.txt on a GPU worker.')
    import torch
    if not torch.cuda.is_available():
        raise ValueError('GPU training requires a CUDA worker; no model has been downloaded.')
    # Verify the actual pinned model-card and weight-license files, not the
    # framework's code license. Refuse missing/ambiguous commercial eligibility.
    license_url=f'https://huggingface.co/{args.model}/raw/{args.revision}/LICENSE'
    card_url=f'https://huggingface.co/{args.model}/raw/{args.revision}/README.md'
    try:
        with urlopen(license_url,timeout=30) as response: license_bytes=response.read()
        with urlopen(card_url,timeout=30) as response: card_text=response.read().decode()
    except OSError:
        raise ValueError('Cannot verify the pinned model weight license. No model weights were downloaded.') from None
    if not re.search(r'^license:\s*apache-2\.0\s*$',card_text,re.MULTILINE) or not re.search(r'Apache License.*?Version 2\.0',license_bytes.decode(),re.DOTALL):
        raise ValueError('The pinned Qwen weights do not have the expected Apache-2.0 declaration; stop for license review.')
    license_evidence={'model_weight_license':'Apache-2.0','license_url':license_url,
                      'license_sha256':hashlib.sha256(license_bytes).hexdigest()}
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments
    output = Path(args.out)
    if output.exists():
        raise ValueError('Choose a new output directory; existing adapters will not be overwritten.')
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(args.model,revision=args.revision,trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    # Fail on oversized examples before loading expensive model weights.
    if summary.get('auxiliary_annotations'):
        from model_work.openstax_annotations import messages as annotation_messages
        training_messages = annotation_messages
    else:
        training_messages = lambda row: messages_for(row,True)
    datasets = {name:[tokenize_example(tokenizer,training_messages(row),args.max_length) for row in splits[name]]
                for name in ('train','validation')}
    options = {'revision':args.revision,'trust_remote_code':False,'torch_dtype':dtype}
    if args.qlora:
        options['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype)
        options['device_map'] = {'':torch.cuda.current_device()}
    model = AutoModelForCausalLM.from_pretrained(args.model,**options)
    if args.qlora:
        model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False
    model = get_peft_model(model,LoraConfig(r=16,lora_alpha=32,lora_dropout=.05,
        target_modules=['q_proj','k_proj','v_proj','o_proj'],bias='none',task_type='CAUSAL_LM'))
    def collate(rows):
        length = max(len(r['input_ids']) for r in rows)
        return {key:torch.tensor([r[key]+[pad]*(length-len(r[key])) for r in rows])
                for key,pad in (('input_ids',tokenizer.pad_token_id),('attention_mask',0),('labels',-100))}
    arguments = TrainingArguments(output_dir=str(output),num_train_epochs=args.epochs,
        per_device_train_batch_size=1,per_device_eval_batch_size=1,gradient_accumulation_steps=8,
        learning_rate=2e-4,gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False},
        bf16=dtype==torch.bfloat16,fp16=dtype==torch.float16,eval_strategy='epoch',save_strategy='epoch',
        load_best_model_at_end=True,save_total_limit=2,report_to=[],seed=42,data_seed=42,logging_steps=10)
    trainer = Trainer(model=model,args=arguments,train_dataset=datasets['train'],eval_dataset=datasets['validation'],
                      data_collator=collate,processing_class=tokenizer)
    trainer.train()
    trainer.save_model(str(output/'adapter'))
    tokenizer.save_pretrained(str(output/'adapter'))
    (output/'training-summary.json').write_text(json.dumps({**summary,'training_performed':True,
        'model':args.model,'revision':args.revision,'max_length':args.max_length,'qlora':args.qlora,**license_evidence,
        'evaluation_required':'Evaluate on the untouched test split and perform independent teacher review before deployment.'},indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',required=True)
    parser.add_argument('--annotations',action='store_true',help='Use published editorial commentary as an auxiliary task, never numeric grade labels.')
    parser.add_argument('--train',action='store_true',help='Explicitly enable downloads and GPU training; otherwise preflight only.')
    parser.add_argument('--model')
    parser.add_argument('--revision')
    parser.add_argument('--out',default='model_work/adapters/writing-v1')
    parser.add_argument('--max-length',type=int,default=2048)
    parser.add_argument('--epochs',type=int,default=3)
    parser.add_argument('--qlora',action='store_true')
    args = parser.parse_args()
    try:
        if args.max_length < 128 or not 1 <= args.epochs <= 10:
            raise ValueError('Use max-length >=128 and 1–10 epochs.')
        if args.annotations:
            from model_work.openstax_annotations import preflight as annotation_preflight
            summary,splits = annotation_preflight(args.prepared)
        else:
            summary,splits = preflight(args.prepared)
        if args.train:
            train(args,summary,splits)
        else:
            print(json.dumps(summary,indent=2))
    except (ValueError,OSError,KeyError) as exc:
        parser.exit(2,str(exc)+'\n')


if __name__ == '__main__':
    main()
