"""
Publishes the generated HTML to Substack.
Option A: Use python-substack-tarun (unofficial wrapper). Requires SUBSTACK_SESSION (cookie) or login.
Option B: Fallback — create a draft post only and print instructions.
"""
import os, pathlib, sys
from substack import Substack  # from python-substack-tarun
from src.utils import get_env, setup_logging

def publish(html_path: str, title: str, status: str="draft"):
    setup_logging()
    base_url = get_env("SUBSTACK_BASE_URL")  # e.g., https://yourpub.substack.com
    email = get_env("SUBSTACK_EMAIL")
    password = get_env("SUBSTACK_PASSWORD")
    sb = Substack(base_url=base_url, email=email, password=password)
    html = pathlib.Path(html_path).read_text(encoding="utf-8")
    post = sb.create_post(title=title, body_html=html, status=status)  # status: 'draft' or 'publish'
    url = post.get("post", {}).get("canonical_url", base_url)
    print(f"Created Substack post: {url}")
    return url

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.publish_substack out/newsletter_post.html 'Title' [draft|publish]")
        raise SystemExit(1)
    publish(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv)>3 else "draft")
