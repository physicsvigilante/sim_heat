"""Real Chromium DOM/selection/layout smoke on a captured OFFLINE HTML document.

set_content executes the actual generated page's inline script and CSP. It does
not start a server, load remote assets, install a browser, run OMC, authenticate
an owner, or establish cross-browser/assistive-technology certification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright


def inspect(html_path: Path, output: Path) -> dict:
    raw = html_path.read_bytes()
    page_source = raw.decode('utf-8')
    output.mkdir(parents=True, exist_ok=True)
    requests, errors = [], []
    selections = []
    with sync_playwright() as p:
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
        browser = p.chromium.launch(headless=True, executable_path=executable)
        page = browser.new_page(viewport={'width': 1200, 'height': 1000})
        page.on('request', lambda r: requests.append(r.url))
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content(page_source, wait_until='load')
        page.wait_for_function("document.getElementById('request-detail').textContent.length > 0")
        assert page.locator('svg .node').count() == 4
        assert page.locator('svg .rod').count() == 4
        assert page.locator('svg .rod .connector').count() == 4
        assert page.locator('#public-request option').count() == 10
        assert 'NOT TO PHYSICAL SCALE' in page.locator('.warning').inner_text()
        assert 'RELEASE BLOCKED' in page.locator('.warning').inner_text()
        # Browser geometry of the source paths agrees with both junction rims;
        # the Python regression also tests exact lane/bend coordinates.
        endpoints = page.locator('svg .rod .connector').evaluate_all('''paths => paths.map(path => {
            const length=path.getTotalLength();
            const start=path.getPointAtLength(0), end=path.getPointAtLength(length);
            return {rod:path.parentElement.dataset.element,
                    start:[start.x,start.y],end:[end.x,end.y]};
        })''')
        expected = {'rod-hotLead': ([161,218],[353,218]),
                    'rod-flatBridge': ([411,218],[603,218]),
                    'rod-roundBridge': ([411,218],[603,218]),
                    'rod-coldLead': ([661,218],[853,218])}
        for edge in endpoints:
            assert (edge['start'],edge['end']) == expected[edge['rod']],edge
        options = page.locator('#public-request option').evaluate_all(
            'options => options.map(o=>({id:o.value,targets:(o.dataset.focus||" ").trim().split(",").filter(Boolean),summary:o.dataset.summary||""}))')
        page.screenshot(path=str(output/'desktop-source-topology.png'),full_page=True)
        for option in options[1:]:
            page.select_option('#public-request', option['id'])
            chosen=page.locator('svg [data-element].selected').evaluate_all(
                'items => items.map(item=>item.dataset.element)')
            assert chosen and set(chosen)==set(option['targets']),option
            text=page.locator('#request-detail').inner_text()
            assert text==option['summary'] and 'native value NOT COMPUTED' in text
            selections.append({'id':option['id'],'targets':chosen,'nativeValueComputed':False})
        page.select_option('#public-request','flatBridgeFlow')
        page.screenshot(path=str(output/'desktop-flat-bridge-selected.png'),full_page=True)
        page.select_option('#public-request','')
        assert page.locator('svg [data-element].selected').count()==0
        page.locator('#public-request').focus()
        page.keyboard.press('ArrowDown')
        page.keyboard.press('Enter')
        assert page.locator('#public-request').input_value()=='leftTemperature'
        assert 'leftTemperature' in page.locator('#request-detail').inner_text()
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth') <= 390
        assert page.locator('.diagram').evaluate('(d)=>d.scrollWidth>d.clientWidth')
        page.select_option('#public-request','')
        page.screenshot(path=str(output/'mobile-left.png'),full_page=True)
        page.locator('.diagram').evaluate('(d)=>d.scrollLeft=d.scrollWidth')
        page.screenshot(path=str(output/'mobile-right.png'),full_page=True)
        version=browser.version
        browser.close()
    assert errors==[],errors
    assert requests==[],requests
    result={'status':'OFFLINE_CHROMIUM_SMOKE_PASS',
            'htmlSha256':hashlib.sha256(raw).hexdigest(),
            'browserVersion':version,'loadingMethod':'page.set_content; no URL navigation',
            'viewports':[[1200,1000],[390,844]],'verifiedRequestSelections':selections,
            'connectorEndpoints':endpoints,'keyboardSelectionVerified':True,
            'mobileDocumentOverflow':False,'mobileDiagramScrollVerified':True,
            'networkRequests':requests,'javascriptErrors':errors,'nativeExecuted':False,
            'limits':['One Chromium build only; no cross-browser or screen-reader certification',
                      'No physical geometry, native values or owner authorization established']}
    (output/'browser-report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--html',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(inspect(a.html,a.out),indent=2))


if __name__=='__main__':main()
