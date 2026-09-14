"""Embed out/assembly.glb into one self-contained HTML viewer at out/viewer.html.

Run from enclosure/ after build.py:  .venv/Scripts/python.exe viewer.py
"""
from __future__ import annotations

import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN = "__GLB_BASE64__"
LIMIT_BYTES = 15 * 1024 * 1024


def main() -> Path:
    glb = (HERE / "out" / "assembly.glb").read_bytes()
    template = (HERE / "viewer_template.html").read_text(encoding="utf-8")
    if template.count(TOKEN) != 1:
        raise RuntimeError(f"viewer_template.html must contain {TOKEN} exactly once")
    html = template.replace(TOKEN, base64.b64encode(glb).decode("ascii"))
    if len(html.encode("utf-8")) > LIMIT_BYTES:
        raise RuntimeError("viewer is over 15 MB; raise linear_deflection for the GLB in build.py")
    out = HERE / "out" / "viewer.html"
    out.write_text(html, encoding="utf-8")
    print(f"{out.relative_to(HERE)}  {out.stat().st_size / 1024:.0f} KB")
    return out


if __name__ == "__main__":
    main()
