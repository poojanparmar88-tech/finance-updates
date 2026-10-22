"""Turn a raw item into a structured update + social captions with Claude."""
import json
import os

import anthropic

from .fetch import Item

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

REGULATORS = ["Income Tax", "GST", "MCA", "RBI", "Supreme Court", "High Court"]
CATEGORIES = ["Act Amendment", "Notification", "Circular", "Press Release",
              "Judgment", "Advisory", "Other"]


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props,
            "required": list(props), "additionalProperties": False}


STR = {"type": "string"}
SCHEMA = _obj({
    "relevant": {"type": "boolean"},
    "regulator": {"type": "string", "enum": REGULATORS},
    "category": {"type": "string", "enum": CATEGORIES},
    "headline": STR,
    "reference": STR,
    "issued_on": STR,
    "effective_from": STR,
    "format": {"type": "string", "enum": ["summary", "table"]},
    "summary_points": {"type": "array", "items": STR},
    "table": _obj({
        "columns": {"type": "array", "items": STR},
        "rows": {"type": "array", "items": {"type": "array", "items": STR}},
    }),
    "who_is_affected": STR,
    "action_required": STR,
    "social": _obj({
        "linkedin": STR,
        "x": STR,
        "instagram": STR,
        "whatsapp": STR,
        "hashtags": {"type": "array", "items": STR},
    }),
})

SYSTEM = """You are the editor of an Indian tax & regulatory update service written for Chartered \
Accountants, CS, lawyers and finance teams. You receive one candidate item (an official notice, \
press release, or a news report about one) and produce a publication-ready update.

Rules:
- relevant=false if the item is not a genuine new regulatory development (Act amendment, \
notification, circular, instruction, advisory, press release with regulatory content) from \
Income Tax/CBDT, GST/CBIC/GSTN, MCA, RBI, or a Supreme Court / High Court judgment on tax, \
corporate, banking, insolvency or finance law. Opinion pieces, market news, stock tips and \
politics are not relevant. When relevant=false, fill other fields with short placeholders.
- Use only facts present in the material. Never invent notification numbers, section numbers, \
dates, rates or case names. Use "" for unknown reference/dates.
- "Source type" tells you what you are reading. "official" = the regulator's own document; \
"judgment" = full text of the court's judgment; "news" = a press report only. For news, keep \
to what the report says, phrase points as "reported" where the detail is not confirmed, and \
leave reference blank unless the report quotes it.
- headline: max 90 characters, plain, specific.
- reference: notification/circular number, or case name with court and citation if known.
- format: "table" when the content is naturally tabular (rate changes, due-date extensions, \
old vs new provisions, lists of forms); otherwise "summary". For "summary", leave table with \
empty columns and rows. For "table", give 2-4 columns and at most 8 rows of short cells, and \
still give 2-3 summary_points.
- summary_points: 3-5 crisp bullets, each under 160 characters. For judgments cover: issue, \
held, and practical impact.
- who_is_affected and action_required: one sentence each, practical.
- social.linkedin: 120-200 words, professional, short paragraphs, ends with a line asking \
readers to verify with the official source; no hashtags inside (they go in hashtags).
- social.x: under 260 characters including a short call to read more.
- social.instagram: 60-120 words, friendly, line breaks, a few emojis are fine.
- social.whatsapp: under 80 words, *bold* via asterisks allowed.
- hashtags: 4-8, no '#'-less words, e.g. "#GST", "#IncomeTax".
- Indian English, use ₹ for rupees."""


def summarise(item: Item, full_text: str) -> dict | None:
    """Returns the structured update, or None if Claude declines or output is unusable."""
    client = anthropic.Anthropic()
    material = (
        f"Regulator hint: {item.regulator}\n"
        f"Source type: {item.source_type}\n"
        f"Title: {item.title}\n"
        f"Published: {item.published or 'unknown'}\n"
        f"Link: {item.link}\n"
        f"Feed snippet: {item.snippet or '(none)'}\n\n"
        f"Document text (may be empty or partial):\n{full_text or '(not available)'}"
    )
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=8000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium",
                       "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM,
        messages=[{"role": "user", "content": material}],
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        print(f"    skipped ({response.stop_reason})")
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("    skipped (unparseable output)")
        return None
