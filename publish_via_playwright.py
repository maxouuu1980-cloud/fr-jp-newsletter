"""
Robust Substack publisher via Playwright (Chromium).
- Tries multiple login URLs and selectors (works around Cloudflare/cookies pages)
- Searches inputs across iframes
- Takes screenshots for debugging (saved in out/playwright/*.png)
Usage:
  python publish_via_playwright.py out/newsletter_post.html "Title" [draft|publish]

Required env vars:
  SUBSTACK_BASE_URL  e.g. https://tonmag.substack.com
  SUBSTACK_EMAIL
  SUBSTACK_PASSWORD
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

BASE = os.environ.get("SUBSTACK_BASE_URL", "").rstrip("/")
EMAIL = os.environ.get("SUBSTACK_EMAIL")
PASSWORD = os.environ.get("SUBSTACK_PASSWORD")

OUTDIR = Path("out/playwright")
OUTDIR.mkdir(parents=True, exist_ok=True)

def ensure_env():
    miss = [k for k,v in [("SUBSTACK_BASE_URL", BASE), ("SUBSTACK_EMAIL", EMAIL), ("SUBSTACK_PASSWORD", PASSWORD)] if not v]
    if miss:
        raise SystemExit(f"Missing env vars: {', '.join(miss)}")

def ss(page, name):
    path = OUTDIR / f"{int(time.time())}_{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        print(f"[screenshot] {path}")
    except Exception as e:
        print(f"[screenshot failed] {e}")
    return path

def find_in_all_frames(page, selectors, timeout_ms=15000):
    # Try main frame first
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout_ms)
            return el
        except PwTimeout:
            pass
    # Then search in iframes
    for frame in page.frames:
        for sel in selectors:
            try:
                el = frame.wait_for_selector(sel, timeout=3000)
                return el
            except PwTimeout:
                continue
    return None

def click_if_exists(page, selectors, timeout_ms=4000):
    for sel in selectors:
        try:
            page.click(sel, timeout=timeout_ms)
            return True
        except PwTimeout:
            continue
        except Exception:
            continue
    return False

def login(page):
    # Visit base once (sets cookies, runs Cloudflare)
    page.goto(BASE, wait_until="domcontentloaded", timeout=120000)
    ss(page, "base_loaded")
    try:
        page.wait_for_load_state("networkidle", timeout=120000)
    except PwTimeout:
        pass

    login_urls = [
        "https://substack.com/sign-in?redirect=" + BASE + "/p/new",
        "https://substack.com/sign-in",
        BASE + "/login",
        BASE + "/account/login",
        BASE + "/publish/login",
    ]

    for url in login_urls:
        print(f"[login] trying {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        try:
            page.wait_for_load_state("networkidle", timeout=120000)
        except PwTimeout:
            pass
        ss(page, "login_page_loaded")

        # Dismiss cookie banners if any
        click_if_exists(page, [
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "button:has-text('J’accepte')",
            "button[aria-label*='accept' i]"
        ], timeout_ms=2000)

        # Email field across frames
        email_el = find_in_all_frames(page, [
            "input[name='email']",
            "input[type='email']",
            "input[placeholder*='email' i]",
            "input[autocomplete='email']",
        ], timeout_ms=8000)

        if not email_el:
            print("[login] email field not found on this page, trying next URL...")
            continue

        email_el.click()
        email_el.fill(EMAIL)
        ss(page, "email_filled")

        # Continue/Next/Sign in
        clicked = click_if_exists(page, [
            "button:has-text('Continue')",
            "button:has-text('Sign in')",
            "button:has-text('Next')",
            "button[type='submit']"
        ], timeout_ms=6000)
        time.sleep(1)

        # Password step (if present)
        pwd_el = find_in_all_frames(page, [
            "input[name='password']",
            "input[type='password']",
            "input[autocomplete='current-password']",
        ], timeout_ms=8000)

        if pwd_el:
            pwd_el.click()
            pwd_el.fill(PASSWORD)
            ss(page, "password_filled")
            click_if_exists(page, [
                "button:has-text('Sign in')",
                "button:has-text('Continue')",
                "button[type='submit']",
            ], timeout_ms=6000)

        # Wait until logged-in context
        try:
            page.wait_for_load_state("networkidle", timeout=120000)
        except PwTimeout:
            pass

        # Heuristic: if we can open /p/new without redirect back to sign-in, assume success
        page.goto(BASE + "/p/new", wait_until="domcontentloaded", timeout=120000)
        ss(page, "compose_loaded_try")
        if "/sign-in" not in page.url and "/login" not in page.url:
            print("[login] success")
            return True

    raise RuntimeError("Email input not found on any known login page (or login blocked).")

def create_post(page, title: str, html_body: str, status: str = "draft") -> str:
    page.goto(BASE + "/p/new", wait_until="domcontentloaded", timeout=120000)
    try:
        page.wait_for_load_state("networkidle", timeout=120000)
    except PwTimeout:
        pass
    ss(page, "compose_opened")

    title_candidates = [
        "textarea[placeholder*='title' i]",
        "input[placeholder*='title' i]",
        "[data-testid='post-title']",
        "h1[contenteditable='true']"
    ]
    title_set = False
    for sel in title_candidates:
        try:
            el = page.wait_for_selector(sel, timeout=10000)
            el.click()
            for _ in range(3):
                el.press("Control+A")
                el.press("Backspace")
            el.type(title, delay=15)
            title_set = True
            break
        except PwTimeout:
            continue
    if not title_set:
        page.keyboard.type(title)

    # Body
    body_candidates = [
        "div[contenteditable='true']",
        "[data-testid='editor'] div[contenteditable='true']",
        "div.ProseMirror[contenteditable='true']"
    ]
    editor = None
    for sel in body_candidates:
        try:
            editor = page.wait_for_selector(sel, timeout=15000)
            break
        except PwTimeout:
            continue
    if editor is None:
        ss(page, "body_editor_not_found")
        raise RuntimeError("Substack editor body not found.")

    page.evaluate("""(el, html) => { el.innerHTML = html; }""", editor, html_body)
    ss(page, "html_injected")
    time.sleep(2)
    try:
        page.keyboard.press("Control+S")
    except Exception:
        pass
    time.sleep(2)

    # Try to hit a save button if present
    click_if_exists(page, [
        "button:has-text('Save')",
        "button:has-text('Save draft')",
    ], timeout_ms=4000)
    time.sleep(2)
    ss(page, "after_save_attempt")

    url = page.url

    if status.lower() == "publish":
        # Try publish button(s)
        pub_clicked = click_if_exists(page, [
            "button:has-text('Publish')",
            "button:has-text('Publish now')",
        ], timeout_ms=8000)
        if pub_clicked:
            time.sleep(2)
            click_if_exists(page, [
                "button:has-text('Publish now')",
                "button:has-text('Publish')"
            ], timeout_ms=8000)
            time.sleep(5)
            ss(page, "after_publish")

        url = page.url

    return url

def main():
    ensure_env()
    if len(sys.argv) < 3:
        print("Usage: python publish_via_playwright.py out/newsletter_post.html \"Title\" [draft|publish]")
        raise SystemExit(1)
    html_path = sys.argv[1]
    title = sys.argv[2]
    status = sys.argv[3] if len(sys.argv) > 3 else "draft"
    html_body = Path(html_path).read_text(encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage","--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()
        try:
            login(page)
            url = create_post(page, title, html_body, status=status)
            print(f"Result URL: {url}")
        finally:
            ss(page, "final_state")
            context.close()
            browser.close()

if __name__ == "__main__":
    main()
