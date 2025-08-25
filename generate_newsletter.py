#!/usr/bin/env python3
import argparse, os, sys, smtplib, ssl, requests, feedparser, toml
from datetime import datetime, timedelta
from dateutil import parser as dtparser
from jinja2 import Environment, FileSystemLoader, select_autoescape
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    import deepl
except Exception:
    deepl = None

def dbg(msg): print(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] {msg}")

def load_config(path):
    with open(path,"r",encoding="utf-8") as f: return toml.load(f)

def ensure_dir(d): os.makedirs(d, exist_ok=True)

def fetch_rss_entries(urls, days=60, max_items=200):
    cutoff = datetime.utcnow() - timedelta(days=days)
    out = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:max_items]:
                published = None
                for key in ("published","updated","created"):
                    if key in e:
                        try:
                            published = dtparser.parse(getattr(e,key)); break
                        except Exception: pass
                if not published: published = datetime.utcnow()
                if published.replace(tzinfo=None) < cutoff: continue
                out.append({
                    "title": e.get("title",""),
                    "link": e.get("link",""),
                    "summary": e.get("summary",""),
                    "published": str(published),
                    "source": url
                })
        except Exception as ex:
            dbg(f"RSS error {url}: {ex}")
    return out

def unsplash_image(query, key):
    if not key: return None
    try:
        r = requests.get("https://api.unsplash.com/photos/random",
            params={"query":query,"orientation":"landscape","content_filter":"high"},
            headers={"Authorization":f"Client-ID {key}"}, timeout=15)
        if r.ok: return r.json().get("urls",{}).get("regular")
    except Exception as ex: dbg(f"Unsplash error: {ex}")
    return None

def openai_client(api_key):
    if not OpenAI: raise RuntimeError("OpenAI SDK not installed")
    return OpenAI(api_key=api_key)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def ai_select(client, model, themes, per_theme, rss_items):
    prompt = f"""
You are an editor for a FR–JP newsletter (gastronomy, crafts, sustainable design).
Pick up to {per_theme} items per theme from the RSS list.
Prefer concrete places/events with addresses or practical info.
Return strict JSON:
{{"blocks":[{{"theme":"gastronomie","items":[{{"title":"","url":"","address":"","price":"","angle_fr":"","angle_en":""}}]}}]}}
RSS JSON:
{rss_items}
"""
    resp = client.chat.completions.create(
        model=model, temperature=0.4,
        response_format={"type":"json_object"},
        messages=[
            {"role":"system","content":"Output JSON only."},
            {"role":"user","content":prompt}
        ]
    )
    import json
    return json.loads(resp.choices[0].message.content)

def translate(text, target_lang, deepl_key=None, openai_cli=None, openai_model=None):
    if not text: return ""
    if deepl_key and deepl:
        try:
            tr = deepl.Translator(deepl_key)
            return tr.translate_text(text, target_lang=target_lang).text
        except Exception as ex: dbg(f"DeepL error: {ex}")
    if openai_cli:
        resp = openai_cli.chat.completions.create(
            model=openai_model, temperature=0.2,
            messages=[{"role":"system","content":"Translate preserving culinary/craft terminology."},
                      {"role":"user","content":f"Translate to {target_lang}: {text}"}])
        return resp.choices[0].message.content
    return text

def render_html(template_dir, template_name, context, outpath):
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html"]))
    html = env.get_template(template_name).render(**context)
    with open(outpath,"w",encoding="utf-8") as f: f.write(html)
    return outpath

