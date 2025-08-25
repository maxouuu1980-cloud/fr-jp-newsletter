"""
Full-auto Substack publishing via Playwright (Chromium).
- Logs in with email/password (must be enabled on your Substack account)
- Creates a NEW POST at /p/new
- Sets title and injects HTML body
- Saves as DRAFT by default
- Optionally publishes (if status == "publish")
Environment variables (required):
  SUBSTACK_BASE_URL  e.g. https://tonmag.substack.com
  SUBSTACK_EMAIL
  SUBSTACK_PASSWORD
Usage:
  python publish_via_playwright.py out/newsletter_post.html "Title here" draft
"""
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

BASE = os.environ.get("SUBSTACK_BASE_URL", "").rstrip("/")
EMAIL = os.environ.get("SUBSTACK_EMAIL")
PASSWORD = os.environ.get("SUBSTACK_PASSWORD")

def ensure_env():
    missing = [k for k,v in [("SUBSTACK_BASE_URL", BASE), ("SUBSTACK_EMAIL", EMAIL), ("SUBSTACK_PASSWORD", PASSWORD)] if not v]
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)}")

def read_html(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")

def login(page):
    # Substack centralized login
    page.goto("https://substack.com/sign-in", wait_until="domcontentloaded", timeout=120000)
    # Fill email
    email_sel_candidates = [
        "input[name='email']",
        "input[type='email']",
        "input[placeholder*='email' i]"
    ]
    for sel in email_sel_candidates:
        try:
            page.fill(sel, EMAIL, timeout=5000)
            break
        except PwTimeout:
            continue
    else:
        raise RuntimeError("Email input not found on Substack sign-in page.")
    # Click Continue or Next
    btn_candidates = [
        "button:has-text('Continue')",
        "button:has-text('Sign in')",
        "button:has-text('Next')"
    ]
    for sel in btn_candidates:
        try:
            page.click(sel, timeout=5000)
            break
        except PwTimeout:
            continue

    # If password page appears, fill it
    try:
        page.wait_for_selector("input[name='password'], input[type='password']", timeout=15000)
        page.fill("input[name='password'], input[type='password']", PASSWORD, timeout=5000)
        # Click Sign in
        page.click("button:has-text('Sign in'), button:has-text('Continue')", timeout=10000)
    except PwTimeout:
        # Some accounts may auto-login via email link (not supported). Require password flow.
        pass

    # Wait for either home or publications page
    page.wait_for_load_state("networkidle", timeout=120000)

def create_post(page, title: str, html_body: str, status: str = "draft") -> str:
    # Open compose page of the target publication
    compose_url = f"{BASE}/p/new"
    page.goto(compose_url, wait_until="domcontentloaded", timeout=120000)

    # Fill title
    title_selectors = [
        "textarea[placeholder*='title' i]",
        "input[placeholder*='title' i]",
        "[data-testid='post-title']",
        "h1[contenteditable='true']"
    ]
    set_title = False
    for sel in title_selectors:
        try:
            el = page.wait_for_selector(sel, timeout=10000)
            el.click()
            for _ in range(3):
                el.press("Control+A")
                el.press("Backspace")
            el.type(title, delay=20)
            set_title = True
            break
        except PwTimeout:
            continue
    if not set_title:
        page.keyboard.type(title)

    # Editor body
    body_selectors = [
        "div[contenteditable='true']",
        "[data-testid='editor'] div[contenteditable='true']",
        "div.ProseMirror[contenteditable='true']"
    ]
    editor = None
    for sel in body_selectors:
        try:
            editor = page.wait_for_selector(sel, timeout=15000)
            break
        except PwTimeout:
            continue
    if editor is None:
        raise RuntimeError("Could not find Substack editor body.")

    page.evaluate("""(el, html) => { el.innerHTML = html; }""", editor, html_body)
    time.sleep(2)
    try:
        page.keyboard.press("Control+S")
    except Exception:
        pass
    time.sleep(2)
    url = page.url
    if "/p/new" in url:
        try:
            page.click("button:has-text('Save')", timeout=5000)
            time.sleep(2)
            url = page.url
        except PwTimeout:
            pass

    if status.lower() == "publish":
        published = False
        for sel in ["button:has-text('Publish')","button:has-text('Publish now)']"]:
            try:
                page.click(sel, timeout=8000)
                published = True
                break
            except PwTimeout:
                continue
        if published:
            try:
                page.click("button:has-text('Publish now')", timeout=8000)
            except PwTimeout:
                try:
                    page.click("button:has-text('Publish')", timeout=8000)
                except PwTimeout:
                    pass
            time.sleep(5)
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
    html_body = read_html(html_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage","--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()
        login(page)
        url = create_post(page, title, html_body, status=status)
        print(f"Result URL: {url}")
        context.close()
        browser.close()

if __name__ == "__main__":
    main()
