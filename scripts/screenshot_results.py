"""README image of the analysis results: runs the simulated demo on the static site and saves the plots panel.

Run: python scripts/screenshot_results.py   ->  docs/img/analyse_results.png
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_static  # noqa: E402
from screenshots import serve  # noqa: E402


def main():
    site = Path(tempfile.mkdtemp()) / "site"
    build_static.build(site)
    out = ROOT / "docs" / "img" / "analyse_results.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome")
        except Exception:
            browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(serve(site) + "#/analyse/demo")
        page.wait_for_selector("#p-ac svg")
        page.check("#v-tracks")
        page.locator("#results .two").screenshot(path=str(out))
        browser.close()
    print(f"saved {out}")


if __name__ == "__main__":
    main()
