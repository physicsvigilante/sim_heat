"""Actual HTTP Chromium teacher journey for an *unfamiliar composition*, source-only.

No native simulation or result is run; browser imports are display-only and
cannot turn an uncomputed composition into a historical diagnostic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from threading import Thread

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.authoring_workbench import create_server

CASE = ROOT/'experiments/teacher_dual_network'


def run(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    server, admitted = create_server(CASE/'study.json', CASE)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    errors = []
    try:
        with sync_playwright() as playwright:
            executable = shutil.which('google-chrome') or shutil.which('chromium')
            browser = playwright.chromium.launch(headless=True, executable_path=executable,
                                                 args=['--no-sandbox'])
            try:
                page = browser.new_page(viewport={'width':1440,'height':960})
                page.on('pageerror', lambda error: errors.append(str(error)))
                try:
                    response = page.goto(origin+'/', wait_until='domcontentloaded')
                    assert response and response.ok
                    expect(page.locator('#state')).to_contain_text('Admitted source only')
                    expect(page.locator('#graph-title')).to_contain_text('DualNetworkLesson')
                    assert page.locator('#error').is_hidden()
                    assert page.locator('#requests .request').count() == 8
                    assert page.locator('#requests').inner_text().count('not_computed') == 8
                    assert 'nativeExecuted=false' in page.locator('#state').inner_text()
                    assert admitted['source']['modelSha256'] in page.locator('#identity').inner_text()
                    assert 'two disconnected thermal networks' in page.locator('#model-assumptions').inner_text()
                    assert page.locator('#graph g').count() > 0
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    assert page.locator('#open-recorded-diagnostic').count() == 0
                    assert page.locator('#no-published-diagnostic').count() == 0
                    page.locator('#element-select').select_option('component:pairLink')
                    details = page.locator('#details').inner_text()
                    assert 'RodCircular' in details
                    assert 'd (source SI)' in details
                    assert 'illustrative' in details
                    page.screenshot(path=str(out/'dual-network-admitted-source.png'), full_page=True)
                    # Local workbench is a fixed read-only virtual preview,
                    # not a server for this study's underlying .mo / .json.
                    assert page.request.get(origin+'/viewer/network/compare.html').status == 404
                    assert page.request.get(origin+'/viewer/network/data/D2.json').status == 404
                    assert page.request.get(origin+'/experiments/teacher_dual_network/model.mo').status == 404
                    assert page.request.post(origin+'/viewer/source_preview/', data=b'test').status == 405
                    forged = json.loads(json.dumps(admitted))
                    forged['source']['nativeQualified'] = True
                    page.locator('#import').set_input_files({
                        'name':'forged-native-status.json', 'mimeType':'application/json',
                        'buffer':json.dumps(forged).encode('utf-8')})
                    page.locator('#error').wait_for(state='visible')
                    assert page.locator('#graph g').count() == 0
                    assert page.locator('#requests .request').count() == 0
                    assert page.locator('#element-select').is_disabled()
                    assert page.locator('#open-recorded-diagnostic').count() == 0
                    page.screenshot(path=str(out/'dual-network-import-refused.png'), full_page=True)
                finally:
                    page.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert not errors, errors
    print('PASS: developer-authored H1 dual network admitted and inspected in real HTTP Chromium;'
          ' disjoint networks/5 rods/8 uncomputed requests, read-only and forged-native refusal; no OMC.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
