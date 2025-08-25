# Substack Monthly Automation (Mistral-only AI)

Pipeline to auto-generate a **bilingual FR–JP** newsletter (gastronomy, craft, sustainable design)
every month using **Mistral AI** only, and publish to **Substack** via GitHub Actions.

## Overview

1. **Collect** fresh items (RSS or curated sources) → `data/collected_YYYYMMDD.json`
2. **Generate** structured picks + HTML with Mistral (`mistral-large-2407`) → `out/newsletter_post.html`
3. **Publish** to Substack (draft or publish) via `python-substack-tarun` wrapper.

> ⚠️ The Substack API wrapper is **unofficial**. Use at your own risk and check Substack's Terms. Alternatively, publish as a draft and click "Publish" manually.

## Secrets (GitHub Actions)

- `MISTRAL_API_KEY` — from https://console.mistral.ai
- `SUBSTACK_BASE_URL` — e.g., `https://yourpub.substack.com`
- `SUBSTACK_EMAIL` and `SUBSTACK_PASSWORD` — account with posting rights
- (optional) `CUSTOM_FEEDS_JSON` — JSON array of RSS URLs

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.collect_sources  # writes data/collected_YYYYMMDD.json
python -m src.generate_issue data/collected_YYYYMMDD.json  # writes out/newsletter_post.html
python -m src.publish_substack out/newsletter_post.html "Art de Vivre Durable — $(date +'%B %Y')" draft
```

## GitHub Actions

Monthly schedule at 09:00 Europe/Paris on the 1st of each month.
- Collect → Generate via Mistral → Publish draft on Substack.

You can switch to `publish` by editing the workflow `SUBSTACK_STATUS` env var.
