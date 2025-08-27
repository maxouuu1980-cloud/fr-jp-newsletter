import os, json, datetime, pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from mistralai import Mistral

MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
FALLBACKS = [m.strip() for m in os.getenv("MISTRAL_MODEL_FALLBACK", "open-mixtral-8x7b,ministral-8b-latest").split(",") if m.strip()]
API_KEY = os.getenv("MISTRAL_API_KEY")
MAPS_EMBED_URL = os.getenv("MAPS_EMBED_URL", "")

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "generator" / "templates"
SITE = ROOT / "site"

if not API_KEY:
    raise SystemExit("Missing MISTRAL_API_KEY")

client = Mistral(api_key=API_KEY)
env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html","xml"]))

def _call_llm_once(model: str, prompt: str, temperature: float = 0.7, max_tokens: int = 900) -> str:
    resp = client.chat.complete(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content

def llm(prompt: str) -> str:
    """
    Appel Mistral avec retries + fallbacks (tous services Mistral).
    Gère les erreurs 429 capacity/rate limit et autres erreurs transitoires.
    """
    models_to_try = [MODEL] + FALLBACKS
    last_err = None
    for model in models_to_try:
        # 5 tentatives par modèle avec backoff exponentiel + jitter
        for attempt in range(5):
            try:
                return _call_llm_once(model, prompt, temperature=0.7, max_tokens=900)
            except Exception as e:
                msg = str(e).lower()
                # 429 / capacity / rate limit → retry
                is_capacity = ("429" in msg) or ("capacity" in msg) or ("rate limit" in msg) or ("service_tier_capacity_exceeded" in msg)
                # autres erreurs réseau transitoires possibles → retry léger
                is_transient = any(k in msg for k in ["timeout", "temporarily", "unavailable", "connection reset"])
                if is_capacity or is_transient:
                    sleep_s = min(60, (2 ** attempt) + random.uniform(0, 1.0))
                    time.sleep(sleep_s)
                    continue
                # sinon on arrête ce modèle et on essaie le suivant
                last_err = e
                break
        # si on arrive ici, ce modèle n'a pas abouti → on tente le suivant
        last_err = last_err or Exception(f"Echec sur modèle {model}")
        continue
    # Tous les modèles ont échoué
    raise last_err or Exception("Mistral: impossible d'obtenir une réponse après retries.")

def gen_section(city_hint, category, url_hint):
    prompt = f"""
Tu es un rédacteur bilingue FR–JP expert de {category}.
Génère deux résumés concis (FR puis JP) sur un lieu/marque/atelier pertinent à {city_hint},
incluant : description, intérêt durable, deux points différenciants, et une phrase engageante.
Ne crée pas d'adresse fictive ; si tu n'es pas sûr, reste descriptif sans adresse.
Réponds en JSON avec les clés:
"title_fr","body_fr","title_jp","body_jp",
"address","address_jp","price","price_jp","url".
Tu peux t'inspirer implicitement de {url_hint}.
"""
    txt = llm(prompt)
    try:
        data = json.loads(txt.strip("` \n"))
    except Exception:
        data = {
            "title_fr": f"{category} – {city_hint}",
            "body_fr": txt,
            "title_jp": f"{category}（{city_hint}）",
            "body_jp": txt,
            "address": "", "address_jp": "", "price": "", "price_jp": "", "url": url_hint
        }
    for k in ["address","address_jp","price","price_jp","url"]:
        data.setdefault(k,"")
    return data

def main():
    today = datetime.date.today()
    date_str = today.strftime("%Y-%m-%d")

    intro_fr = llm("Écris un édito court (80-120 mots) en français sur les ponts FR–JP : gastronomie, artisanat, design durable, ton chaleureux et premium.")
    intro_jp = llm("フランスと日本のガストロノミー・工芸・サステナブルデザインの橋渡しを描く短い序文（80-120語）を、温かく上質なトーンで。")

    gastronomie = gen_section("Kyoto", "gastronomie (kaiseki, saké, produits locaux)", "https://www.kyoto.travel/")
    artisanat  = gen_section("Arita", "artisanat (porcelaine, savoir-faire traditionnel)", "https://www.arita.jp/")
    design     = gen_section("Paris", "design durable (réemploi, artisanat d'art)", "https://www.lareservedesarts.org/")

    template = env.get_template("newsletter.html")
    html = template.render(
        title=f"Newsletter FR–JP — {date_str}",
        subtitle="Gastronomie・Artisanat・Design",
        year=today.year,
        date_str=date_str,
        intro_fr=intro_fr,
        intro_jp=intro_jp,
        gastronomie=gastronomie,
        artisanat=artisanat,
        design=design,
        maps_embed_url=MAPS_EMBED_URL,
    )

    out_dir = SITE / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")

    issues = sorted([p.name for p in SITE.iterdir() if p.is_dir()], reverse=True)
    index = ["<h1>Archives – FR–JP Newsletter</h1><ul>"]
    for issue in issues:
        index.append(f'<li><a href="{issue}/index.html">{issue}</a></li>')
    index.append("</ul>")
    (SITE / "index.html").write_text("\n".join(index), encoding="utf-8")

if __name__ == "__main__":
    main()
