from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    candidates = [Path("C:/Windows/Fonts/arialbd.ttf"), Path("C:/Windows/Fonts/arial.ttf")]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def generate_thumbnail(topic: str, destination: Path) -> Path:
    image = Image.new("RGB", (1280, 720), "#080b18")
    draw = ImageDraw.Draw(image)
    draw.ellipse((760, 80, 1210, 530), fill="#15254f", outline="#54d6ff", width=8)
    headline = "THE 6174\nNUMBER TRAP" if "6174" in topic else topic[:45].upper()
    draw.multiline_text((70, 125), headline, font=_font(92), fill="#ffffff", spacing=18)
    draw.text((830, 210), "6174", font=_font(118), fill="#ffb347")
    draw.text((75, 610), "VISUAL MATHEMATICS", font=_font(34), fill="#54d6ff")
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "PNG", optimize=True)
    return destination
