"""Collect candidate updates from official sources, judgment feeds and (as a fallback) news.

Source types (configured in config/sources.yaml):
  rss               any RSS/Atom feed (RBI, Indian Kanoon judgment feeds, ...)
  cbic              CBIC Tax Information Portal API: GST notifications & circulars with the PDF
  incometax_portal  Income Tax e-filing portal "Latest News": CBDT notifications/circulars + PDF
  google_news       Google News search; fallback for regulators whose sites block automation
  html              generic listing page + CSS selector
"""
import base64
import hashlib
import io
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urljoin, urlparse

import feedparser
import requests
import urllib3
from bs4 import BeautifulSoup

# Several government sites reject non-browser user agents.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/141.0 Safari/537.36 FinanceUpdateHub/1.0")
TIMEOUT = 30

# Hosts whose TLS certificate chain is incomplete (browsers repair it, Python can't).
# Only public documents are read from them. Filled from `verify_tls: false` in the config.
INSECURE_HOSTS: set[str] = set()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CBIC = "https://taxinformation.cbic.gov.in"
CBIC_DOWNLOAD = {"Notification": "cbic-notification-msts", "Circular": "cbic-circular-msts"}


@dataclass
class Item:
    source_id: str
    regulator: str
    title: str
    link: str            # page a reader should open
    published: str       # ISO date, may be ""
    snippet: str = ""
    doc_url: str = ""    # official document to read for the summary (PDF / page); defaults to link
    source_type: str = "news"  # official | judgment | news
    text_filter: str = ""      # regex the document must match 3+ times to be worth summarising

    @property
    def uid(self) -> str:
        # Normalised title catches the same story arriving from two feeds.
        key = re.sub(r"[^a-z0-9]+", " ", self.title.lower()).strip()
        return hashlib.sha1(key.encode()).hexdigest()[:12]


def _get(url: str, **kw) -> requests.Response:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT,
                        verify=urlparse(url).netloc not in INSECURE_HOSTS, **kw)
    resp.raise_for_status()
    return resp


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(html or "", "html.parser").get_text(" ")).strip()


def _date(text: str, fmts: tuple) -> str:
    for fmt in fmts:
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def _too_old(iso: str, settings: dict) -> bool:
    if not iso:
        return False
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings["max_age_days"])).date()
    return datetime.fromisoformat(iso).date() < cutoff


def _from_feed(src: dict, url: str, settings: dict) -> list[Item]:
    feed = feedparser.parse(_get(url).content)
    title_filter = re.compile(src["title_filter"], re.I) if src.get("title_filter") else None
    items = []
    for e in feed.entries[: settings["max_items_per_source"]]:
        title = _clean(e.get("title", ""))
        if title_filter and not title_filter.search(title):
            continue
        stamp = e.get("published_parsed") or e.get("updated_parsed")
        published = (datetime.fromtimestamp(time.mktime(stamp), timezone.utc).date().isoformat()
                     if stamp else "")
        if not published:  # Indian Kanoon titles end with "on 14 October, 2026"
            m = re.search(r"on (\d{1,2} \w+, \d{4})\s*$", title)
            published = _date(m.group(1), ("%d %B, %Y",)) if m else ""
        if _too_old(published, settings):
            continue
        snippet = _clean(e.get("summary", ""))
        if e.get("source", {}).get("title"):
            snippet = f"{snippet} (Reported by {e.source.title})".strip()
        items.append(Item(src["id"], src["regulator"], title, e.get("link", ""), published,
                          snippet[:1500], source_type=src["source_type"],
                          text_filter=src.get("text_filter", "")))
    return items


def _from_cbic(src: dict, settings: dict) -> list[Item]:
    """Latest GST notifications & circulars from the CBIC Tax Information Portal's own API."""
    rows = _get(f"{CBIC}/api/cbic-notification-msts/fetchUpdatesByTaxId/{src.get('tax_id', 1000001)}").json()
    items = []
    for r in rows[: settings["max_items_per_source"]]:
        published = _date(r.get("updatedDate") or "", ("%d-%b-%Y",))
        if _too_old(published, settings):
            continue
        kind = r.get("updateType") or ""
        number = r.get("notificationNo") or ""
        title = f"{kind} No. {number}: {r.get('notificationName', '')}".strip()
        api = CBIC_DOWNLOAD.get(kind)
        items.append(Item(
            src["id"], src["regulator"], title,
            link=f"{CBIC}/view-pdf/{r['id']}/ENG/{kind}s",
            published=published,
            snippet=f"{r.get('updateCategory', '')}: {r.get('notificationName', '')}",
            doc_url=f"{CBIC}/api/{api}/download/{r['id']}/ENG" if api else "",
            source_type="official",
        ))
    return items


