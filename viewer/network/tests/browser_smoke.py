"""Real Chromium read-only H2-02 case switching and refusal smoke.

Runs on localhost only, with no OpenModelica or physics-application actions.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import argparse
import json
import shutil
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

def run(evidence:Path):
    class Static(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,directory=str(ROOT),**kwargs)
        def log_message(self,*args):pass
    http=ThreadingHTTPServer(('127.0.0.1',0),Static)
    thread=Thread(target=http.serve_forever,daemon=True);thread.start()
    chrome=shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
    errors=[];evidence.mkdir(exist_ok=True,parents=True)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'],
              **({'executable_path':chrome} if chrome else {}))
            page=browser.new_page(viewport={'width':1376,'height':940})
            page.on('pageerror',lambda x:errors.append(str(x)))
            page.goto(f'http://127.0.0.1:{http.server_port}/index.html',wait_until='networkidle')
            expect(page.locator('#case-select option')).to_have_count(3)
            expect(page.locator('#graph-count')).to_have_text('2 nodes · 1 rods')
            expect(page.locator('#sample-note')).to_contain_text('21 saved points')
            assert page.locator('#network .node-button').count()==2
            assert page.locator('#network .edge-button').count()==1
            assert page.locator('#reversal').is_disabled()
            assert 'Supplied to network' in page.locator('#energy-readouts').inner_text()
            page.screenshot(path=str(evidence/'D1.png'),full_page=True,animations='disabled')

            page.locator('#case-select').select_option('H1_D2')
            expect(page.locator('#model-id')).to_have_text('H1_D2')
            assert page.locator('#energy-readouts .record-field').count()==3
            assert page.locator('#reversal').is_disabled()
            page.locator('#time-slider').focus();page.keyboard.press('ArrowRight')
            assert page.locator('#time-label').inner_text()=='468.75 s'
            page.screenshot(path=str(evidence/'D2.png'),full_page=True,animations='disabled')

            page.locator('#case-select').select_option('DEV_BRIDGE')
            expect(page.locator('#graph-count')).to_have_text('4 nodes · 5 rods')
            assert page.locator('#network .edge-button').count()==5
            assert not page.locator('#reversal').is_disabled()
            page.locator('#reversal').click()
            expect(page.locator('#time-label')).to_have_text('1,730 s')
            assert '+0.0058 W' in page.locator('#current-value').inner_text()
            assert 'left → right' in page.locator('#current-direction').inner_text()
            assert 'Absorbed from network' in page.locator('#energy-readouts').inner_text()
            assert '1720' not in page.locator('#current-value').inner_text()
            page.screenshot(path=str(evidence/'bridge.png'),full_page=True,animations='disabled')

            page.locator('#play').click();expect(page.locator('#play')).to_have_text('Ⅱ Pause')
            page.locator('#play').click();expect(page.locator('#play')).to_have_text('▶ Play')
            page.locator('#reset').click();expect(page.locator('#time-label')).to_have_text('0 s')

            bogus=evidence/'wrong.csv';bogus.write_text('time,left.T\n0,300\n')
            page.locator('#native-import').set_input_files(str(bogus))
            expect(page.locator('#import-status')).to_contain_text('File refused: Original native CSV SHA-256 mismatch')
            assert page.locator('#sample-note').inner_text().startswith('23 saved points')

            # A different source case cannot silently reuse previous good observations.
            def tampered(route): route.fulfill(status=200,content_type='application/json',body='{"schema":"tampered"}')
            page.route('**/data/D2.json',tampered)
            page.locator('#case-select').select_option('H1_D2')
            expect(page.locator('#error')).to_contain_text('Case digest differs from source catalog')
            assert page.locator('#current-value').inner_text()=='—'
            assert page.locator('#time-slider').is_disabled()
            page.screenshot(path=str(evidence/'refusal.png'),full_page=True,animations='disabled')
            page.unroute('**/data/D2.json',tampered)
            page.reload(wait_until='networkidle')
            expect(page.locator('#model-id')).to_have_text('H1_D1')
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#case-select').select_option('DEV_BRIDGE')
            expect(page.locator('#graph-count')).to_have_text('4 nodes · 5 rods')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 5')
            page.locator('#reversal').click()
            expect(page.locator('#time-label')).to_have_text('1,730 s')
            page.screenshot(path=str(evidence/'mobile.png'),full_page=True,animations='disabled')
            assert not errors,errors
            browser.close()
            print('PASS: 3 data-only cases; topology; signed directions; data-only switching; desktop/mobile; keyboard; negative SHA; screenshots')
    finally:
        http.shutdown();http.server_close();thread.join(timeout=3)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('h2_generic_ci_evidence/screenshots'))
    run(p.parse_args().out)
