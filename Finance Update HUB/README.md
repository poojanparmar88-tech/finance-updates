# Finance Update Hub

An automated cloud workflow that watches **Income Tax (CBDT), GST (CBIC), MCA, RBI, the Supreme Court and the High Courts**, and for every new update:

1. writes a summary, or a table when the content is tabular (rates, due dates, old vs new),
2. creates a ready-to-post **1080×1350 social media image** plus LinkedIn / Instagram / X / WhatsApp captions,
3. saves everything to your **GitHub repository** (your cloud storage) and publishes it to a mobile web app,
4. sends a **push notification** to your phone or tablet. Tapping it opens that post, where **Save image** downloads it to the device.

```
GitHub Actions (every 2 h)                                        Your phone / tablet
┌─────────────────────────────────────────────────────────┐
│ fetch feeds → drop duplicates → Claude summary + captions│
│ → render PNG → commit to repo → deploy GitHub Pages ─────┼──► web app (installable)
│ → notification (ntfy / Telegram) ────────────────────────┼──► tap → opens the post → Save / Share
└─────────────────────────────────────────────────────────┘
```

Nothing runs on your computer. Everything runs on GitHub's servers on a schedule.

## Where the updates come from

Summaries are written from the **actual document** wherever the regulator allows automated access:

| Regulator | Source | What Claude reads | Badge in app |
|---|---|---|---|
| RBI | rbi.org.in official RSS feeds | the notification / press release page | Official source |
| Income Tax (CBDT) | Income Tax Dept e-filing portal, *Latest News* (incometax.gov.in) | the official notification / circular **PDF** | Official source |
| GST (CBIC) | CBIC Tax Information Portal API (taxinformation.cbic.gov.in) | the official notification / circular **PDF** | Official source |
| Supreme Court | Indian Kanoon court feed | the **full judgment text** | Judgment text |
| High Courts (Delhi, Bombay, Gujarat, Karnataka, Madras, Calcutta, Allahabad, Kerala, Telangana, MP, Patna, Orissa) | Indian Kanoon court feeds | the **full judgment text** | Judgment text |
| MCA | Google News | the news headline and snippet only | News report |

- **Judgments are filtered before Claude is called.** The case title must name a tax, corporate or banking party, and the judgment text must cite tax or corporate law at least three times. Criminal, service and similar cases are skipped at no cost.
- **Why MCA uses news:** mca.gov.in, incometaxindia.gov.in and egazette.gov.in block automated access. They return "Access Denied" or redirect to the home page, even for a headless browser. MCA posts are therefore marked **News report** in the app and on the image, with a reminder to check the official notification. To add an official MCA source later, add an `rss` or `html` source in `config/sources.yaml`.
- CBIC's site and some other government sites have an incomplete TLS certificate chain, which browsers repair but Python can't. For those hosts the certificate check is skipped. Only public documents are read from them, and nothing is sent to them.

## Setup (about 15 minutes, one time)

### 1. Create the repository
- Sign in to github.com → **New repository** → name it e.g. `finance-updates` → **Public** (GitHub Pages is free for public repos; see *Privacy* below) → Create.
- Upload all files from this folder (**Add file → Upload files**, drag the whole folder in, including the `.github` folder).

### 2. Get a Claude API key
- console.anthropic.com → **API Keys** → Create key. Add a small amount of credit.
- Cost guide: each update is one Claude call. The workflow uses **Claude Sonnet 5.5** (`CLAUDE_MODEL` in `.github/workflows/finance-updates.yml`), which costs half as much per token as Claude Opus 5.5. Each run handles at most 12 new items (`max_new_per_run` in `config/sources.yaml`).
- Change `CLAUDE_MODEL` to `claude-opus-5-5` for the most capable model, or to `claude-haiku-5-5` for the cheapest.

### 3. Set up notifications (pick one or both)
**ntfy (recommended, free, no account):**
- Install the **ntfy** app (Play Store / App Store).
- Tap **+**, subscribe to a hard-to-guess topic name, e.g. `fuh-yourname-8k3j2x` (anyone who knows the name can read it).

**Telegram (optional):**
- Message `@BotFather` → `/newbot` → copy the bot token.
- Send any message to your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id`.

### 4. Add the secrets
Repository → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your Claude API key (required) |
| `NTFY_TOPIC` | the ntfy topic name |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | only if using Telegram |

### 5. Turn on the web app
Repository → **Settings → Pages → Build and deployment → Source: GitHub Actions**.

### 6. First run
**Actions** tab → *Finance updates* → **Run workflow**. After 2–4 minutes your app is live at
`https://<your-github-username>.github.io/finance-updates/` and the first notifications arrive.

### 7. Install on your phone / tablet
Open the app link in Chrome (Android) or Safari (iPhone/iPad) → **Add to Home screen**. It then opens like a normal app and works offline for posts you've already opened.

## Using it
- **Notification → tap** → opens that update's post page.
- **Save image** downloads the PNG. On iPhone/iPad, use **Share → Save Image** to put it in Photos.
- **Captions** tab: pick LinkedIn / Instagram / X / WhatsApp, then **Copy caption**.
- Home screen: filter by regulator, search by headline, notification number or case name.

## Customising
All in `config/sources.yaml` (edit it on github.com directly):
- `brand_handle` — the handle printed on every image, e.g. `@ABCandAssociates`.
- Add sources: any RSS feed, a Google News search, or an official listing page via CSS selector.
- `max_new_per_run`, `max_age_days` — volume and cost control.
- Schedule: edit the `cron` line in `.github/workflows/finance-updates.yml` (times are UTC; IST = UTC+5:30).
- Image colours / layout: `pipeline/render.py`. Model: set a `CLAUDE_MODEL` env var in the workflow.

## Accuracy
Claude is told to use only facts in the source text and to leave numbers, dates and case names blank when they aren't stated. It is also told whether it is reading an official document, a judgment or a news report, and to phrase news-based points as "reported". **Check the official notification or judgment before posting.** Every image carries a "For information only. Verify with the official source." line and names its source type.

## Privacy
With a public repo, the posts and web app are publicly viewable (they're meant for social media, so that's usually fine). Your API key and notification settings stay in encrypted Secrets and are never published. For a private setup, use a private repo with GitHub Pro/Team (private Pages) or deploy `docs/` to Cloudflare Pages with Cloudflare Access.

## Run locally (optional)
```bash
pip install -r requirements.txt
python -m pipeline.run --samples      # sample posts, no API key needed
python -m http.server -d docs 8000    # open http://localhost:8000
```

## Files
| Path | What it does |
|---|---|
| `pipeline/fetch.py` | reads feeds / pages, extracts full text (HTML or PDF) |
| `pipeline/summarise.py` | Claude call: relevance check, summary or table, captions |
| `pipeline/render.py` | draws the social media image |
| `pipeline/notify.py` | ntfy + Telegram notifications with a deep link to the post |
| `pipeline/run.py` | runs the whole flow |
| `docs/` | the web app + all saved posts (`docs/posts/`) and the feed (`docs/data/`) |
| `.github/workflows/finance-updates.yml` | the schedule |

Note: GitHub pauses scheduled workflows in repos with no activity for 60 days. The bot's own commits count as activity, so it keeps running while updates keep arriving.