def _from_incometax_portal(src: dict, settings: dict) -> list[Item]:
    """CBDT notifications/circulars announced on the Income Tax e-filing portal's Latest News."""
    url = src.get("url", "https://www.incometax.gov.in/iec/foportal/latest-news")
    soup = BeautifulSoup(_get(url).text, "html.parser")
    items = []
    for row in soup.select("div.views-row")[: settings["max_items_per_source"]]:
        text = _clean(str(row))
        m = re.match(r"(\d{2}-[A-Za-z]{3}-\d{4})\s+(.*)", text)
        if not m:
            continue
        published, body = _date(m.group(1), ("%d-%b-%Y",)), m.group(2).replace("Click here", "").strip()
        if _too_old(published, settings):
            continue
        doc = next((urljoin(url, a["href"]) for a in row.select("a[href]")
                    if a["href"].lower().endswith(".pdf")), "")
        items.append(Item(src["id"], src["regulator"], body[:300], link=doc or url,
                          published=published, snippet=body, doc_url=doc,
                          source_type="official"))
    return items


def _from_html(src: dict, settings: dict) -> list[Item]:
    soup = BeautifulSoup(_get(src["url"]).text, "html.parser")
    items = []
    for a in soup.select(src["selector"])[: settings["max_items_per_source"]]:
        title = _clean(a.get_text())
        if len(title) < 8:
            continue
        items.append(Item(src["id"], src["regulator"], title, urljoin(src["url"], a["href"]), "",
                          source_type=src["source_type"]))
    return items


def fetch_source(src: dict, settings: dict) -> list[Item]:
    # A source may override the global age limit (judgments are uploaded days after the decision).
    settings = {**settings, "max_age_days": src.get("max_age_days", settings["max_age_days"])}
    kind = src["type"]
    src.setdefault("source_type", "news" if kind == "google_news" else "official")
    if src.get("verify_tls") is False and src.get("url"):
        INSECURE_HOSTS.add(urlparse(src["url"]).netloc)
    if kind == "rss":
        return _from_feed(src, src["url"], settings)
    if kind == "cbic":
        INSECURE_HOSTS.add(urlparse(CBIC).netloc)
        return _from_cbic(src, settings)
    if kind == "incometax_portal":
        return _from_incometax_portal(src, settings)
    if kind == "google_news":
        url = ("https://news.google.com/rss/search?q=" + quote_plus(src["query"] + " when:7d")
               + "&hl=en-IN&gl=IN&ceid=IN:en")
        return _from_feed(src, url, settings)
    if kind == "html":
        return _from_html(src, settings)
    raise ValueError(f"Unknown source type {kind!r} in {src['id']}")


def fetch_all(cfg: dict) -> list[Item]:
    items: list[Item] = []
    for src in cfg["sources"]:
        if src.get("enabled") is False:
            continue
        try:
            found = fetch_source(src, cfg["settings"])
            print(f"  {src['id']}: {len(found)} items")
            items.extend(found)
        except Exception as exc:  # one broken source must not stop the run
            print(f"  {src['id']}: FAILED ({exc})")
    return items


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return " ".join((p.extract_text() or "") for p in reader.pages[:12])


def fetch_full_text(item: Item, limit: int = 18000) -> str:
    """Text of the official document (or linked page). Empty string if unavailable."""
    url = item.doc_url or item.link
    if not url or urlparse(url).netloc.endswith("news.google.com"):
        return ""  # Google News links are JS redirects; the snippet is all we get
    try:
        resp = _get(url)
        ctype = resp.headers.get("content-type", "")
        if "json" in ctype:  # CBIC returns {"data": "<base64 PDF>", "fileName": ...}
            text = _pdf_text(base64.b64decode(resp.json()["data"]))
        elif "pdf" in ctype or url.lower().endswith(".pdf"):
            text = _pdf_text(resp.content)
        else:
            soup = BeautifulSoup(resp.text, "html.parser")
            body = soup.select_one("div.judgments") or soup  # Indian Kanoon judgment body
            for tag in body(["script", "style", "nav", "header", "footer", "noscript"]):
                tag.decompose()
            text = body.get_text(" ")
    except Exception as exc:
        print(f"    could not read document ({exc.__class__.__name__})")
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        # Keep the opening (facts, issue) and the end (holding, order) of long documents.
        head = int(limit * 0.6)
        text = text[:head] + " [...] " + text[-(limit - head):]
    return text
