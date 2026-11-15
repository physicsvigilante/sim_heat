"""Real Chromium smoke for static read-only H2 viewer, with captured screenshot.
Only localhost HTTP UI and saved native preview; no OMC simulation or engine mutation.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from tempfile import TemporaryDirectory
import argparse
import shutil
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

def main(screenshot: Path):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,directory=str(ROOT),**kwargs)
        def log_message(self,*args): pass
    http=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    worker=Thread(target=http.serve_forever,daemon=True);worker.start()
    executable=next((p for p in (shutil.which("google-chrome"),shutil.which("chromium"),
                shutil.which("chromium-browser")) if p),None)
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(**({"executable_path":executable} if executable else {}),
                                       headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
            page=browser.new_page(viewport={"width":1440,"height":1000})
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{http.server_port}/index.html",wait_until="networkidle")
            expect(page.locator("#mode")).to_have_text("HASH-PINNED NATIVE PREVIEW")
            assert page.locator("#count").inner_text()=="23/2,001 samples"
            assert page.locator("#bridge-value").inner_text()=="-6.00 W"
            assert page.locator("#direction").inner_text()=="Right → left"
            assert page.locator("#arrows path").count()==5
            page.locator("#jump").click()
            assert page.locator("#seconds").inner_text()=="1,730"
            assert page.locator("#direction").inner_text()=="Left → right"
            assert page.locator("#bridge-value").inner_text().startswith("+0.0058")
            assert page.locator("#bracket").inner_text()=="Flow reverses between 1,720 and 1,730 s"
            page.locator("#reset").click()
            assert page.locator("#seconds").inner_text()=="0"
            page.locator("#time").focus();page.keyboard.press("ArrowRight")
            assert page.locator("#seconds").inner_text()=="1,000"
            page.locator("#play").click();assert page.locator("#play").inner_text()=="Ⅱ Pause"
            page.locator("#play").click();assert page.locator("#play").inner_text()=="▶ Play"
            with TemporaryDirectory() as directory:
                bad=Path(directory)/"fake.csv";bad.write_text("time,left.T\n0,300\n")
                page.locator("#full-csv").set_input_files(str(bad))
                expect(page.locator("#file-note")).to_contain_text("File refused: SHA-256 mismatch")
                assert page.locator("#count").inner_text()=="23/2,001 samples"
            screenshot.parent.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(screenshot),full_page=True,animations="disabled")
            page.set_viewport_size({"width":390,"height":844})
            page.reload(wait_until="networkidle")
            expect(page.locator("#mode")).to_have_text("HASH-PINNED NATIVE PREVIEW")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 4")
            page.locator("#jump").click()
            assert page.locator("#direction").inner_text()=="Left → right"
            assert not errors,errors
            browser.close()
            print("PASS: desktop/mobile, signed-arrow reversal, time control, playback, SHA refusal, screenshot")
    finally:
        http.shutdown();http.server_close();worker.join(timeout=3)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--screenshot",type=Path,default=Path("h2_viewer_ci_evidence/browser.png"))
    args=parser.parse_args();main(args.screenshot)
