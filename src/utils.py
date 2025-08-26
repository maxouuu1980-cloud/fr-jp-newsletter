import json, os, time
from slugify import slugify

STATE_FILE = os.getenv('STATE_FILE', 'state/seen.json')

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_seen(ids):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sorted(list(ids)), f, ensure_ascii=False, indent=2)

def make_slug(title: str):
    return slugify(title)[:120]
