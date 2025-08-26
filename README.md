# FR–JP Newsletter Bot (Ghost + Mistral + GitHub Actions)

Automatisez **chaque mois** la génération d’une newsletter bilingue **FR/JP** avec **Mistral AI** et la publication **sur Ghost** (brouillon ou publication + envoi email), orchestrée par **GitHub Actions**.

> L’IA générative provient **exclusivement de Mistral AI** (SDK `mistralai`).

## Prérequis (clic par clic)

### Ghost (clé Admin API + newsletter)
1. Ghost Admin → **Settings → Integrations → Add custom integration** (*Monthly AI Bot*).
2. Copiez l’**Admin API Key** (format `id:secret`) et l’URL admin (ex. `https://votresite.ghost.io`). 
3. (Facultatif) **Settings → Newsletters → New newsletter** et notez le **slug**.
4. Vérifiez la configuration d’**Email** (Settings → Email).

### Mistral AI (clé API)
1. Ouvrez **console.mistral.ai → API Keys → Create new key** et copiez la clé.

### GitHub (repo + secrets)
1. Créez un **nouveau dépôt** et uploadez ce dossier.
2. **Settings → Secrets and variables → Actions → New repository secret** :  
   - `MISTRAL_API_KEY`  
   - `GHOST_ADMIN_URL` (ex. `https://votresite.ghost.io`)  
   - `GHOST_ADMIN_API_KEY` (`id:secret`)  
   - `GHOST_NEWSLETTER_SLUG` (optionnel)  
   - `PUBLISH_MODE` = `draft` (défaut) ou `publish`  
3. **Actions** : autorisez le workflow si demandé.

## Lancer en local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' config/settings.example.env | xargs -d '
')
python -m src.build --month "$(date +%Y-%m)"
```

## Ce que fait le pipeline
1. **Collecte** des nouveautés via RSS/Atom (`config/sources.yml`).
2. **Déduplication** (`state/seen.json`).
3. **Génération** bilingue via **Mistral** (JSON structuré).
4. **Rendu** HTML (Jinja2 → `templates/newsletter.html.j2`).
5. **Publication** sur Ghost : brouillon par défaut, ou **publication + email** si `PUBLISH_MODE=publish` et `GHOST_NEWSLETTER_SLUG` défini.

> Le générateur n’invente pas d’adresses/prix : s’ils ne sont pas dans les sources, il affiche `TBD`.

## Dépannage
- **Invalid token** : format `id:secret`, horloge système, header `Authorization: Ghost <JWT>`.
- **403** : domaine admin incorrect ou clé invalide.
- **Aucun email** : passer `?newsletter=<slug>` lors de la publication et vérifier les réglages email.
- **Peu de contenu** : ajoutez des flux dans `config/sources.yml` ou augmentez `MAX_ITEMS`.

