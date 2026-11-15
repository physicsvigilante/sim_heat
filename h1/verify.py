"""Explicit prepare/check CLI; never invokes a compiler or installs packages."""
import argparse
import json
from pathlib import Path
import sys

from . import reference
from .model import Refusal
from .study import load_study, strict_json
from .verification import bind_reference, check_candidate


def read_bounded(path, limit):
    p = Path(path)
    if not p.is_file() or p.stat().st_size > limit or any(q.is_symlink() for q in (p, *p.parents)):
        raise ValueError('missing/oversized input or symlink')
    return p.read_bytes().decode('utf-8')  # Preserve CRLF/LF for raw-artifact hashes.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('prepare', 'check'):
        p = sub.add_parser(action)
        p.add_argument('--study', required=True); p.add_argument('--root', required=True)
        if action == 'prepare':
            p.add_argument('--reference', required=True); p.add_argument('--out', required=True)
        else:
            p.add_argument('--bundle', required=True); p.add_argument('--seal', required=True)
            p.add_argument('--csv', required=True); p.add_argument('--receipt', required=True)
    args = parser.parse_args(argv)
    try:
        study = load_study(Path(args.study), Path(args.root))
        if args.action == 'prepare':
            if not study.request_report['admitted']:
                raise ValueError('study has refused observation requests')
            spec = reference.read_reference(args.reference)
            bind_reference(study, spec)
            bundle = reference.prepare(spec)
            # Explicit artifact write only, never overwrite retained evidence.
            with Path(args.out).open('x', encoding='utf-8') as output:
                output.write(json.dumps(bundle, sort_keys=True, indent=2, allow_nan=False)+'\n')
            print(json.dumps({'stage': 'reference_preparation', 'seal': bundle['seal'],
                              'path': args.out, 'nativeQualified': False, 'nativeExecuted': False}))
            return 0
        bundle = strict_json(read_bounded(args.bundle, 100*1024*1024))
        receipt = strict_json(read_bounded(args.receipt, 16384))
        csv = read_bounded(args.csv, 20*1024*1024)
        result = check_candidate(study, bundle, csv, receipt, args.seal)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result['status'] == 'checks_passed' else 3
    except (Refusal, reference.ReferenceError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'stage': 'offline_verification', 'status': 'refused', 'reason': str(exc),
                          'nativeQualified': False, 'nativeExecuted': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
