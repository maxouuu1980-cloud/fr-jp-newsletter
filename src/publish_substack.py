"""
Publishes the generated HTML to Substack using python-substack-tarun (unofficial).
- Creates a DRAFT by default
- If status == "publish", it publishes and envoie l'email (send=True)
"""

import os
import pathlib
import sys
from src.utils import get_env, setup_logging

# NOTE: with python-substack-tarun==0.1.16 the right import is Api (not Substack)
from substack import Api  # pip install python-substack-tarun==0.1.16

def publish(html_path: str, title: str, status: str = "draft"):
    setup_logging()

    base_url = get_env("SUBSTACK_BASE_URL")  # ex: https://tonmag.substack.com
    email = get_env("SUBSTACK_EMAIL")
    password = get_env("SUBSTACK_PASSWORD")

    # Initialize API client
    api = Api(
        email=email,
        password=password,
        publication_url=base_url
    )

    # Read generated HTML
    html = pathlib.Path(html_path).read_text(encoding="utf-8")

    # Create a draft
    draft_data = {
        "title": title,
        # Substack accepte du Markdown dans "body", mais le wrapper accepte aussi HTML en mode "body".
        # On pousse le HTML tel quel ici.
        "body": html,
        "published": False,
        "section_id": None,  # default section
        # "tags": ["FR-JP", "newsletter"],  # optionnel
    }
    draft = api.post_draft(draft_data)

    # Publish if requested
    if status.lower() == "publish":
        published = api.publish_draft(draft, send=True, share_automatically=False)
        url = published.get("url") or base_url
        print(f"Published Substack post: {url}")
        return url

    # Otherwise keep as draft
    # Selon le wrapper, l'URL de draft n'est pas toujours renvoyée; on loggue au minimum l'ID.
    draft_id = draft.get("id", "n/a")
    print(f"Created Substack draft id={draft_id} (check {base_url}/drafts)")
    return base_url

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: python -m src.publish_substack out/newsletter_post.html "Title" [draft|publish]')
        raise SystemExit(1)
    publish(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "draft")
