"""Генератор бренд-знака «Без Б» (монета с кириллической Б) 300x300.
Геометрия совпадает с IconLogo из miniapp/src/components/Icons.tsx (viewBox 24x24),
масштаб 12.5x. Делает прозрачный PNG и SVG."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(__file__)
S = 12.5                      # масштаб 24 -> 300
SIZE = 300
TEAL = (38, 166, 154, 255)    # #26a69a
DARK = (14, 17, 23, 255)      # #0e1117


def px(v):
    return v * S


# ── PNG ──
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# монета
d.ellipse([px(0.5), px(0.5), px(23.5), px(23.5)], fill=TEAL)
# 4 штриха (биткоин-стиль) сверху и снизу
for x, y in [(9.0, 3.6), (12.2, 3.6), (9.0, 17.2), (12.2, 17.2)]:
    d.rounded_rectangle([px(x), px(y), px(x + 1.5), px(y + 3.2)], radius=px(0.5), fill=DARK)
# буква Б по центру
font = None
for fp in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\Arial.ttf"):
    if os.path.exists(fp):
        font = ImageFont.truetype(fp, int(px(13.5)))
        break
if font is None:
    font = ImageFont.load_default()
d.text((px(11.6), px(12.4)), "Б", font=font, fill=DARK, anchor="mm")
img.save(os.path.join(OUT, "bezb_logo_300.png"))
print("PNG saved:", os.path.join(OUT, "bezb_logo_300.png"), img.size)

# ── SVG (точный, масштабируемый) ──
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="11.5" fill="#26a69a"/>
  <g fill="#0e1117">
    <rect x="9.0" y="3.6" width="1.5" height="3.2" rx="0.5"/>
    <rect x="12.2" y="3.6" width="1.5" height="3.2" rx="0.5"/>
    <rect x="9.0" y="17.2" width="1.5" height="3.2" rx="0.5"/>
    <rect x="12.2" y="17.2" width="1.5" height="3.2" rx="0.5"/>
    <text x="11.6" y="12.6" text-anchor="middle" dominant-baseline="central"
      font-family="Arial, Helvetica, sans-serif" font-size="13.5" font-weight="700">Б</text>
  </g>
</svg>'''
with open(os.path.join(OUT, "bezb_logo_300.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("SVG saved:", os.path.join(OUT, "bezb_logo_300.svg"))
