import feedparser, yaml, hashlib, os
from datetime import datetime, timedelta, timezone
from .utils import load_seen, save_seen

MAX_ITEMS = int(os.getenv('MAX_ITEMS', '12'))
RECENT_DAYS = int(os.getenv('RECENT_DAYS', '45'))

def _hash(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8')).hexdigest()

def load_sources(path='config/sources.yml'):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def fetch_recent():
    cfg = load_sources()
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)
    seen = load_seen()
    picked = []
    for cat, urls in cfg.get('feeds', {}).items():
        for url in urls:
            d = feedparser.parse(url)
            for e in d.entries[:50]:
                uid = _hash((e.get('id') or e.get('link') or '') + (e.get('title') or ''))
                # choose published or updated
                if e.get('published_parsed'):
                    published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                elif e.get('updated_parsed'):
                    published = datetime(*e.updated_parsed[:6], tzinfo=timezone.utc)
                else:
                    published = datetime.now(timezone.utc)
                if published < cutoff:
                    continue
                if uid in seen:
                    continue
                picked.append({
                    'id': uid,
                    'category': cat,
                    'title': (e.get('title') or '').strip(),
                    'summary': (e.get('summary') or '').strip(),
                    'link': e.get('link'),
                    'published': published.isoformat(),
                    'source': url
                })
    picked = sorted(picked, key=lambda x: x['published'], reverse=True)[:MAX_ITEMS]
    seen |= {p['id'] for p in picked}
    save_seen(seen)
    return picked
