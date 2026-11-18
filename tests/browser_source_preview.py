"""Actual HTTP Chromium smoke for source-only preview; no native operation."""
from __future__ import annotations
import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import sys
from threading import Thread

from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from h1.study import load_study
from h1.source_preview import build_source_preview, serialized


def run(out: Path):
    out.mkdir(parents=True,exist_ok=True)
    other=serialized(build_source_preview(load_study(ROOT/'h1/cases/D2/study.json',ROOT/'h1/cases')))
    first=json.loads((ROOT/'viewer/source_preview/data/TEACH_SPLIT3.json').read_bytes())
    first['source']['nativeQualified']=True
    bad=json.dumps(first).encode()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(ROOT)))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    errors=[]
    try:
        with sync_playwright() as p:
            executable=shutil.which('chromium') or shutil.which('google-chrome')
            browser=p.chromium.launch(headless=True,executable_path=executable,args=['--no-sandbox'])
            try:
                for label,viewport in [('desktop',{'width':1440,'height':950}),('mobile',{'width':390,'height':844})]:
                    page=browser.new_page(viewport=viewport)
                    page.on('pageerror',lambda err:errors.append(str(err)))
                    try:
                        response=page.goto(origin+'/viewer/source_preview/',wait_until='networkidle')
                        assert response and response.ok
                        page.wait_for_function("document.querySelector('#state').textContent.includes('admitted_source_only') || document.querySelector('#state').textContent.includes('Admitted source only')")
                        assert page.locator('#error').is_hidden(),page.locator('#error').inner_text()
                        assert page.locator('#graph g[role=button]').count()==13
                        assert page.locator('#requests .request').count()==4
                        assert page.locator('#requests').inner_text().count('not_computed')==4
                        assert page.locator('#identity').inner_text().count('false')>=3
                        assert page.locator('#element-select option').count()==18
                        page.locator('#element-select').select_option('shortcut')
                        assert 'shortcut' in page.locator('#details').inner_text()
                        assert 'Authored endpoints' in page.locator('#details').inner_text()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        page.screenshot(path=str(out/f'source-{label}.png'),full_page=True)
                        # A forged nativeQualified flag must refuse and CLEAR prior graph/requests.
                        page.locator('#import').set_input_files({'name':'forged.json','mimeType':'application/json','buffer':bad})
                        page.locator('#error').wait_for(state='visible')
                        assert 'REFUSED' in page.locator('#error').inner_text()
                        assert page.locator('#graph g').count()==0
                        assert page.locator('#element-select').is_disabled()
                        assert page.locator('#requests .request').count()==0
                        page.screenshot(path=str(out/f'refusal-{label}.png'),full_page=True)
                        # A second unrelated admitted H1 composition must load without changing viewer code.
                        page.locator('#import').set_input_files({'name':'D2-source.json','mimeType':'application/json','buffer':other})
                        page.wait_for_function("document.querySelector('#graph-title').textContent.includes('H1_D2')")
                        assert page.locator('#error').is_hidden()
                        assert 'H1_D2' in page.locator('#graph-title').inner_text()
                        assert page.locator('#requests .request').count()==2
                        assert page.locator('#identity').inner_text().count('false')>=3
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        # Deterministically delay a prior file read. The more recent
                        # refusal must win even if the older valid file completes last.
                        page.evaluate('''() => {
                          const originalText=File.prototype.text;
                          File.prototype.text=function(){
                            const item=this;
                            return new Promise((resolve,reject)=>setTimeout(
                              ()=>originalText.call(item).then(resolve,reject),
                              item.name==='slow.json'?180:8));
                          };
                          window.testImport=(name,text)=>{
                            const input=document.querySelector('#import');
                            const transfer=new DataTransfer();
                            transfer.items.add(new File([text],name,{type:'application/json'}));
                            input.files=transfer.files;
                            input.dispatchEvent(new Event('change',{bubbles:true}));
                          };
                        }''')
                        page.evaluate('''({good,bad})=>{
                          window.testImport('slow.json',good);
                          window.testImport('fast.json',bad);
                        }''',{'good':other.decode(),'bad':bad.decode()})
                        page.wait_for_timeout(260)
                        assert page.locator('#error').is_visible()
                        assert page.locator('#graph g').count()==0
                        assert page.locator('#requests .request').count()==0
                        # Inverse order: an older refusal must not replace a
                        # newer valid source composition or restore stale state.
                        page.evaluate('''({good,bad})=>{
                          window.testImport('slow.json',bad);
                          window.testImport('fast.json',good);
                        }''',{'good':other.decode(),'bad':bad.decode()})
                        page.wait_for_timeout(260)
                        assert page.locator('#error').is_hidden()
                        assert 'H1_D2' in page.locator('#graph-title').inner_text()
                        assert page.locator('#requests .request').count()==2
                    finally:
                        page.close()
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    print('PASS: two authored H1 topologies, default source-only visibility, real HTTP browser, refusal clears stale UI, out-of-order imports, desktop/mobile; no native execution.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
