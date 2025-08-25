# FR–JP Newsletter – Automation Pack

This pack generates a monthly bilingual (FR–JP) newsletter and can email it to Substack via your secret email-to-post.
## Steps
1) `python -m venv .venv && source .venv/bin/activate`
2) `pip install -r requirements.txt`
3) `cp config.example.toml config.toml` then edit keys (OpenAI, DeepL optional, Unsplash optional, Substack email + SMTP).
4) Run: `python generate_newsletter.py --config config.toml`
Output goes to `out/`.
### Cron (1st day 10:00 monthly)
`0 10 1 * * /path/to/.venv/bin/python /path/to/generate_newsletter.py --config /path/to/config.toml >> /path/to/newsletter.log 2>&1`
