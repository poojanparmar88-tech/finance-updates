"""Draw a 1080x1350 social post image (Instagram/LinkedIn portrait) for one update."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
PAD = 64
FOOTER_H = 170

COLORS = {
    "Income Tax": "#1f4e9c",
    "GST": "#0f7b6c",
    "MCA": "#6b3fa0",
    "RBI": "#b4532a",
    "Supreme Court": "#7a1f2b",
    "High Court": "#86651a",
}
INK, MUTED, RULE, ZEBRA = "#16181d", "#5b6170", "#e3e5ea", "#f4f5f8"

_FONT_PATHS = {
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf"],
    "regular": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "C:/Windows/Fonts/arial.ttf", "/Library/Fonts/Arial.ttf"],
}
_cache: dict = {}


def font(weight: str, size: int):
    key = (weight, size)
    if key not in _cache:
        path = next((p for p in _FONT_PATHS[weight] if Path(p).exists()), None)
        _cache[key] = ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
    return _cache[key]


def wrap(draw, text: str, fnt, width: int, max_lines: int | None = None) -> list[str]:
    lines, line = [], ""
    for word in str(text).split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and draw.textlength(lines[-1] + "…", font=fnt) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + "…"
    return lines


def _hex(c: str) -> tuple:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def render_post(post: dict, out_path: Path, brand_handle: str) -> None:
    accent = COLORS.get(post["regulator"], "#333a48")
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # Header band
    d.rectangle([0, 0, W, 190], fill=accent)
    d.text((PAD, 52), post["regulator"].upper(), font=font("bold", 54), fill="white")
    chip = post["category"]
    cf = font("bold", 28)
    cw = d.textlength(chip, font=cf) + 44
    d.rounded_rectangle([W - PAD - cw, 62, W - PAD, 116], radius=27, fill="white")
    d.text((W - PAD - cw + 22, 74), chip, font=cf, fill=accent)
    date_line = "  ·  ".join(x for x in [
        f"Issued {post['issued_on']}" if post.get("issued_on") else "",
        f"Effective {post['effective_from']}" if post.get("effective_from") else ""] if x)
    if date_line:
        d.text((PAD, 134), date_line, font=font("regular", 26), fill=(255, 255, 255, 220))

    # Headline
    y = 230
    hf = font("bold", 52)
    for ln in wrap(d, post["headline"], hf, W - 2 * PAD, max_lines=4):
        d.text((PAD, y), ln, font=hf, fill=INK)
        y += 64
    y += 18
    d.rectangle([PAD, y, PAD + 120, y + 8], fill=accent)
    y += 40

    limit = H - FOOTER_H - 30
    table = post.get("table") or {}
    if post["format"] == "table" and table.get("columns") and table.get("rows"):
        y = _draw_table(d, table, y, limit, accent)
    else:
        y = _draw_bullets(d, post["summary_points"], y, limit, accent)

    lf = font("regular", 28)
    for label, key in (("Who is affected", "who_is_affected"), ("Action", "action_required")):
        if not post.get(key) or y + 90 > limit:
            continue
        y += 16
        lines = wrap(d, f"{label}: {post[key]}", lf, W - 2 * PAD,
                     max_lines=max(1, (limit - y) // 38))
        for ln in lines:
            d.text((PAD, y), ln, font=lf, fill=MUTED)
            y += 38

    # Footer
    fy = H - FOOTER_H
    d.rectangle([0, fy, W, H], fill=ZEBRA)
    d.rectangle([0, fy, W, fy + 6], fill=accent)
    ref = post.get("reference") or post.get("source_name") or ""
    d.text((PAD, fy + 30), wrap(d, ref, font("bold", 28), W - 2 * PAD, 1)[0] if ref else "",
           font=font("bold", 28), fill=INK)
    source_line = {
        "official": f"Official source: {post.get('source_domain', '')}",
        "judgment": f"Judgment text: {post.get('source_domain', '')}",
        "news": "Based on a news report",
    }.get(post.get("source_type"), f"Source: {post.get('source_domain', '')}")
    d.text((PAD, fy + 74), source_line, font=font("regular", 24), fill=MUTED)
    d.text((PAD, fy + 110), "For information only. Verify with the official source.",
           font=font("regular", 22), fill=MUTED)
    bf = font("bold", 30)
    d.text((W - PAD - d.textlength(brand_handle, font=bf), fy + 100), brand_handle, font=bf,
           fill=accent)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)


def _draw_bullets(d, points, y, limit, accent) -> int:
    bf = font("regular", 34)
    for point in points:
        lines = wrap(d, point, bf, W - 2 * PAD - 44)
        if y + 46 * len(lines) > limit:
            room = (limit - y) // 46
            if room < 1:
                break
            lines = wrap(d, point, bf, W - 2 * PAD - 44, max_lines=room)
        d.ellipse([PAD, y + 13, PAD + 16, y + 29], fill=accent)
        for ln in lines:
            d.text((PAD + 44, y), ln, font=bf, fill=INK)
            y += 46
        y += 22
    return y


def _draw_table(d, table, y, limit, accent) -> int:
    cols, rows = table["columns"], table["rows"]
    n = len(cols)
    inner = W - 2 * PAD
    # Column widths proportional to the longest text in each column, with a floor.
    lengths = [max([len(str(cols[i]))] + [len(str(r[i])) for r in rows if i < len(r)])
               for i in range(n)]
    total = sum(max(l, 8) for l in lengths)
    widths = [inner * max(l, 8) / total for l in lengths]
    hf, cf, cell_pad, lh = font("bold", 26), font("regular", 26), 14, 34

    def draw_row(cells, fnt, fill, text_fill, y0):
        wrapped = [wrap(d, str(cells[i]) if i < len(cells) else "", fnt,
                        int(widths[i] - 2 * cell_pad), max_lines=4) for i in range(n)]
        h = max(len(w) for w in wrapped) * lh + 2 * cell_pad
        if y0 + h > limit:
            return None
        d.rectangle([PAD, y0, W - PAD, y0 + h], fill=fill)
        x = PAD
        for i, lines in enumerate(wrapped):
            for j, ln in enumerate(lines):
                d.text((x + cell_pad, y0 + cell_pad + j * lh), ln, font=fnt, fill=text_fill)
            x += widths[i]
        return y0 + h

    y = draw_row(cols, hf, accent, "white", y) or y
    for k, row in enumerate(rows):
        nxt = draw_row(row, cf, ZEBRA if k % 2 else "white", INK, y)
        if nxt is None:
            d.text((PAD, y + 8), "… full table in the app", font=font("regular", 24), fill=MUTED)
            return y + 40
        d.line([PAD, nxt, W - PAD, nxt], fill=RULE, width=2)
        y = nxt
    return y + 10
