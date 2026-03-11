#!/usr/bin/env python3
"""
tools/create_icns.py
Convert chess_karma/assets/icon.png → chess_karma/assets/icon.icns

Requires:
  - Pillow  (pip install Pillow)
  - iconutil  (macOS built-in, available on all macOS systems)

Run this script on macOS before packaging with chess_karma_mac.spec.
It is called automatically by the GitHub Actions macOS build workflow.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ASSETS_DIR = Path(__file__).parent.parent / "chess_karma" / "assets"
SRC_PNG    = ASSETS_DIR / "icon.png"
ICONSET    = ASSETS_DIR / "icon.iconset"   # temporary, deleted after conversion
DST_ICNS   = ASSETS_DIR / "icon.icns"

# Required icon sizes and their Retina (@2x) pixel dimensions.
# iconutil maps:  icon_NxN.png  →  N points,  icon_NxN@2x.png  →  N@2x points
ICON_SIZES = {
    "icon_16x16.png":      16,
    "icon_16x16@2x.png":   32,
    "icon_32x32.png":      32,
    "icon_32x32@2x.png":   64,
    "icon_128x128.png":    128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png":    256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png":    512,
    "icon_512x512@2x.png": 1024,
}


def _ensure_pillow() -> None:
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Pillow not found – installing…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])


def main() -> None:
    if sys.platform != "darwin":
        print("create_icns.py: skipped (not macOS).")
        return

    if not SRC_PNG.exists():
        print(f"ERROR: source PNG not found: {SRC_PNG}", file=sys.stderr)
        sys.exit(1)

    _ensure_pillow()
    from PIL import Image  # noqa: PLC0415

    # Clean up any previous partial iconset
    if ICONSET.exists():
        shutil.rmtree(ICONSET)
    ICONSET.mkdir(parents=True)

    img = Image.open(SRC_PNG).convert("RGBA")

    for filename, px in ICON_SIZES.items():
        resized = img.resize((px, px), Image.LANCZOS)
        resized.save(ICONSET / filename)
        print(f"  {filename}  ({px}×{px})")

    # Convert the iconset → .icns using the macOS built-in tool
    subprocess.check_call(
        ["iconutil", "-c", "icns", str(ICONSET), "-o", str(DST_ICNS)]
    )

    # Remove the temporary iconset directory
    shutil.rmtree(ICONSET)

    print(f"\nCreated: {DST_ICNS.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