def send_email_html(smtp_host, smtp_port, smtp_user, smtp_pass, from_email, to_email, subject, html_body):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject; msg["From"] = from_email; msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", _charset="utf-8"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=ctx); server.login(smtp_user, smtp_pass); server.sendmail(from_email, [to_email], msg.as_string())

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True); args = ap.parse_args()
    cfg = load_config(args.config)
    outdir = cfg.get("run",{}).get("output_dir","out"); ensure_dir(outdir)

    rss_urls = cfg.get("content",{}).get("rss_feeds",[])
    per_theme = int(cfg.get("content",{}).get("items_per_theme",4))
    themes = cfg.get("content",{}).get("themes",["gastronomie","artisanat","design durable"])
    rss_items = fetch_rss_entries(rss_urls, days=60, max_items=200); dbg(f"Fetched {len(rss_items)} RSS items")

    openai_key = cfg.get("ai",{}).get("openai_api_key",""); openai_model = cfg.get("ai",{}).get("openai_model","gpt-4o-mini")
    if not openai_key: raise SystemExit("Missing OpenAI key")
    cli = openai_client(openai_key)
    selection = ai_select(cli, openai_model, themes, per_theme, rss_items)
    blocks = selection.get("blocks", [])

    deepl_key = cfg.get("ai",{}).get("deepl_api_key","")
    for block in blocks:
        for it in block.get("items",[]):
            fr = it.get("angle_fr") or it.get("angle_en") or it.get("title","")
            jp = translate(it.get("angle_en") or fr, "JA", deepl_key=deepl_key, openai_cli=cli, openai_model=openai_model)
            it["text_fr"] = fr; it["text_jp"] = jp
            it["address"] = it.get("address",""); it["price"] = it.get("price",""); it["url"] = it.get("url","")

    unsplash_key = cfg.get("apis",{}).get("unsplash_access_key","")
    theme_queries = cfg.get("content",{}).get("unsplash_queries",{})
    for block in blocks:
        theme = block.get("theme","").lower(); queries = theme_queries.get(theme, []) if isinstance(theme_queries, dict) else []
        qi = 0
        for it in block.get("items",[]):
            img = None
            if unsplash_key and queries:
                q = queries[qi % len(queries)]; img = unsplash_image(q, unsplash_key); qi += 1
            it["image_url"] = img or "https://images.unsplash.com/photo-1498654077810-12f23ab7ae6e?q=80&w=1600&auto=format&fit=crop"

    today = datetime.now()
    title = f"Art de Vivre Durable – FR・JP #{today.strftime('%Y.%m')}"
    subtitle = f"Gastronomie・Artisanat・Design – {today.strftime('%B %Y')}"

    context = {
        "title": title, "subtitle": subtitle,
        "intro_fr": "Notre sélection franco-japonaise du mois, entre tables inspirantes, ateliers d’exception et design durable.",
        "intro_jp": "今月のおすすめ：美食、工芸、サステナブル・デザインを横断する日仏セレクション。",
        "cover_image": "https://images.unsplash.com/photo-1542838132-92c53300491e?q=80&w=1600&auto=format&fit=crop",
        "blocks": [{"kicker": (b.get("theme") or "").title(), "title": (b.get("theme") or "").title(), "items": b.get("items", [])} for b in blocks],
        "mymaps_embed_url": "https://www.google.com/maps/d/embed?mid=YOUR_MYMAPS_ID_HERE",
        "subscribe_url": "https://your-substack-url.example.com/subscribe"
    }

    tpl_dir = os.path.join(os.path.dirname(__file__), "templates")
    outname = f"newsletter_{today.strftime('%Y_%m')}.html"
    outpath = os.path.join(outdir, outname); os.makedirs(os.path.dirname(outpath), exist_ok=True)
    render_html(tpl_dir, "newsletter_template.html", context, outpath)
    dbg(f"Rendered → {outpath}")

    if cfg.get("run",{}).get("send_email", False):
        with open(outpath,"r",encoding="utf-8") as f: html_body = f.read()
        subj = cfg.get("run",{}).get("subject_prefix","") + title
        em = cfg.get("email",{})
        to = em.get("substack_post_email","")
        if not to: dbg("send_email=true but substack_post_email is empty; skip email")
        else:
            dbg("Emailing Substack…")
            send_email_html(em.get("smtp_host","smtp.gmail.com"), int(em.get("smtp_port",587)),
                            em.get("smtp_user",""), em.get("smtp_pass",""),
                            em.get("from_email",""), to, subj, html_body)
            dbg("Email sent.")

if __name__ == "__main__":
    main()
