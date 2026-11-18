"""Real localhost navigation smoke for the static start page; no native operations."""
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
            browser = p.chromium.launch(headless=True, executable_path=executable,
                                        args=['--no-sandbox'])
            try:
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.on('pageerror', lambda error: errors.append(str(error)))
                for name, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    response = page.goto(origin + '/', wait_until='networkidle')
                    assert response and response.ok
                    assert page.title() == 'SIM_HEAT | Start exploring'
                    assert page.locator('#enter-explorer').is_visible()
                    for section in ('archived-native', 'analytical-checking', 'expected-only'):
                        assert page.locator('#' + section).count() == 1
                    assert page.locator('script, iframe, form').count() == 0
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.screenshot(path=str(out / f'entry-{name}.png'), full_page=True)
                    page.keyboard.press('Tab')
                    assert page.locator('#skip-link').evaluate('(el) => el === document.activeElement')
                    page.keyboard.press('Enter')
                    page.keyboard.press('Tab')
                    assert page.locator('#enter-explorer').evaluate('(el) => el === document.activeElement')
                    page.keyboard.press('Enter')
                    page.wait_for_url('**/viewer/network/index.html')
                    page.wait_for_function("document.querySelector('#case-select').options.length === 6 && !document.querySelector('#case-select').disabled")
                    assert page.locator('#error').inner_text() == ''
                    page.goto(origin + '/', wait_until='networkidle')
                    page.locator('#compare-saved').click()
                    page.wait_for_url('**/viewer/network/compare.html')
                    page.wait_for_function("!document.querySelector('#comparison-select').disabled && !document.querySelector('#inspector').hidden")
                    assert page.locator('#error').inner_text() == ''
                    page.goto(origin + '/', wait_until='networkidle')
                    href = page.locator('#read-registry').get_attribute('href')
                    registry = page.request.get(origin + '/' + href)
                    assert registry.ok and 'nativeQualified=false' in registry.text()
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    print('PASS: start-page desktop/mobile layout, keyboard navigation, six-case explorer, comparison and registry links; no page errors. No native execution.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
