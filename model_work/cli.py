"""Run with python -m model_work.cli; no remote calls unless benchmark is live."""
import argparse
import json
from model_work.data import collect_reviews, prepare, read_examples
from model_work.evaluate import benchmark


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('validate','prepare','benchmark'):
        child = commands.add_parser(name)
        child.add_argument('--data', required=True)
        child.add_argument('--allow-demo', action='store_true')
        if name != 'validate':
            child.add_argument('--out', required=True)
        if name == 'benchmark':
            child.add_argument('--models', default='model_work/models.example.json')
            child.add_argument('--repeats', type=int, default=3)
            child.add_argument('--dry-run', action='store_true')
            child.add_argument('--injection-check', action='store_true')
    collect = commands.add_parser('collect')
    collect.add_argument('--reviews',required=True)
    collect.add_argument('--out',required=True)
    args = parser.parse_args()
    try:
        if args.command == 'collect':
            result = collect_reviews(args.reviews,args.out)
        elif args.command == 'validate':
            rows = read_examples(args.data,allow_demo=args.allow_demo)
            result = {'valid_examples':len(rows), 'demo_only':any(r.provenance=='synthetic_demo' for r in rows)}
        elif args.command == 'prepare':
            result = prepare(args.data,args.out,allow_demo=args.allow_demo)
        else:
            result = benchmark(args.data,args.models,args.out,allow_demo=args.allow_demo,
                               dry_run=args.dry_run,repeats=args.repeats,injection_check=args.injection_check)
        print(json.dumps(result,indent=2))
        if args.command == 'benchmark' and not args.dry_run and any(
                not m['metrics']['complete'] or m['tutor_failed_calls'] for m in result['models'].values()):
            parser.exit(1,'Some model calls failed; inspect the report. This is not a completed benchmark.\n')
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc)+'\n')


if __name__ == '__main__':
    main()
