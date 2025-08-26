import feedparser, yaml, hashlib, os, logging, time
from datetime import datetime, timedelta, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .utils import load_seen, save_seen

# --------- Réglages ----------
MAX_ITEMS   = int(os.getenv('MAX_ITEMS', '12'))
RECENT_DAYS = int(os.getenv('RECENT_DAYS', '45'))
TIMEOUT_S   = float(os.getenv('HTTP_TIMEOUT', '15'))   # seconds
RETRIES     = int(os.getenv('HTTP_RETRIES', '4'))
BACKOFF     = float(os.getenv('HTTP_BACKOFF', '0.6'))

UA = os.getenv(
    'HTTP_USER_AGENT',
    'FRJPNewsletterBot/1.0 (+https://github.com/your/repo) Python-requests'
)

ACCEPT = 'application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5'
# ------------------------------

log = logging.getLogger("feeds")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

def _hash(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8')).hexdigest()

def load_sources(path='config/sources.yml'):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def _http_session():
    retry = Retry(
        total=RETRIES,
        connect=RETRIES,
        read=RETRIES,
        status=RETRIES,
        backoff_factor=BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(['GET', 'HEAD'])
    )
    s = requests.Session()
    s.headers.update({'User-Agent': UA, 'Accept': ACCEPT})
    s.mount('https://', HTTPAdapter(max_retries=retry))
    s.mount('http://', HTTPAdapter(max_retries=retry))
    return s

def _fetch_one(session: requests.Session, url: str):
    """Télécharge le flux avec retries/UA/timeout et parse via feedparser."""
    try:
        resp = session.get(url, timeout=TIMEOUT_S)
        resp.raise_for_status()
        # Utilise feedparser sur le contenu déjà téléchargé (évite les problèmes d’UA)
        return feedparser.parse(resp.content)
    except Exception as e:
        log.warning("Flux en échec: %s — %s", url, e)
        return feedparser.parse(b"")  # flux vide pour continuer

def fetch_recent():
    cfg = load_sources()
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)
    seen = load_seen()
    picked = []

    session = _http_session()

    for cat, urls in cfg.get('feeds', {}).items():
        for url in urls:
            d = _fetch_one(session, url)

            # Si le serveur renvoie une redirection vers HTML sans feed,
            # d.entries sera vide — on continue sans planter.
            for e in d.entries[:50]:
                uid = _hash((e.get('id') or e.get('link') or '') + (e.get('title') or ''))
                # date de publication robuste
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

            # petite pause polie pour éviter le rate limiting dur
            time.sleep(0.4)

    picked = sorted(picked, key=lambda x: x['published'], reverse=True)[:MAX_ITEMS]
    seen |= {p['id'] for p in picked}
    save_seen(seen)
    return picked
