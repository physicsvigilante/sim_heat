"""Read-only CLI: python -B -m h1 STUDY.json --root CASE_ROOT."""
import argparse
import json
from pathlib import Path
from .model import Refusal
from .study import load_study, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = report(load_study(args.study, args.root))
    except (Refusal, OSError, ValueError) as exc:
        result = {'stage': 'offline_validation', 'admitted': False, 'nativeExecuted': False,
                  'code': getattr(exc, 'code', 'input_error'), 'reason': str(exc)}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['admitted'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
