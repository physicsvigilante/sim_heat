"""Real Chromium read-only H2-02 case switching and refusal smoke.

Runs on localhost only, with no OpenModelica or physics-application actions.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import argparse
import csv
import hashlib
import io
import json
import shutil
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

def numeric_time(page):
    # Compare the saved physical timestamp, not a UI rounding/display style.
    return float(page.locator('#time-label').inner_text().replace(',', '').split()[0])

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
            expect(page.locator('#sample-note')).to_contain_text('21 saved points')
            expect(page.locator('#time-slider')).to_be_enabled()
            assert numeric_time(page)==0.0
            assert page.locator('#energy-readouts .record-field').count()==3
            assert page.locator('#reversal').is_disabled()
            page.locator('#time-slider').focus()
            expect(page.locator('#time-slider')).to_be_focused()
            page.keyboard.press('ArrowRight')
            expect(page.locator('#time-slider')).to_have_value('1')
            assert numeric_time(page)==468.75
            page.screenshot(path=str(evidence/'D2.png'),full_page=True,animations='disabled')

            page.locator('#case-select').select_option('DEV_BRIDGE')
            expect(page.locator('#graph-count')).to_have_text('4 nodes · 5 rods')
            assert page.locator('#network .edge-button').count()==5
            assert not page.locator('#reversal').is_disabled()
            page.locator('#reversal').click()
            assert numeric_time(page)==1730.0
            assert '+0.0058 W' in page.locator('#current-value').inner_text()
            assert 'left → right' in page.locator('#current-direction').inner_text()
            assert 'Absorbed from network' in page.locator('#energy-readouts').inner_text()
            assert '1720' not in page.locator('#current-value').inner_text()
            page.screenshot(path=str(evidence/'bridge.png'),full_page=True,animations='disabled')

            page.locator('#play').click();expect(page.locator('#play')).to_have_text('Ⅱ Pause')
            page.locator('#play').click();expect(page.locator('#play')).to_have_text('▶ Play')
            page.locator('#reset').click();expect(page.locator('#time-label')).to_contain_text('0');assert numeric_time(page)==0.0

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
            # F-01: a refused case must clear every previous evidence panel.
            for field in ('time-label','graph-count','model-id','check-count',
                          'csv-sha','field-unit','current-direction','time-start','time-stop'):
                assert page.locator('#'+field).inner_text()=='—',field
            assert page.locator('#native-run').inner_text()=='—'
            assert page.locator('#native-run').get_attribute('href') is None
            assert page.locator('#energy-readouts').inner_text()==''
            assert page.locator('#temp-legend').inner_text()==''
            assert page.locator('#network').locator('*').count()==0
            assert page.locator('#observation option').count()==0
            assert 'No evidence displayed' in page.locator('#sample-note').inner_text()
            assert 'No verified evidence' in page.locator('#reversal-note').inner_text()
            assert 'No verified evidence' in page.locator('#import-status').inner_text()
            page.screenshot(path=str(evidence/'refusal.png'),full_page=True,animations='disabled')
            page.unroute('**/data/D2.json',tampered)
            page.reload(wait_until='networkidle')
            expect(page.locator('#model-id')).to_have_text('H1_D1')
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#case-select').select_option('DEV_BRIDGE')
            expect(page.locator('#graph-count')).to_have_text('4 nodes · 5 rods')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 5')
            page.locator('#reversal').click()
            assert numeric_time(page)==1730.0
            page.screenshot(path=str(evidence/'mobile.png'),full_page=True,animations='disabled')
            # F-02: Test-only synthetic full D1 fixture, with its own
            # temporary, re-hashed D1 bundle/catalog. It exercises real
            # WebCrypto + native CSV parsing, NOT an independent native result.
            with TemporaryDirectory() as scratch:
                case=json.loads((ROOT/'data/D1.json').read_text())
                index=json.loads((ROOT/'data/index.json').read_text())
                cols=case['columns']
                selected={row[0]:row for row in case['samples']}
                a=case['analysis'];step=(a['stop']-a['start'])/a['intervals']
                buf=io.StringIO(newline='');writer=csv.writer(buf,lineterminator='\n')
                writer.writerow(cols)
                for i in range(a['intervals']+1):
                    t=a['start']+i*step
                    last=selected.get(t,[t]+[0.0]*(len(cols)-1))
                    writer.writerow([str(v) for v in last])
                writer.writerow([str(v) for v in last])
                csv_data=buf.getvalue().encode('utf-8')
                fixture=Path(scratch)/'SYNTHETIC-ONLY-D1-race.csv';fixture.write_bytes(csv_data)
                case['source']['csvSha256']=hashlib.sha256(csv_data).hexdigest()
                case_bytes=(json.dumps(case,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
                index['cases'][0]['sha256']=hashlib.sha256(case_bytes).hexdigest()
                index_bytes=(json.dumps(index,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
                test=browser.new_page(viewport={'width':1260,'height':830})
                test.on('pageerror',lambda exc:errors.append(str(exc)))
                test.route('**/data/index.json',lambda route:route.fulfill(
                    status=200,content_type='application/json',body=index_bytes))
                test.route('**/data/D1.json',lambda route:route.fulfill(
                    status=200,content_type='application/json',body=case_bytes))
                test.add_init_script("""(()=>{
                  const original=SubtleCrypto.prototype.digest;
                  window.__heldNative={armed:false,pending:false,done:false,release:null,expected:0,seen:[]};
                  SubtleCrypto.prototype.digest=function(algo,bytes){
                    window.__heldNative.seen.push([String(algo),bytes.byteLength,window.__heldNative.armed]);
                    if(window.__heldNative.armed && algo==='SHA-256'
                       && bytes.byteLength===window.__heldNative.expected){
                      window.__heldNative.armed=false;
                      window.__heldNative.pending=true;
                      return new Promise((resolve,reject)=>{
                        window.__heldNative.release=()=>{
                          Promise.resolve(original.call(this,algo,bytes)).then(value=>{
                            resolve(value);window.__heldNative.done=true;
                          },reject);
                        };
                      });
                    }
                    return original.call(this,algo,bytes);
                  };
                })();""")
                test.goto(f'http://127.0.0.1:{http.server_port}/index.html',wait_until='networkidle')
                expect(test.locator('#model-id')).to_have_text('H1_D1')
                # Positive control: a correctly repinned synthetic fixture
                # passes the real SHA-256, grid, duplicate and preview checks.
                test.locator('#native-import').set_input_files(str(fixture))
                expect(test.locator('#sample-note')).to_contain_text('1001 saved points')
                expect(test.locator('#import-status')).to_contain_text('Exact native CSV verified')
                test.reload(wait_until='networkidle')
                expect(test.locator('#model-id')).to_have_text('H1_D1')
                test.evaluate('(size)=>{window.__heldNative.expected=size;window.__heldNative.armed=true}',len(csv_data))
                test.locator('#native-import').set_input_files(str(fixture))
                try:
                    test.wait_for_function('window.__heldNative.pending && window.__heldNative.release',timeout=4000)
                except Exception:
                    print('DIAGNOSTIC import hold state:',test.evaluate("""()=>({
                      hold:window.__heldNative,
                      model:document.querySelector('#model-id')?.textContent,
                      importStatus:document.querySelector('#import-status')?.textContent,
                      samples:document.querySelector('#sample-note')?.textContent
                    })"""))
                    raise
                test.locator('#case-select').select_option('H1_D2')
                expect(test.locator('#model-id')).to_have_text('H1_D2')
                expect(test.locator('#sample-note')).to_contain_text('21 saved points')
                test.evaluate('window.__heldNative.release()')
                test.wait_for_function('window.__heldNative.done')
                test.wait_for_timeout(100)
                expect(test.locator('#model-id')).to_have_text('H1_D2')
                assert test.locator('#sample-note').inner_text().startswith('21 saved points')
                assert test.locator('#energy-readouts .record-field').count()==3
                assert 'NaN' not in test.locator('#energy-readouts').inner_text()
                assert 'Exact native CSV verified' not in test.locator('#import-status').inner_text()
                test.screenshot(path=str(evidence/'import-race.png'),full_page=True,animations='disabled')
                test.close()
            assert not errors,errors
            browser.close()
            print('PASS: D1/D2/bridge, refusal clears old J/W/model, async import isolated, synthetic CSV positive-control SHA, desktop/mobile, screenshots')
    finally:
        http.shutdown();http.server_close();thread.join(timeout=3)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('h2_generic_ci_evidence/screenshots'))
    run(p.parse_args().out)
