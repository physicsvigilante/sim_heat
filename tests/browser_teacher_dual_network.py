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
                    # PR74 independent reviewer F-02: inspect ACTUALLY drawn SVG
                    # connectivity, not merely the admitted source JSON.
                    assert page.locator('#graph line.rod').count() == 5
                    assert page.locator('#graph circle.component-node').count() == 6
                    assert page.locator('#graph circle.component-node.junction').count() == 1
                    rendered = page.evaluate("""() => {
                      const circles=[...document.querySelectorAll('#graph circle.component-node')];
                      const lines=[...document.querySelectorAll('#graph line.rod')];
                      const key=(x,y)=>x+','+y;
                      const map=new Map(circles.map((c,i)=>
                        [key(c.getAttribute('cx'),c.getAttribute('cy')),i]));
                      if(map.size!==circles.length)return {error:'coincident SVG nodes'};
                      const parent=circles.map((_,i)=>i);
                      const root=(i)=>{while(parent[i]!==i)i=parent[i];return i;};
                      const edges=[];
                      for(const line of lines){
                        const a=map.get(key(line.getAttribute('x1'),line.getAttribute('y1')));
                        const b=map.get(key(line.getAttribute('x2'),line.getAttribute('y2')));
                        if(a===undefined||b===undefined||a===b)
                          return {error:'line not between two distinct rendered nodes'};
                        parent[root(a)]=root(b);
                        edges.push([line.getAttribute('data-rod'),a,b]);
                      }
                      const groups=new Map();
                      circles.forEach((_,i)=>{const r=root(i);groups.set(r,(groups.get(r)||0)+1);});
                      const rodRoot=Object.fromEntries(edges.map(([id,a])=>[id,root(a)]));
                      return {nodeGroups:[...groups.values()].sort((a,b)=>a-b),
                              samePairAndBypass:rodRoot.pairLink===rodRoot.bypass,
                              rodNames:Object.keys(rodRoot).sort()};
                    }""")
                    assert 'error' not in rendered, rendered
                    assert rendered['nodeGroups'] == [2, 4], rendered
                    assert rendered['samePairAndBypass'] is False, rendered
                    assert rendered['rodNames'] == ['bypass', 'hotFeed', 'pairLink',
                                                    'seriesOne', 'seriesTwo'], rendered
                    assert page.locator('#graph g[aria-label="Inspect authored rod pairLink"]').count() == 1
                    page.locator('#graph g[aria-label="Inspect authored rod pairLink"]').click()
                    assert 'RodCircular' in page.locator('#details').inner_text()
                    node = page.locator('#graph g[aria-label^="Inspect source node Ideal junction"]')
                    assert node.count() == 1
                    node.click()
                    junction_details=page.locator('#details').inner_text()
                    assert 'Ownerless ideal junction' in junction_details
                    assert 'seriesOne.port_b' in junction_details
                    assert 'seriesTwo.port_a' in junction_details
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
