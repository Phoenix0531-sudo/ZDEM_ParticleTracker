"""Generate portfolio evidence figures from pure services (no full GUI)."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from zdem_particle_tracker.services.region_detector import RegionDetector
from zdem_particle_tracker.services.trajectory_service import _compute_kinematics
from zdem_particle_tracker.widgets.selection_logic import pick_particle_id

OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

BG = "#0b1220"
PANEL = "#111827"
FG = "#e5e7eb"
ACCENT = "#38bdf8"
ACCENT2 = "#f472b6"
GOOD = "#34d399"
WALL = "#fbbf24"
MUTED = "#94a3b8"


def style(ax, title: str) -> None:
    ax.set_facecolor(PANEL)
    ax.set_title(title, color=FG, fontsize=11, pad=8)
    ax.tick_params(colors=MUTED, labelsize=8)
    for s in ax.spines.values():
        s.set_color("#1f2937")
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)


def main() -> None:
    # Synthetic frame: walls + particles with permanent ids
    walls = np.array(
        [
            [0, 0, 100, 0],
            [100, 0, 100, 60],
            [100, 60, 0, 60],
            [0, 60, 0, 0],
        ],
        dtype=float,
    )
    det = RegionDetector()
    reg = det.detect_from_walls(walls)
    assert reg.source == "walls"

    rng = np.random.default_rng(7)
    n = 48
    xs = rng.uniform(5, 95, n)
    ys = rng.uniform(5, 55, n)
    rads = rng.uniform(1.2, 2.8, n)
    ids = np.arange(1000, 1000 + n, dtype=np.int64)
    start_ids = set(ids[:40].tolist())  # last few not selectable at session start

    # Click near particle 0
    click = (float(xs[0]), float(ys[0]))
    picked = pick_particle_id(xs, ys, rads, ids, click[0], click[1], start_ids=start_ids)
    blocked = pick_particle_id(
        xs, ys, rads, ids, float(xs[-1]), float(ys[-1]), start_ids=start_ids
    )

    # Kinematics along a short synthetic track
    track = [(10.0, 10.0, 0), (12.0, 11.0, 1), (15.0, 13.0, 3), (19.0, 14.5, 5)]
    first_x = first_y = prev_x = prev_y = prev_step = None
    path_length = 0.0
    vels = []
    for x, y, step in track:
        first_x, first_y, prev_x, prev_y, prev_step, path_length, fields = _compute_kinematics(
            x, y, step, first_x, first_y, prev_x, prev_y, prev_step, path_length
        )
        vels.append(fields["velocity_total"])

    fig = plt.figure(figsize=(12.8, 7.4), facecolor=BG)
    gs = GridSpec(2, 3, figure=fig, wspace=0.28, hspace=0.32, left=0.05, right=0.98, top=0.88, bottom=0.08)

    # Panel 1: mesh-disc style scene (honest synthetic)
    ax1 = fig.add_subplot(gs[:, 0])
    style(ax1, "True-radius discs + wall region")
    ax1.set_aspect("equal")
    ax1.set_xlim(-5, 105)
    ax1.set_ylim(-5, 65)
    # walls
    for x1, y1, x2, y2 in walls:
        ax1.plot([x1, x2], [y1, y2], color=WALL, lw=2.0, zorder=1)
    # region box
    ax1.add_patch(
        Rectangle(
            (reg.x_min, reg.y_min),
            reg.x_max - reg.x_min,
            reg.y_max - reg.y_min,
            fill=False,
            edgecolor=GOOD,
            lw=1.5,
            linestyle="--",
            zorder=2,
        )
    )
    for x, y, r, pid in zip(xs, ys, rads, ids):
        allowed = int(pid) in start_ids
        face = ACCENT if allowed else "#475569"
        ax1.add_patch(Circle((x, y), r, facecolor=face, edgecolor="#0f172a", lw=0.4, alpha=0.9, zorder=3))
    if picked is not None:
        i = int(np.where(ids == picked)[0][0])
        ax1.add_patch(
            Circle((xs[i], ys[i]), rads[i] * 1.35, fill=False, edgecolor=ACCENT2, lw=2.0, zorder=4)
        )
        ax1.plot(click[0], click[1], marker="+", color=ACCENT2, ms=12, mew=2, zorder=5)
    ax1.set_xlabel("x")
    ax1.set_ylabel("y")

    # Panel 2: selection gate
    ax2 = fig.add_subplot(gs[0, 1])
    style(ax2, "Selection gate (session-start IDs)")
    ax2.axis("off")
    text = (
        f"pick at near id {ids[0]} → {picked}\n"
        f"pick at gated id {ids[-1]} → {blocked}\n"
        f"start_ids size = {len(start_ids)} / {n}\n"
        f"rule: permanent id must exist in start frame\n"
        f"API: pick_particle_id(... start_ids=)"
    )
    ax2.text(0.05, 0.9, text, transform=ax2.transAxes, va="top", color=FG, family="monospace", fontsize=10)

    # Panel 3: region detector numbers
    ax3 = fig.add_subplot(gs[0, 2])
    style(ax3, "RegionDetector.detect_from_walls")
    ax3.axis("off")
    ax3.text(
        0.05,
        0.9,
        "\n".join(
            [
                f"source   = {reg.source}",
                f"x_min    = {reg.x_min:.1f}",
                f"x_max    = {reg.x_max:.1f}",
                f"y_min    = {reg.y_min:.1f}",
                f"y_max    = {reg.y_max:.1f}",
                "",
                "policy: user lock > walls > metadata",
                "never permanent crop to particle Y bbox",
            ]
        ),
        transform=ax3.transAxes,
        va="top",
        color=FG,
        family="monospace",
        fontsize=10,
    )

    # Panel 4: velocity definition
    ax4 = fig.add_subplot(gs[1, 1:])
    style(ax4, "Kinematics: v = Δx / Δstep (not wall-clock)")
    steps = [t[2] for t in track]
    ax4.plot(steps, vels, "o-", color=ACCENT, lw=2, ms=7)
    ax4.set_xlabel("step")
    ax4.set_ylabel("velocity_total")
    ax4.text(
        0.02,
        0.92,
        f"path_length = {path_length:.3f}\n_compute_kinematics in trajectory_service.py",
        transform=ax4.transAxes,
        color=GOOD,
        fontsize=9,
        va="top",
        family="monospace",
    )

    fig.suptitle(
        "ZDEM Particle Tracker — service-level evidence (synthetic frame)",
        color=FG,
        fontsize=14,
        fontweight="bold",
        y=0.96,
    )
    path = OUT / "evidence.png"
    fig.savefig(path, dpi=160, facecolor=BG)
    plt.close(fig)
    print(f"wrote {path} picked={picked} blocked={blocked} path_len={path_length:.4f}")


if __name__ == "__main__":
    main()
