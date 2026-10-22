"""Read/write the published data that the web app serves (everything lives under docs/)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DATA = DOCS / "data"
POSTS = DOCS / "posts"
FEED = DATA / "updates.json"
SEEN = DATA / "seen.json"
OUTBOX = ROOT / "out" / "new_items.json"  # not published; read by the notify step
MAX_FEED = 400
MAX_SEEN = 5000


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def load_seen() -> list[str]:
    return _load(SEEN, [])


def save_seen(seen: list[str]) -> None:
    _save(SEEN, seen[-MAX_SEEN:])


def load_feed() -> list[dict]:
    return _load(FEED, [])


def save_post(post: dict) -> None:
    _save(POSTS / f"{post['id']}.json", post)


def save_feed(feed: list[dict]) -> None:
    feed.sort(key=lambda p: p["created_at"], reverse=True)
    for old in feed[MAX_FEED:]:
        for ext in ("json", "png"):
            (POSTS / f"{old['id']}.{ext}").unlink(missing_ok=True)
    _save(FEED, feed[:MAX_FEED])


def remove_samples(feed: list[dict]) -> list[dict]:
    keep = []
    for p in feed:
        if p.get("sample"):
            for ext in ("json", "png"):
                (POSTS / f"{p['id']}.{ext}").unlink(missing_ok=True)
        else:
            keep.append(p)
    return keep


def feed_entry(post: dict) -> dict:
    """The small summary row shown in the list view."""
    keys = ("id", "regulator", "category", "headline", "reference", "issued_on",
            "created_at", "format", "source_domain", "source_type", "sample")
    return {k: post.get(k) for k in keys if k in post}


def write_outbox(posts: list[dict]) -> None:
    _save(OUTBOX, posts)


def read_outbox() -> list[dict]:
    return _load(OUTBOX, [])
