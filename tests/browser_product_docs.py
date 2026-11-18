"""Actual HTTP click/readability/source-link smoke for generated product docs."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def run(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    errors = []
    try:
        with sync_playwright() as p:
            executable = shutil.which('google-chrome') or shutil.which('chromium')
            browser = p.chromium.launch(headless=True, executable_path=executable, args=['--no-sandbox'])
            try:
                for name, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
                    page = browser.new_page(viewport={'width': width, 'height': height})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    assert page.goto(origin + '/', wait_until='networkidle').ok
                    page.locator('#read-registry').click()
                    page.wait_for_url('**/docs/CAPABILITIES.html')
                    assert page.locator('h1').inner_text() == 'SIM_HEAT capability and evidence registry'
                    assert page.locator('table').count() == 3
                    assert 'nativeQualified=false' in page.locator('main').inner_text()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    assert page.locator('script,iframe,form').count() == 0
                    table = page.locator('.table-scroll').first
                    table.focus()
                    assert table.evaluate('(el) => el === document.activeElement')
                    page.screenshot(path=str(out / f'registry-{name}.png'), full_page=True)
                    with page.expect_navigation() as navigation:
                        page.locator('main a[href="../viewer/network/data/D1.json"]').click()
                    response = navigation.value
                    assert response and response.ok
                    assert response.json()['source']['nativeQualified'] is False
                    assert 'historical_native_diagnostic' in page.locator('body').inner_text()
                    assert page.goto(origin + '/', wait_until='networkidle').ok
                    page.locator('#read-authoring').click()
                    page.wait_for_url('**/docs/AUTHORING.html')
                    assert page.locator('h1').inner_text() == 'Author a supported thermal model'
                    assert page.locator('pre code.language-python').count() == 1
                    assert 'not_computed' in page.locator('main').inner_text()
                    assert 'historical H1 foundation contract' in page.locator('main').inner_text()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    assert page.locator('script,iframe,form').count() == 0
                    page.screenshot(path=str(out / f'authoring-{name}.png'), full_page=True)
                    with page.expect_navigation() as navigation:
                        page.locator('main a[href="../h1/cases/D1/study.json"]').click()
                    response = navigation.value
                    assert response and response.ok and response.json()['schema'] == 'sim_heat.study/1'
                    assert 'H1_D1' in page.locator('body').inner_text()
                    assert page.goto(origin + '/docs/CAPABILITIES.html', wait_until='networkidle').ok
                    page.locator('main a[href="AUTHORING.html"]').click()
                    page.wait_for_url('**/docs/AUTHORING.html')
                    page.close()
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    print('PASS: rendered registry/authoring tables, desktop/mobile clicks, original JSON source links and cross-navigation; no JavaScript page errors. No native execution.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
