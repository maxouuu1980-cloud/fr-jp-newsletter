"""
Uses Mistral AI to (a) pick fresh items, (b) extract practical info (addresses, prices if present), 
(c) write a bilingual FR/JP newsletter sectioned HTML from a Jinja template.
"""
import json, pathlib, datetime as dt, os
from typing import List, Dict
from mistralai import Mistral
from jinja2 import Environment, FileSystemLoader, select_autoescape
from src.utils import get_env, setup_logging

SECTION_SYSTEM_PROMPT = """Tu es un rédacteur expert bilingue FR–JP spécialisé en gastronomie, artisanat, design durable.
Tu écris un numéro de newsletter concis et pratique : adresses, heures, prix quand disponibles, liens.
Ne fabrique pas d'informations non présentes dans les sources : si une donnée manque, écris 'N.C.'.
Retourne du HTML minimal compatible e-mail, avec segments FR et JP.
"""

ITEM_USER_PROMPT = """Sources candidates (JSON):
{{ items_json }}

Objectif:
1) Sélectionner 6 à 9 éléments {gastronomie=2-3, artisanat=2-3, design=2-3} pertinents France/Japon.
2) Pour chaque élément, extraire: titre, 2-3 phrases FR, 2-3 phrases JP, adresse (si disponible), prix (si disponible), lien.
3) Indiquer la ville/pays et tag {Gastronomie|Artisanat|Design}.
4) Retour: JSON strict, champ 'items' = liste d'objets structurés.

Rappels:
- Ne pas inventer; si adresse/prix absents -> "N.C.".
- Utiliser du japonais naturel pour JP, français naturel pour FR.
"""

POST_USER_PROMPT = """À partir du JSON structuré ci-dessous, génère le corps HTML de la newsletter:
- Titre h2 FR/JP
- Sections: Gastronomie / Artisanat / Design
- Pour chaque item: bloc FR puis bloc JP + méta (adresse, prix, lien)
- Ajoute un encart "Carte / 地図" avec un placeholder d'iframe My Maps

JSON:
{{ structured_json }}
"""

def mistral_client():
    key = get_env("MISTRAL_API_KEY")
    return Mistral(api_key=key)

def chat(client: Mistral, model: str, system: str, user: str) -> str:
    resp = client.chat.complete(model=model, messages=[
        {"role":"system","content":system},
        {"role":"user","content":user},
    ])
    return resp.choices[0].message.content

def main(collected_path: str, out_dir: str="out", model: str="mistral-large-2407"):
    setup_logging()
    client = mistral_client()
    items = json.loads(pathlib.Path(collected_path).read_text(encoding="utf-8"))
    user_1 = ITEM_USER_PROMPT.replace("{{ items_json }}", json.dumps(items, ensure_ascii=False))
    structured = chat(client, model, SECTION_SYSTEM_PROMPT, user_1)
    user_2 = POST_USER_PROMPT.replace("{{ structured_json }}", structured)
    html_body = chat(client, model, SECTION_SYSTEM_PROMPT, user_2)

    env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape(['html']))
    tpl = env.get_template("post_template.html")
    today = dt.date.today().strftime("%B %Y")
    full_html = tpl.render(title=f"Art de Vivre Durable — {today}", html_body=html_body)

    os.makedirs(out_dir, exist_ok=True)
    out = pathlib.Path(out_dir) / "newsletter_post.html"
    out.write_text(full_html, encoding="utf-8")
    (pathlib.Path(out_dir) / "structured.json").write_text(structured, encoding="utf-8")
    print(str(out))

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.generate_issue data/collected_YYYYMMDD.json [out_dir]")
        raise SystemExit(1)
    main(sys.argv[1], out_dir=sys.argv[2] if len(sys.argv)>2 else "out")
