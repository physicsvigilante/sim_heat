"""Real HTTP Chromium source-only import smoke for original T1 studies; no native tool."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def run(out: Path, receipt_dir: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    http = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{http.server_port}'
    passed, skipped = [], []
    errors = []
    try:
        with sync_playwright() as p:
            executable = shutil.which('google-chrome') or shutil.which('chromium')
            browser = p.chromium.launch(headless=True, executable_path=executable,
                                        args=['--no-sandbox'])
            try:
                for label, viewport in [('S', {'width':1440,'height':980}),
                                        ('T', {'width':390,'height':844})]:
                    path = receipt_dir / (label+'.source-only.json')
                    if not path.exists():
                        skipped.append(label)
                        continue
                    data = path.read_bytes()
                    payload = json.loads(data)
                    page = browser.new_page(viewport=viewport)
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    try:
                        response = page.goto(url+'/viewer/source_preview/', wait_until='networkidle')
                        assert response and response.ok
                        page.locator('#import').set_input_files({'name':label+'.json',
                            'mimeType':'application/json','buffer':data})
                        page.wait_for_function('(expected) => document.querySelector("#graph-title").textContent.includes(expected)', arg=payload['studyId'])
                        assert page.locator('#error').is_hidden(), page.locator('#error').inner_text()
                        assert payload['studyId'] in page.locator('#graph-title').inner_text()
                        assert page.locator('#requests .request').count() == len(payload['requests'])
                        assert page.locator('#requests').inner_text().count('not_computed') == len(payload['requests'])
                        assert page.locator('#identity').inner_text().count('false') >= 3
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        page.screenshot(path=str(out/(label+'-source.png')), full_page=True)
                        altered = json.loads(data)
                        altered['source']['nativeQualified'] = True
                        page.locator('#import').set_input_files({'name':'forged.json',
                            'mimeType':'application/json','buffer':json.dumps(altered).encode()})
                        page.locator('#error').wait_for(state='visible')
                        assert page.locator('#graph g').count() == 0
                        assert page.locator('#requests .request').count() == 0
                        page.screenshot(path=str(out/(label+'-refusal.png')), full_page=True)
                        passed.append(label)
                    finally:
                        page.close()
                assert not errors, errors
            finally:
                browser.close()
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)
    summary = {'actualHttpChromiumPass':passed,'notTestedBecauseAdmissionRefused':skipped,
               'nativeExecuted':False, 'sourceOnly':True}
    (out/'browser-receipt.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--receipts',type=Path,required=True)
    a=p.parse_args()
    run(a.out,a.receipts)
