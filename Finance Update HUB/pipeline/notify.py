"""Send a phone/tablet notification per new post, after the site is deployed.

Channels (each optional, enabled by its environment variables):
  ntfy      NTFY_TOPIC [, NTFY_SERVER, NTFY_TOKEN]   free push app for Android & iOS
  Telegram  TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID

Tapping the notification opens the post page directly: SITE_URL#/p/<id>.
"""
import os
import sys

import requests

from . import store


def post_url(site: str, pid: str) -> str:
    return f"{site.rstrip('/')}/#/p/{pid}"


def image_url(site: str, pid: str) -> str:
    return f"{site.rstrip('/')}/posts/{pid}.png"


def send_ntfy(post: dict, site: str) -> None:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    headers = {}
    if os.environ.get("NTFY_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['NTFY_TOKEN']}"
    body = {
        "topic": topic,
        "title": f"{post['regulator']} · {post['category']}",
        "message": post["headline"],
        "click": post_url(site, post["id"]),
        "attach": image_url(site, post["id"]),
        "filename": f"{post['id']}.png",
        "tags": ["bell"],
        "actions": [{"action": "view", "label": "Open post", "url": post_url(site, post["id"])}],
    }
    requests.post(server, json=body, headers=headers, timeout=20).raise_for_status()


def send_telegram(post: dict, site: str) -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    caption = f"<b>{post['regulator']} · {post['category']}</b>\n{post['headline']}"
    requests.post(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        json={
            "chat_id": chat,
            "photo": image_url(site, post["id"]),
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [[
                {"text": "Open post", "url": post_url(site, post["id"])}]]},
        },
        timeout=20,
    ).raise_for_status()


def main() -> int:
    site = os.environ.get("SITE_URL", "")
    posts = store.read_outbox()
    if not posts:
        print("Nothing new to notify.")
        return 0
    if not site:
        print("SITE_URL not set; cannot build links.")
        return 1
    failures = 0
    for post in posts:
        for sender in (send_ntfy, send_telegram):
            try:
                sender(post, site)
            except Exception as exc:
                failures += 1
                print(f"{sender.__name__} failed for {post['id']}: {exc}")
    print(f"Notified {len(posts)} post(s), {failures} failure(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
