"""Generate the app icons (run once; output is committed)."""
from pathlib import Path

from PIL import Image, ImageDraw

from .render import font

OUT = Path(__file__).resolve().parent.parent / "docs" / "icons"


def make(size: int) -> None:
    img = Image.new("RGB", (size, size), "#1f4e9c")
    d = ImageDraw.Draw(img)
    s = size / 512
    # Three rising bars + a rupee sign: "finance updates"
    for i, h in enumerate((120, 190, 260)):
        x = int((150 + i * 80) * s)
        d.rounded_rectangle([x, int((380 - h) * s), x + int(52 * s), int(380 * s)],
                            radius=int(10 * s), fill="white")
    f = font("bold", int(110 * s))
    d.text((int(330 * s), int(70 * s)), "₹", font=f, fill="#ffd27a")
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"icon-{size}.png")


if __name__ == "__main__":
    for n in (192, 512):
        make(n)
