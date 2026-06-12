"""
Genera assets/icon.ico — icono de sincronización para SincroSIG.
Ejecutar una sola vez: python create_icon.py
"""
import math
import os
from PIL import Image, ImageDraw


def _draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    # Fondo circular azul
    pad = max(1, size // 16)
    d.ellipse([pad, pad, size - pad, size - pad], fill=(41, 98, 168, 255))

    cx, cy  = size / 2, size / 2
    r       = size * 0.29
    lw      = max(2, int(size * 0.09))
    arr     = size * 0.13       # largo de la cabeza de flecha

    def arc_arrow(start_deg, end_deg, head_at_end=True):
        bbox = [cx - r, cy - r, cx + r, cy + r]
        d.arc(bbox, start=start_deg, end=end_deg, fill="white", width=lw)

        tip_deg  = end_deg if head_at_end else start_deg
        tang_deg = tip_deg + 90 if head_at_end else tip_deg - 90
        tip_rad  = math.radians(tip_deg)
        tang_rad = math.radians(tang_deg)

        tx = cx + r * math.cos(tip_rad)
        ty = cy + r * math.sin(tip_rad)
        p1x = tx + arr * math.cos(tang_rad + math.radians(35))
        p1y = ty + arr * math.sin(tang_rad + math.radians(35))
        p2x = tx + arr * math.cos(tang_rad - math.radians(35))
        p2y = ty + arr * math.sin(tang_rad - math.radians(35))
        d.polygon([(tx, ty), (p1x, p1y), (p2x, p2y)], fill="white")

    # Arco superior (izquierda → derecha, flecha a la derecha)
    arc_arrow(190, 350, head_at_end=True)
    # Arco inferior (derecha → izquierda, flecha a la izquierda)
    arc_arrow(10, 170, head_at_end=True)

    return img


if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)
    sizes  = [256, 128, 64, 48, 32, 16]
    frames = [_draw_icon(s) for s in sizes]
    frames[0].save(
        "assets/icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print("OK  assets/icon.ico generado correctamente.")
