"""
Icon generator for Chess Karma.

Draws a gold chess pawn on a dark-green rounded background and writes:
  chess_karma/assets/icon.png   (256×256, for reference)
  chess_karma/assets/icon.ico   (multi-size: 256‥16, PNG-in-ICO format)

Run once from the repo root:
    python tools/create_icon.py
"""

from __future__ import annotations

import io
import pathlib
import struct
import sys

from PyQt6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication

_ASSETS = pathlib.Path(__file__).parent.parent / "chess_karma" / "assets"

# ── Drawing ────────────────────────────────────────────────────────────────────

def _draw(size: int) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s  = float(size)
    m  = s * 0.04          # outer margin
    r  = s * 0.20          # corner radius
    cx = s / 2.0

    # ── Background ────────────────────────────────────────────────────────────
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), r, r)

    grad = QLinearGradient(0.0, 0.0, 0.0, s)
    grad.setColorAt(0.0, QColor("#4a5e3a"))
    grad.setColorAt(1.0, QColor("#2a3820"))
    p.fillPath(bg, QBrush(grad))

    # Border
    pen_w = max(1.0, s * 0.022)
    p.setPen(QPen(QColor("#6a8858"), pen_w))
    p.drawPath(bg)

    # ── Pawn silhouette (gold) ────────────────────────────────────────────────
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#f5c542")))

    # Head
    hr  = s * 0.135
    hcy = s * 0.255
    p.drawEllipse(QPointF(cx, hcy), hr, hr)

    # Neck
    nw = s * 0.095
    nh = s * 0.065
    ny = hcy + hr - s * 0.005
    p.drawRect(QRectF(cx - nw / 2, ny, nw, nh))

    # Body (ellipse)
    bw = s * 0.285
    bh = s * 0.170
    by = ny + nh - s * 0.01
    p.drawEllipse(QPointF(cx, by + bh / 2), bw / 2, bh / 2)

    # Base — trapezoid via QPainterPath
    base_top_w  = s * 0.26
    base_bot_w  = s * 0.52
    base_h      = s * 0.105
    base_y      = by + bh - s * 0.01
    radius      = base_h * 0.35

    base_path = QPainterPath()
    # Draw a shape that narrows slightly at the top
    tl = QPointF(cx - base_top_w / 2, base_y)
    tr = QPointF(cx + base_top_w / 2, base_y)
    br = QPointF(cx + base_bot_w / 2, base_y + base_h)
    bl = QPointF(cx - base_bot_w / 2, base_y + base_h)

    base_path.moveTo((tl + tr) / 2)
    base_path.lineTo(tr)
    base_path.lineTo(br)
    # rounded bottom-right corner
    base_path.quadTo(br, QPointF(br.x() - radius, br.y()))
    bottom_right_arc = QPointF(br.x() - radius, br.y())
    base_path.moveTo(tl)
    base_path.lineTo(tr)
    base_path.lineTo(br)
    base_path.lineTo(bl)
    base_path.lineTo(tl)
    base_path.closeSubpath()

    # Use a rounded rect instead — simpler and looks better
    base_path2 = QPainterPath()
    base_path2.addRoundedRect(
        QRectF(cx - base_bot_w / 2, base_y, base_bot_w, base_h),
        radius, radius,
    )
    p.drawPath(base_path2)

    # Tiny highlight on head
    p.setBrush(QBrush(QColor("#fff8dc")))
    hlight_r = hr * 0.35
    p.drawEllipse(QPointF(cx - hr * 0.28, hcy - hr * 0.28), hlight_r, hlight_r)

    p.end()
    return px


# ── ICO helpers ────────────────────────────────────────────────────────────────

def _px_to_png_bytes(px: QPixmap) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    px.save(buf, "PNG")
    buf.close()
    return bytes(buf.data())


def _make_ico(entries: list[tuple[int, bytes]]) -> bytes:
    """Build a multi-size ICO that embeds PNG data (Vista+ format)."""
    count = len(entries)
    icondir = struct.pack("<HHH", 0, 1, count)          # reserved, type=1, count

    dir_entries = b""
    images      = b""
    offset = 6 + count * 16                             # ICONDIR + N×ICONDIRENTRY

    for size, png_data in entries:
        w = size if size < 256 else 0                   # 0 encodes 256 in ICO
        h = w
        dir_entries += struct.pack(
            "<BBBBHHII",
            w, h,              # width, height
            0,                 # colour count  (0 = fullcolour)
            0,                 # reserved
            1,                 # planes
            32,                # bits per pixel
            len(png_data),     # size of embedded data
            offset,            # file offset of embedded data
        )
        images += png_data
        offset += len(png_data)

    return icondir + dir_entries + images


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    sizes = [256, 128, 64, 48, 32, 16]
    ico_entries: list[tuple[int, bytes]] = []

    for sz in sizes:
        px  = _draw(sz)
        png = _px_to_png_bytes(px)
        ico_entries.append((sz, png))
        print(f"  rendered {sz}×{sz}")

    # Save PNG (256 px reference copy)
    png_path = _ASSETS / "icon.png"
    png_path.write_bytes(ico_entries[0][1])
    print(f"Saved {png_path}")

    # Save ICO
    ico_path = _ASSETS / "icon.ico"
    ico_path.write_bytes(_make_ico(ico_entries))
    print(f"Saved {ico_path}")


if __name__ == "__main__":
    main()
