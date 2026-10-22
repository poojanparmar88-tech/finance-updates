"""One pipeline run: fetch -> dedupe -> summarise -> render -> publish data -> queue notifications.

  python -m pipeline.run            real run (needs ANTHROPIC_API_KEY)
  python -m pipeline.run --samples  write illustrative sample posts, no network or API key
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

from . import store
from .fetch import fetch_all, fetch_full_text
from .render import render_post

CONFIG = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"
SAMPLES = Path(__file__).resolve().parent / "samples.json"


def build_post(uid: str, data: dict, link: str, title: str, source_type: str) -> dict:
    now = datetime.now(timezone.utc)
    domain = urlparse(link).netloc.removeprefix("www.")
    return {
        **data,
        "id": f"{now:%Y%m%d}-{uid}",
        "created_at": now.isoformat(timespec="seconds"),
        "source_url": link,
        "source_title": title,
        "source_domain": domain,
        "source_type": source_type,
    }


def publish(posts: list[dict], cfg: dict) -> None:
    # Samples are dropped on every run: a live run replaces them, a sample run rewrites them.
    feed = store.remove_samples(store.load_feed())
    handle = cfg["settings"]["brand_handle"]
    for post in posts:
        render_post(post, store.POSTS / f"{post['id']}.png", handle)
        store.save_post(post)
        feed.append(store.feed_entry(post))
    store.save_feed(feed)
    store.write_outbox([store.feed_entry(p) for p in posts])


def run_samples(cfg: dict) -> list[dict]:
    posts = []
    for i, s in enumerate(json.loads(SAMPLES.read_text(encoding="utf-8"))):
        post = build_post(f"sample{i}", s, "https://example.com", s["headline"], "official")
        post["sample"] = True
        posts.append(post)
    return posts


def run_live(cfg: dict) -> list[dict]:
    from .summarise import summarise  # imported here so --samples needs no API key

    print("Fetching sources…")
    items = fetch_all(cfg)
    seen = store.load_seen()
    seen_set = set(seen)
    fresh, batch_ids = [], set()
    for it in items:
        if it.uid not in seen_set and it.uid not in batch_ids and it.title:
            fresh.append(it)
            batch_ids.add(it.uid)
    # Take items from each source in turn so a busy source can't use up the whole per-run cap.
    queues: dict[str, list] = {}
    for it in fresh:
        queues.setdefault(it.source_id, []).append(it)
    fresh = [q[i] for i in range(max(map(len, queues.values()), default=0))
             for q in queues.values() if i < len(q)]
    fresh = fresh[: cfg["settings"]["max_new_per_run"]]
    print(f"{len(items)} fetched, {len(fresh)} new to process")

    posts = []
    for it in fresh:
        print(f"- [{it.regulator} / {it.source_type}] {it.title[:90]}")
        text = fetch_full_text(it)
        if it.text_filter and len(re.findall(it.text_filter, text, re.I)) < 3:
            seen.append(it.uid)  # e.g. a criminal or service-law judgment: skip without a Claude call
            print("    not about tax/corporate/banking law, skipped")
            continue
        try:
            data = summarise(it, text)
        except Exception as exc:
            print(f"    error: {exc}")  # left unseen so the next run retries it
            continue
        seen.append(it.uid)
        if not data or not data.get("relevant"):
            print("    not a regulatory update, skipped")
            continue
        posts.append(build_post(it.uid, data, it.link, it.title, it.source_type))
    store.save_seen(seen)
    return posts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", action="store_true", help="write sample posts only")
    args = ap.parse_args()
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    posts = run_samples(cfg) if args.samples else run_live(cfg)
    publish(posts, cfg)
    print(f"Published {len(posts)} post(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
