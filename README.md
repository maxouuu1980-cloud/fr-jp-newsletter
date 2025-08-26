# FR–JP Automated Newsletter (Mistral + GitHub Actions)

Ce dépôt génère automatiquement une newsletter bilingue (FR–JP) chaque semaine en utilisant **Mistral AI** via Python, publie le HTML dans `site/`, et fournit une **app Flask** avec paywall (Stripe) pour hébergement OVH/Azure/Google.

## Démarrage rapide
1. Créez un dépôt GitHub et poussez ces fichiers.
2. Dans **Settings → Secrets and variables → Actions**, ajoutez :
   - `MISTRAL_API_KEY` (clé Mistral)
   - `MAPS_EMBED_URL` (votre My Maps)
   - `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`
   - `APP_SECRET_KEY`
3. (Optionnel) Éditez `generator/sources.yml`.
4. Déclenchez le workflow **Actions** (ou attendez l’exécution hebdomadaire).
5. Déployez `app/app.py` (Flask) sur OVH/Azure/Google (Dockerfile fourni).
