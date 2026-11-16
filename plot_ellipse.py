#!/usr/bin/env python3
"""
Overlay of the elliptical-fiber scatter sweeps: transverse elastic constants vs
fiber angle scatter, one colour/marker per a/b, FFT solid and ANSYS dashed, with
the circular fiber (a/b = 1 from the matching aspect scenario) as reference lines.

    python plot_ellipse.py            # stiffness, N = 32 (scenarios 9-12)
    python plot_ellipse.py dataset    # dataset mode, N = 25 (scenarios 13-16)

Works on partial results: missing points are simply left out. Writes
runs/ellipse_compare/<family>.png/.eps and summary_<family>.csv (the plotted
means and standard deviations, as a table view of the figure).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import CONFIGS, ELLIPSE_ASPECTS
from plot import extract_series, get_light_tint, load_sweep_data

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Liberation Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = Path("runs/ellipse_compare")

# family -> (scatter scenario name pattern, a/b = 1 reference scenario)
FAMILIES = {
    "stiffness": ("fscatter_{tag}_cf_epoxy", "aspect_sweep_cf_epoxy"),
    "dataset": ("fscatter_{tag}_dataset_cf_epoxy_n25", "aspect_dataset_cf_epoxy_n25"),
}

# One hue + one marker per a/b (fixed order, validated for colour-vision deficiency;
# the marker carries identity too, the aqua is below 3:1 contrast on white).
AB_STYLE = [("#2a78d6", "o"), ("#eb6834", "s"), ("#1baf7a", "^")]
# Solver -> line style, marker fill, reference-line style
SOLVER_LINE = {"fft": ("-", "full", ":"), "ansys": ("--", "none", "-.")}

PANELS = [("E1", "E₁ (вздовж x)", "ГПа"), ("E2", "E₂ (вздовж y)", "ГПа"),
          ("G12", "G₁₂ (зсув у площині перерізу)", "ГПа"), ("G23", "G₂₃", "ГПа"),
          ("G13", "G₁₃", "ГПа"), ("nu12", "ν₁₂", "")]


def scenario_name(pattern: str, ab: float) -> str:
    return pattern.format(tag=f"ab{ab:g}".replace(".", ""))


def solvers_in(rows) -> list[str]:
    present = {r.get("solver", "fft").strip().lower() for r in rows}
    return [s for s in SOLVER_LINE if s in present]


def circular_reference(ref_name: str) -> dict[str, dict[str, float]]:
    """solver -> constants of the circular fiber (a/b = 1), for whatever is computed."""
    path = Path(CONFIGS[ref_name].rundir) / "results.csv"
    if not path.exists():
        return {}
    out = {}
    for r in load_sweep_data(path):
        if abs(float(r["sweep_value"]) - 1.0) < 1e-4:
            out[r.get("solver", "fft").strip().lower()] = {
                k: float(r[k]) for k, _, _ in PANELS if r.get(k) not in ("", None)}
    return out


def main():
    family = sys.argv[1] if len(sys.argv) > 1 else "stiffness"
    if family not in FAMILIES:
        raise SystemExit(f"Usage: python plot_ellipse.py [{' | '.join(FAMILIES)}]")
    pattern, ref_name = FAMILIES[family]
    cfg = CONFIGS[scenario_name(pattern, ELLIPSE_ASPECTS[0])]
    values = cfg.sweep_values
    x = np.array(values)
    ref = circular_reference(ref_name)

    data = {}
    for ab in ELLIPSE_ASPECTS:
        path = Path(CONFIGS[scenario_name(pattern, ab)].rundir) / "results.csv"
        if path.exists():
            data[ab] = load_sweep_data(path)
    if not data:
        raise SystemExit(f"No results yet for any {pattern.format(tag='*')} scenario")
    all_solvers = solvers_in([r for rows in data.values() for r in rows]
                             + [{"solver": s} for s in ref])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True)
    summary = []
    for ax, (key, title, unit) in zip(axes.flat, PANELS):
        for ab, (color, marker) in zip(ELLIPSE_ASPECTS, AB_STYLE):
            rows = data.get(ab)
            if not rows:
                continue
            for s in solvers_in(rows):
                ls, fill, _ = SOLVER_LINE[s]
                m, sd, raw = extract_series(rows, values, key, solver=s)
                ok = ~np.isnan(m)
                if not ok.any():
                    continue
                if np.nanmax(sd) > 0:
                    ax.fill_between(x[ok], (m - sd)[ok], (m + sd)[ok],
                                    color=get_light_tint(color, 0.85 if s == "ansys" else 0.8), zorder=2)
                ax.plot(x[ok], m[ok], color=color, linestyle=ls, marker=marker, fillstyle=fill,
                        ms=6, lw=2, label=f"a/b = {ab:g} ({s.upper()})", zorder=4)
                for v, mv, sv in zip(values, m, sd):
                    if not np.isnan(mv):
                        summary.append({"a_b": ab, "scatter_deg": v, "solver": s, "quantity": key,
                                        "mean": f"{mv:.5g}", "std": f"{sv:.3g}", "n": len(raw[v])})
        for s, consts in ref.items():
            if key in consts and s in SOLVER_LINE:
                ax.axhline(consts[key], color="#555555", linestyle=SOLVER_LINE[s][2], lw=1.3,
                           label=f"кругле волокно, a/b = 1 ({s.upper()})", zorder=1)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_ylabel(f"{key}, {unit}" if unit else key, fontsize=10)
        ax.grid(True, linestyle="--", linewidth=0.6, color="#dcdcdc")
        ax.set_xlim(-8, 188)
        ax.set_xticks(values)
        ax.set_xticklabels([f"{v:g}" if v >= 1 else "0" for v in values])
    for ax in axes[1]:
        ax.set_xlabel("Розкид кута повороту перерізу волокон, °", fontsize=10)
    axes[0, 0].legend(fontsize=8, frameon=True, facecolor="white", edgecolor="#d0d0d0", framealpha=1,
                      ncol=2 if len(all_solvers) > 1 else 1)

    stats = (f"лінія — середнє за {cfg.realizations} реалізаціями, смуга — ±1σ"
             if cfg.realizations > 1 else "1 реалізація на точку")
    fig.suptitle(f"{cfg.fiber_material} / {cfg.matrix_material}, еліптичні волокна, Vf = {cfg.vf:g}, "
                 f"1 волокно в комірці, N = {cfg.size}, режим {cfg.mode}, "
                 f"{' vs '.join(s.upper() for s in all_solvers)}\n({stats})",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()

    png, eps = OUT_DIR / f"{family}.png", OUT_DIR / f"{family}.eps"
    fig.savefig(png, dpi=cfg.dpi, bbox_inches="tight")
    fig.savefig(eps, bbox_inches="tight")
    plt.close(fig)

    table = OUT_DIR / f"summary_{family}.csv"
    with table.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["a_b", "scatter_deg", "solver", "quantity", "mean", "std", "n"])
        w.writeheader()
        w.writerows(summary)

    print(f"PNG -> {png}\nEPS -> {eps}\nCSV -> {table}")
    total = len(values) * cfg.realizations
    for ab in ELLIPSE_ASPECTS:
        rows = data.get(ab, [])
        done = ", ".join(f"{s.upper()} {sum(r['solver'] == s for r in rows)}/{total}" for s in cfg.solvers)
        print(f"  a/b = {ab:g}: {done}")


if __name__ == "__main__":
    main()
