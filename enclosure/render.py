"""Shaded PNG views of every part for visual review. Writes out/renders/<name>_<view>.png.

Run from enclosure/:  .venv/Scripts/python.exe render.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from build123d import Part  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from build import OUT, assembly_parts, parts  # noqa: E402

LIGHT = np.array([0.45, -0.55, 0.70]) / np.linalg.norm([0.45, -0.55, 0.70])
VIEWS = {"front": (24, -62), "back": (30, 118), "top": (88, -90), "under": (-35, -62)}
PART_RGB = (0.90, 0.88, 0.84)
RGB = {
    "body": PART_RGB, "lid": (0.78, 0.83, 0.88), "wedge": (0.78, 0.83, 0.88),
    "pcb": (0.10, 0.35, 0.70), "cell": (0.25, 0.25, 0.28), "sensors": (0.12, 0.55, 0.45), "panel": (0.12, 0.12, 0.16),
}


def _triangles(part: Part) -> np.ndarray:
    verts, tris = part.tessellate(0.05, 0.3)
    v = np.array([(q.X, q.Y, q.Z) for q in verts])
    return v[np.array(tris)]


def _render(name: str, items: list[tuple[Part, tuple[float, float, float]]], out_dir: Path) -> list[Path]:
    tris, colours = [], []
    for part, rgb in items:
        t = _triangles(part)
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        shade = 0.30 + 0.70 * np.abs(n @ LIGHT)
        tris.append(t)
        colours.append(np.clip(np.outer(shade, rgb), 0.0, 1.0))
    tris_all, colours_all = np.concatenate(tris), np.concatenate(colours)
    lo, hi = tris_all.reshape(-1, 3).min(0), tris_all.reshape(-1, 3).max(0)
    written = []
    for view, (elev, azim) in VIEWS.items():
        fig = plt.figure(figsize=(9, 7), dpi=120)
        ax = fig.add_subplot(projection="3d")
        ax.add_collection3d(Poly3DCollection(tris_all, facecolors=colours_all, edgecolors="none"))
        ax.set_xlim(lo[0], hi[0])
        ax.set_ylim(lo[1], hi[1])
        ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(tuple(hi - lo))
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(f"{name}, {view}")
        path = out_dir / f"{name}_{view}.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        written.append(path)
    return written


def main() -> None:
    out_dir = OUT / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    models = parts()
    jobs = {name: [(model, RGB.get(name, PART_RGB))] for name, (model, _) in models.items()}
    assembly = assembly_parts(models["body"][0], models["lid"][0], models["wedge"][0])
    jobs["assembly"] = [(part, RGB[part.label]) for part in assembly]
    for name, items in jobs.items():
        for path in _render(name, items, out_dir):
            print(path.relative_to(HERE))


if __name__ == "__main__":
    main()
