"""Real HTTP Chromium check of local-only admission into generic source inspector."""
from __future__ import annotations

import argparse
from functools import partial
import json
from pathlib import Path
import shutil
import sys
from threading import Thread

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.authoring_workbench import create_server
from h1.study import load_study
from h1.source_preview import serialized, build_source_preview


def run(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        executable = shutil.which('google-chrome') or shutil.which('chromium')
        browser = playwright.chromium.launch(headless=True, executable_path=executable,
                                              args=['--no-sandbox'])
        try:
            for case, label, width, height in (
                    ('D1', 'd1-desktop', 1440, 950),
                    ('S1', 'steady-mobile', 390, 844),
                    ('TEACH_SPLIT3', 'split3-desktop', 1440, 950)):
                server, payload = create_server(ROOT/'h1/cases'/case/'study.json',
                                                ROOT/'h1/cases')
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                origin = f'http://127.0.0.1:{server.server_port}'
                try:
                    page = browser.new_page(viewport={'width':width,'height':height})
                    requests = []
                    page.on('request', lambda req: requests.append(req.url))
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    try:
                        response = page.goto(origin+'/', wait_until='domcontentloaded')
                        assert response and response.ok
                        page.wait_for_function("document.querySelector('#state').textContent.includes('Admitted source only')")
                        assert page.locator('#error').is_hidden()
                        assert payload['modelName'] in page.locator('#graph-title').inner_text()
                        assert case not in ('D1','S1') or 'TEACH_SPLIT3' not in page.locator('#graph-title').inner_text()
                        assert page.locator('#requests .request').count()==len(payload['requests'])
                        assert page.locator('#requests').inner_text().count('not_computed')==len(payload['requests'])
                        assert payload['source']['studySha256'] in page.locator('#identity').inner_text()
                        assert 'false' in page.locator('#identity').inner_text()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        assert 'Your admitted H1 source loads automatically' in page.locator('main').inner_text()
                        page.screenshot(path=str(out/f'{label}.png'), full_page=True)
                        # Deliberately forged qualification must refuse, clearing prior state.
                        bad=json.loads(json.dumps(payload))
                        bad['source']['nativeQualified']=True
                        page.locator('#import').set_input_files({
                            'name':'forged-source.json','mimeType':'application/json',
                            'buffer':json.dumps(bad).encode('utf-8')})
                        page.locator('#error').wait_for(state='visible')
                        assert page.locator('#graph g').count()==0
                        assert page.locator('#requests .request').count()==0
                        assert page.locator('#model-assumptions').inner_text().strip()==''
                        assert page.locator('#element-select').is_disabled()
                        page.screenshot(path=str(out/f'{label}-refused.png'), full_page=True)
                        # Local server remains read-only and must not serve study/model source.
                        forbidden=page.request.get(origin+'/h1/cases/'+case+'/model.mo')
                        assert forbidden.status==404
                        posted=page.request.post(origin+'/viewer/source_preview/data/TEACH_SPLIT3.json',data=b'test')
                        assert posted.status==405
                        assert all(url.startswith(origin+'/') for url in requests),requests
                    finally:
                        page.close()
                finally:
                    server.shutdown(); server.server_close(); thread.join(timeout=5)
            # Teacher what-if mode: TWO genuinely admitted H1 studies served
            # read-only on one loopback session, never simulated or uploaded.
            server,baseline=create_server(ROOT/'h1/cases/D2/study.json',ROOT/'h1/cases',
                                          comparison_study=ROOT/'h1/cases/D2_K2/study.json')
            thread=Thread(target=server.serve_forever,daemon=True)
            thread.start()
            origin=f'http://127.0.0.1:{server.server_port}'
            try:
                page=browser.new_page(viewport={'width':1440,'height':990})
                page.on('pageerror',lambda err:errors.append(str(err)))
                try:
                    response=page.goto(origin+'/',wait_until='domcontentloaded')
                    assert response and response.ok
                    expect(page.locator('#comparison-state')).to_contain_text('difference(s)')
                    assert 'H1_D2_K2' in page.locator('#comparison-identity').inner_text()
                    assert 'shortcut' not in page.locator('#comparison-changes').inner_text()
                    assert 'rod.k' in page.locator('#comparison-changes').inner_text()
                    assert '100 W/(m K)' in page.locator('#comparison-changes').inner_text()
                    assert '200 W/(m K)' in page.locator('#comparison-changes').inner_text()
                    assert 'not_computed' in page.locator('#comparison-state').inner_text() or 'no computed' in page.locator('#comparison-state').inner_text()
                    assert 'nativeExecuted=false' in page.locator('#state').inner_text()
                    assert 'H1_D2' in page.locator('#graph-title').inner_text()
                    assert page.locator('#view-variant').is_enabled()
                    page.locator('#view-variant').click()
                    assert 'H1_D2_K2' in page.locator('#graph-title').inner_text()
                    assert '200 W/(m K)' in page.locator('#details').inner_text() or '200 W/(m K)' in page.locator('#comparison-changes').inner_text()
                    page.screenshot(path=str(out/'d2-whatif-source-only.png'),full_page=True)
                    # Replace the selected scenario with a forged native-status
                    # variant. The previous scenario graph must be cleared.
                    bad=json.loads(page.request.get(origin+'/viewer/source_preview/data/VARIANT.json').body())
                    bad['source']['nativeQualified']=True
                    page.locator('#variant-import').set_input_files({
                        'name':'forged-native-variant.json','mimeType':'application/json',
                        'buffer':json.dumps(bad).encode('utf-8')})
                    page.locator('#comparison-error').wait_for(state='visible')
                    assert page.locator('#comparison-changes .compare-item').count()==0
                    assert page.locator('#view-variant').is_disabled()
                    assert 'H1_D2_K2' not in page.locator('#graph-title').inner_text()
                    assert 'H1_D2' in page.locator('#graph-title').inner_text()
                    assert page.request.get(origin+'/h1/cases/D2_K2/model.mo').status==404
                    assert page.request.post(origin+'/viewer/source_preview/data/VARIANT.json',data=b'x').status==405
                    page.screenshot(path=str(out/'d2-whatif-refusal.png'),full_page=True)
                    # Chat B PR71 F-01 A->B->bad replacement: the latest
                    # comparison, rendered graph, selection details and requests
                    # must all refer to the same admitted display or baseline.
                    d1=json.loads(serialized(build_source_preview(load_study(
                        ROOT/'h1/cases/D1/study.json',ROOT/'h1/cases'))))
                    s1=json.loads(serialized(build_source_preview(load_study(
                        ROOT/'h1/cases/S1/study.json',ROOT/'h1/cases'))))
                    page.locator('#variant-import').set_input_files({
                        'name':'admitted-D1.json','mimeType':'application/json',
                        'buffer':json.dumps(d1).encode('utf-8')})
                    expect(page.locator('#comparison-identity')).to_contain_text('H1_D1')
                    page.locator('#view-variant').click()
                    assert 'H1_D1' in page.locator('#graph-title').inner_text()
                    assert d1['source']['studySha256'] in page.locator('#identity').inner_text()
                    assert page.locator('#requests .request').count()==len(d1['requests'])
                    page.locator('#variant-import').set_input_files({
                        'name':'malformed-variant.json','mimeType':'application/json',
                        'buffer':b'{}'})
                    page.locator('#comparison-error').wait_for(state='visible')
                    assert 'H1_D2' in page.locator('#graph-title').inner_text()
                    assert 'H1_D1' not in page.locator('#graph-title').inner_text()
                    assert baseline['source']['studySha256'] in page.locator('#identity').inner_text()
                    assert page.locator('#requests .request').count()==len(baseline['requests'])
                    assert page.locator('#view-variant').is_disabled()
                    assert page.locator('#comparison-changes .compare-item').count()==0
                    page.screenshot(path=str(out/'d2-replacement-refused.png'),full_page=True)
                    # Exercise an actual race between TWO file reads, not only
                    # the baseline loadVersion. The second chosen S1 scenario
                    # must win even after the first D1 file read resolves.
                    page.evaluate("""() => {
                      const original=File.prototype.text;
                      File.prototype.text=function(...args){
                        const pending=original.apply(this,args);
                        if(this.name==='slow-D1.json'){
                          return new Promise((resolve,reject)=>{
                            document.body.dataset.slowScenarioPending='yes';
                            window.__releaseSlowScenario=()=>pending.then(v=>{
                              window.__slowReadDelivered=true;document.body.dataset.slowReadDelivered='yes';resolve(v);
                            },reject);
                          });
                        }
                        return pending;
                      };
                      window.__slowReadDelivered=false;
                    }""")
                    page.locator('#variant-import').set_input_files({
                        'name':'slow-D1.json','mimeType':'application/json',
                        'buffer':json.dumps(d1).encode('utf-8')})
                    page.locator('body[data-slow-scenario-pending="yes"]').wait_for()
                    page.locator('#variant-import').set_input_files({
                        'name':'fast-S1.json','mimeType':'application/json',
                        'buffer':json.dumps(s1).encode('utf-8')})
                    expect(page.locator('#comparison-identity')).to_contain_text('H1_S1')
                    page.locator('#view-variant').click()
                    assert 'H1_S1' in page.locator('#graph-title').inner_text()
                    page.evaluate("() => window.__releaseSlowScenario()")
                    page.locator('body[data-slow-read-delivered="yes"]').wait_for()
                    page.wait_for_timeout(150)
                    assert 'H1_S1' in page.locator('#graph-title').inner_text()
                    assert 'H1_S1' in page.locator('#comparison-identity').inner_text()
                    assert 'H1_D1' not in page.locator('#comparison-identity').inner_text()
                    assert s1['source']['studySha256'] in page.locator('#identity').inner_text()
                    assert page.locator('#requests .request').count()==len(s1['requests'])
                    page.screenshot(path=str(out/'d2-last-import-wins.png'),full_page=True)
                    # Reviewer F-02: a byte-identical STUDY identifier cannot
                    # claim a different model SHA without changed study bytes.
                    same_study_wrong_model=json.loads(json.dumps(baseline))
                    same_study_wrong_model['source']['modelSha256']='f'*64
                    page.locator('#variant-import').set_input_files({
                        'name':'impossible-study-model-pair.json','mimeType':'application/json',
                        'buffer':json.dumps(same_study_wrong_model).encode('utf-8')})
                    page.locator('#comparison-error').wait_for(state='visible')
                    assert 'study SHA-256' in page.locator('#comparison-error').inner_text()
                    assert page.locator('#view-variant').is_disabled()
                    assert 'H1_D2' in page.locator('#graph-title').inner_text()
                    assert baseline['source']['studySha256'] in page.locator('#identity').inner_text()
                    assert page.locator('#comparison-changes .compare-item').count()==0
                    # Reviewer F-03: changing supported component law/type
                    # cannot silently omit its SI field and original attribution.
                    circular=json.loads(json.dumps(baseline))
                    rod=next(c for c in circular['components'] if c['id']=='rod')
                    assert rod['kind']=='RodArea'
                    rod['kind']='RodCircular'
                    area=next(v for v in rod['inputs'] if v['name']=='A')
                    area.update(name='d',quantityType='Length',siUnit='m',sourceValue=0.04)
                    for note in rod['sourceProvenance']:
                        if note['target']=='rod.A':
                            note['target']='rod.d'
                            note['note']='Revised from source area to illustrative diameter'
                        note['appliesTo']=[('rod.d' if x=='rod.A' else x)
                                           for x in note['appliesTo']]
                    circular['source']['modelSha256']='a'*64
                    circular['source']['studySha256']='b'*64
                    page.locator('#variant-import').set_input_files({
                        'name':'circular-source-only-variant.json','mimeType':'application/json',
                        'buffer':json.dumps(circular).encode('utf-8')})
                    expect(page.locator('#comparison-state')).to_contain_text('difference(s)')
                    summary=page.locator('#comparison-changes').inner_text()
                    assert 'rod · kind' in summary
                    assert 'rod.A' in summary and 'rod.d' in summary
                    assert 'provenance' in summary and 'Revised from source area' in summary
                    page.locator('#view-variant').click()
                    page.locator('#element-select').select_option('component:rod')
                    assert 'RodCircular' in page.locator('#details').inner_text()
                    assert 'd (source SI)' in page.locator('#details').inner_text()
                    assert page.locator('#requests .request').count()==len(baseline['requests'])
                    assert 'not_computed' in page.locator('#requests').inner_text()
                    page.screenshot(path=str(out/'d2-cross-kind-input-provenance.png'),full_page=True)
                finally:
                    page.close()
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)
            assert not errors, errors
        finally:
            browser.close()
    print('PASS: D1/S1/TEACH_SPLIT3 one-command local loopback source previews, distinct modes, refusals, read-only route limits and desktop/mobile; no native run.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
