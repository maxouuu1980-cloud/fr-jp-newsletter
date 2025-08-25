"""
Collects candidate links / items from RSS feeds or static lists.
No AI here — just harvesting data; AI summarization occurs in generate_issue.py (Mistral).
"""
import feedparser, json, pathlib, datetime as dt
from typing import List, Dict

DEFAULT_FEEDS = [
    "https://www.timeout.com/kyoto/food-drink/rss",
    "https://www.timeout.com/tokyo/shopping/rss",
    "https://www.dezeen.com/feed/",
]

def collect(feeds: List[str]=None, limit:int=30) -> List[Dict]:
    feeds = feeds or DEFAULT_FEEDS
    items: List[Dict] = []
    for url in feeds:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:limit]:
                items.append({
                    "title": getattr(e, "title", ""),
                    "link": getattr(e, "link", ""),
                    "summary": getattr(e, "summary", ""),
                    "published": getattr(e, "published", ""),
                    "source": url,
                })
        except Exception:
            pass
    dedup = {}
    for it in items:
        if it["link"] and it["link"] not in dedup:
            dedup[it["link"]] = it
    return list(dedup.values())

if __name__ == "__main__":
    data = collect()
    out = pathlib.Path("data")
    out.mkdir(exist_ok=True, parents=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%d")
    path = out / f"collected_{ts}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Wrote {path}")
