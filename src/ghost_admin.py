import os, time, requests, jwt
from .utils import make_slug

def _make_jwt(admin_api_key: str):
    key_id, secret = admin_api_key.split(':')
    iat = int(time.time())
    payload = {'iat': iat, 'exp': iat + 5*60, 'aud': '/admin/'}
    token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})
    return token

def create_post(html: str, title: str, tags=None, status='draft',
                send_email=False, newsletter_slug=None, feature_image=None):
    """
    Crée un post Ghost en envoyant du HTML. IMPORTANT :
    - 'source=html' doit être passé EN QUERY (params), pas dans le body.
    - 'html' doit être dans le body.
    - On construit toujours 'body' AVANT l'appel HTTP.
    - L'envoi d'email ne se fait PAS ici : seulement lors du publish (PUT) avec ?newsletter=<slug>.
    """
    admin_url = os.environ['GHOST_ADMIN_URL'].rstrip('/')
    api_key   = os.environ['GHOST_ADMIN_API_KEY']
    version   = os.getenv('GHOST_API_VERSION', 'v5.0')

    token = _make_jwt(api_key)
    headers = {
        'Authorization': f'Ghost {token}',
        'Accept-Version': version,
        'Content-Type': 'application/json'
    }

    # ✅ IMPORTANT : 'source=html' en QUERY
    url    = f'{admin_url}/ghost/api/admin/posts/'
    params = {'source': 'html'}

    post_obj = {
        'title': title,
        'slug': make_slug(title),
        'html': html,
        'status': status,
        'tags': [{'name': t} for t in (tags or [])],
    }
    if feature_image:
        post_obj['feature_image'] = feature_image

    # ✅ 'body' est défini AVANT le POST, sans condition
    body = {'posts': [post_obj]}

    r = requests.post(url, headers=headers, params=params, json=body, timeout=30)
    r.raise_for_status()
    return r.json()['posts'][0]

def publish_post(post_id: str, updated_at: str, send_email=False, newsletter_slug=None, email_only=False):
    admin_url = os.environ['GHOST_ADMIN_URL'].rstrip('/')
    api_key = os.environ['GHOST_ADMIN_API_KEY']
    version = os.getenv('GHOST_API_VERSION', 'v5.0')

    token = _make_jwt(api_key)
    headers = {
        'Authorization': f'Ghost {token}',
        'Accept-Version': version,
        'Content-Type': 'application/json'
    }
    url = f'{admin_url}/ghost/api/admin/posts/{post_id}/'
    params = {}
    if send_email and newsletter_slug:
        params['newsletter'] = newsletter_slug
    body = {'posts': [ {'updated_at': updated_at, 'status': 'published', **({'email_only': True} if email_only else {})} ]}
    r = requests.put(url, headers=headers, params=params, json=body, timeout=30)
    r.raise_for_status()
    return r.json()['posts'][0]
