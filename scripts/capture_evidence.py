"""Capture evidence from the real Streamlit app (no mocked pages)."""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
URL = "http://127.0.0.1:8501"

def click_if_visible(page, label: str) -> bool:
    locator = page.get_by_role("button", name=label, exact=True).first
    if not locator.count(): locator = page.get_by_text(label, exact=True).first
    if locator.count() and locator.is_visible() and locator.is_enabled():
        locator.evaluate("el => el.click()"); page.wait_for_timeout(900); return True
    return False

def capture(page, name: str) -> None:
    page.screenshot(path=str(EVIDENCE / name), full_page=True)

def main() -> None:
    EVIDENCE.mkdir(exist_ok=True)
    env = os.environ.copy(); env["FAIRDRAW_DEMO"] = "1"
    process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless=true", "--server.port=8501"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    captured: list[str] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width, suffix in ((1440, "1440"), (390, "390")):
                page = browser.new_page(viewport={"width": width, "height": 1100}, device_scale_factor=1)
                page.goto(URL, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(1500)
                if click_if_visible(page, "Load sample data"):
                    capture(page, f"squad-board-{suffix}.png"); captured.append(f"squad-board-{suffix}.png")
                    for player in ["Ari", "Bea", "Cal", "Dev", "Eli", "Finn", "Gia", "Hugo", "Iris", "Jules", "Kai", "Lena", "Milo", "Nia"]:
                        click_if_visible(page, player)
                    pills = page.locator('[data-testid="stPills"] button')
                    for index in range(min(10, pills.count())):
                        if pills.nth(index).is_enabled(): pills.nth(index).click()
                    page.wait_for_timeout(700)
                    capture(page, f"attendance-proposal-{suffix}.png"); captured.append(f"attendance-proposal-{suffix}.png")
                if click_if_visible(page, "Confirm attendance"):
                    capture(page, f"draw-disabled-{suffix}.png"); captured.append(f"draw-disabled-{suffix}.png")
                if click_if_visible(page, "RUN DRAW"):
                    page.wait_for_timeout(1800); capture(page, f"draw-pitch-{suffix}.png"); captured.append(f"draw-pitch-{suffix}.png")
                    if click_if_visible(page, "Write announcement"):
                        capture(page, f"share-card-{suffix}.png"); captured.append(f"share-card-{suffix}.png")
                if click_if_visible(page, "Safety demos (for the report)"):
                    capture(page, f"defense-log-attack-{suffix}.png"); captured.append(f"defense-log-attack-{suffix}.png")
                page.close()
            browser.close()
    finally:
        process.terminate(); process.wait(timeout=15)
    print(f"Captured {len(captured)} real-app screenshots.")
    for item in captured: print(item)
    print("Other evidence remains missing until its real UI state is reached or user material is supplied.")

if __name__ == "__main__": main()
