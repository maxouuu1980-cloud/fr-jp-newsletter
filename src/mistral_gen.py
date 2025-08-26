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

def generate_sections(items):
    client = Mistral(api_key=os.environ['MISTRAL_API_KEY'])
    resp = client.chat.complete(
        model=MODEL,
        messages=[
            {"role":"system","content": SYSTEM},
            {"role":"user","content": build_prompt(items)}
        ],
        temperature=0.3,
        max_tokens=1800
    )
    content = resp.choices[0].message.content
    m = re.search(r"\{[\s\S]*\}\s*$", content)
    raw = content if m is None else m.group(0)
    data = json.loads(raw)
    return data['sections']
