import os, json, re
from mistralai import Mistral

MODEL = os.getenv('MISTRAL_MODEL', 'mistral-large-latest')

SYSTEM = """Tu es un rédacteur franco-japonais expert en gastronomie, artisanat et design durable.
- Style : informatif, concis, élégant.
- Sortie bilingue FR / JP.
- NE PAS inventer d'adresses/prix : si inconnus dans les extraits fournis, mettre 'TBD'.
- Retourne STRICTEMENT un JSON valide suivant ce schéma :
{
  "sections": [
    {
      "heading": "Titre de section",
      "fr": "Paragraphe FR en HTML léger (<a> autorisé)",
      "jp": "Paragraphe JP en HTML léger",
      "places": [
        {"name":"...", "city":"...", "address":"TBD|...", "price":"TBD|...", "map_url":"TBD|https://..."}
      ],
      "sources": [{"title":"...", "url":"..."}]
    }
  ]
}
"""

def build_prompt(items):
    intro = "Voici une sélection d'articles récents (titre, résumé, URL) :\n\n"
    for i, it in enumerate(items, 1):
        intro += f"[{i}] ({it['category']}) {it['title']}\n{it['summary'][:400]}\nURL: {it['link']}\n\n"
    intro += "Produis 3 à 5 sections thématiques maximum en respectant le schéma JSON."
    return intro

def _safe_json(content: str):
    """
    Essaie d'extraire un JSON valide ; sinon lève ValueError.
    """
    # Si le modèle respecte 'json_object', on reçoit déjà un JSON pur.
    content = content.strip()
    # Tentative directe
    try:
        return json.loads(content)
    except Exception:
        pass
    # Tentative: chercher un bloc JSON
    m = re.search(r"\{[\s\S]*\}\s*$", content)
    if m:
        return json.loads(m.group(0))
    raise ValueError("Réponse non-JSON")

def generate_sections(items):
    client = Mistral(api_key=os.environ['MISTRAL_API_KEY'])
    # Active le mode JSON strict (supporté par Mistral)
    resp = client.chat.complete(
        model=MODEL,
        messages=[
            {"role":"system","content": SYSTEM},
            {"role":"user","content": build_prompt(items)}
        ],
        temperature=0.3,
        max_tokens=1800,
        response_format={"type": "json_object"}  # <-- clé pour recevoir un JSON propre
    )
    content = resp.choices[0].message.content
    try:
        data = _safe_json(content)
        sections = data.get('sections') or []
        # garde-fou : liste vide -> fallback minimal
        if not sections:
            raise ValueError("Sections vides")
        return sections
    except Exception:
        # Fallback ultra-simple : on crée 1 section basée sur les items
        fallback = [{
            "heading": "Sélection FR・JP",
            "fr": "Aperçu mensuel généré automatiquement à partir des sources. Vérifier les détails avant publication.",
            "jp": "情報元から自動生成した月次プレビューです。公開前に内容をご確認ください。",
            "places": [],
            "sources": [{"title": it["title"], "url": it["link"]} for it in items[:6]]
        }]
        return fallback
