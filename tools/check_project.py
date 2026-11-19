"""One-command OFFLINE product health checks. Never installs or invokes OpenModelica.

Run from any working directory. Optional archive replay reads saved data only.
The optional browser checks need an already installed Chromium/Playwright.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New outside-repository evidence directory')
    parser.add_argument('--archives', type=Path, help='Directory of the five original artifact-ID ZIP files')
    parser.add_argument('--browser', action='store_true', help='Run real HTTP Chromium smoke tests')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.is_relative_to(ROOT) or out.exists():
        parser.error('--out must be a NEW directory outside the source repository')
    out.mkdir(parents=True)
    py = [sys.executable, '-B']
    suites = [
        ('h1', py+['-m','unittest','discover','-s','h1/tests','-v']),
        ('analytical', py+['-m','unittest','discover','-s','experiments/h1_spike/checks','-v']),
        ('adapters', py+['-m','unittest','discover','-s','viewer/network/tests','-p','test_*.py','-v']),
        ('product', py+['-m','unittest','discover','-s','tests','-p','test_*.py','-v']),
        ('javascript', ['node','--test']+[str(p.relative_to(ROOT)) for pattern in (
            'viewer/tests/*.test.mjs','viewer/network/tests/*.test.mjs',
            'viewer/source_preview/*.test.mjs') for p in sorted(ROOT.glob(pattern))]),
        ('docs', py+['tools/render_product_docs.py','--check']),
    ]
    if args.archives:
        suites.append(('archive-replay', py+['viewer/network/tools/replay_published_archives.py',
                                            '--archives',str(args.archives.resolve())]))
    if args.browser:
        for name, script in (
            ('browser-workbench','tests/browser_authoring_workbench.py'),
            ('browser-explorer','viewer/network/tests/browser_smoke.py'),
            ('browser-preview','tests/browser_source_preview.py'),
            ('browser-docs','tests/browser_product_docs.py'),
        ):
            suites.append((name, py+[script,'--out',str(out/name)]))
    env = os.environ | {'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
    results = []
    for name, command in suites:
        start = time.monotonic()
        record = {'name':name,'command':command}
        with (out/(name+'.log')).open('w', encoding='utf-8') as stream:
            try:
                completed = subprocess.run(command,cwd=ROOT,env=env,stdout=stream,
                                           stderr=subprocess.STDOUT,timeout=240,check=False)
                record['exitCode'] = completed.returncode
            except (OSError,subprocess.TimeoutExpired) as exc:
                record['exitCode'] = None
                record['error'] = repr(exc)
        record['seconds'] = round(time.monotonic()-start,3)
        results.append(record)
        print(name, 'PASS' if record['exitCode']==0 else 'FAILED_OR_BLOCKED',flush=True)
    report = {'schema':'sim_heat.offline_project_health/1','nativeCalls':0,
              'nativeQualificationGranted':False,'browserRequested':args.browser,
              'archiveReplayRequested':bool(args.archives),'checks':results,
              'allRequestedChecksPassed':all(x['exitCode']==0 for x in results)}
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0 if report['allRequestedChecksPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
