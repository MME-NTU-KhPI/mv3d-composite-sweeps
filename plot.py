#!/usr/bin/env python3
"""
Plotting for the MatViz3D scatter-sweep tool.

Reads results.csv from a run directory and writes sweep.png + sweep.eps
(a 3-panel figure: stiffness components, elastic constants with Voigt/Reuss
bounds, E_max/E_min anisotropy), criteria_summary.txt and, for FFT vs ANSYS,
comparison.png/.eps and comparison_summary.txt/.csv. Normally called from
run.py; run directly for a quick redraw after editing a config's cosmetics:

    python plot.py vf_sweep_cf_epoxy
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import SweepConfig, CONFIGS
import composite_ref

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Liberation Sans"]
plt.rcParams["axes.unicode_minus"] = False

SOLVER_STYLE = {
    "fft": {"ls": "-", "marker": "o", "suffix": "(FFT)"},
    "ansys": {"ls": "--", "marker": "s", "suffix": "(ANSYS)"},
}


def get_light_tint(color: Any, factor: float = 0.78) -> tuple[float, float, float]:
    """Mix a color with white, for shaded bands that stay solid (EPS-safe, no alpha)."""
    r, g, b = matplotlib.colors.to_rgb(color)
    return (r * (1 - factor) + factor, g * (1 - factor) + factor, b * (1 - factor) + factor)


def load_sweep_data(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Results CSV not found: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def reference_rows(cfg: SweepConfig, rows) -> list[dict[str, Any]]:
    """Rows from cfg.compare_with's results.csv for the solvers this scenario did not run."""
    if not cfg.compare_with:
        return []
    own = {r.get("solver", "fft").strip().lower() for r in rows}
    ref = load_sweep_data(Path(CONFIGS[cfg.compare_with].rundir) / "results.csv")
    return [r for r in ref if r.get("solver", "fft").strip().lower() not in own]


def extract_series(rows: Sequence[dict[str, Any]], values: Sequence[float], key: str, solver: str | None = None):
    """Mean, std, and raw per-realization values of `key` at each sweep value, optionally filtered by solver."""
    means, stds, raw = [], [], {}
    for v in values:
        vals = [
            float(r[key]) for r in rows
            if abs(float(r["sweep_value"]) - v) < 1e-4
            and r.get(key) not in ("", None)
            and (solver is None or r.get("solver", "fft").strip().lower() == solver)
        ]
        raw[v] = vals
        if vals:
            arr = np.array(vals)
            means.append(arr.mean())
            stds.append(arr.std())
        else:
            means.append(np.nan)
            stds.append(np.nan)
    return np.array(means), np.array(stds), raw


def _plot_panel(ax, rows, x, values, series_info, solvers, cfg, is_comparison, has_spread, title, ylabel):
    """Draw one panel: shaded band + scatter dots + mean line, for each (key, label, color) x each solver."""
    for key, label, color in series_info:
        for s in solvers:
            style = SOLVER_STYLE.get(s, {"ls": "-", "marker": "o", "suffix": f"({s})"})
            m, sd, raw = extract_series(rows, values, key, solver=s)
            if np.all(np.isnan(m)):
                continue
            curve_label = f"{label} {style['suffix']}" if is_comparison else label

            if has_spread:
                band = get_light_tint(color, 0.78)
                ax.fill_between(x, m - cfg.band_sigma * sd, m + cfg.band_sigma * sd, color=band, zorder=2)
                pts_color = get_light_tint(color, 0.25)
                for v in values:
                    pts = raw.get(v, [])
                    if len(pts) > 1:
                        ax.scatter([v] * len(pts), pts, color=pts_color, s=18,
                                   marker=style["marker"], edgecolors="none", zorder=3)

            ax.plot(x, m, color=color, linestyle=style["ls"], marker=style["marker"],
                     ms=5, lw=1.8, label=curve_label, zorder=4)

    ax.set_title(title, fontsize=11, fontweight="bold", pad=10)
    ax.set_xlabel(cfg.axis_label, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.legend(fontsize=8, frameon=True, facecolor="white", edgecolor="#d0d0d0", ncol=2 if is_comparison else 1)
    ax.grid(True, linestyle="--", linewidth=0.6, color="#dcdcdc")


COMPOSITE_REPORT_KEYS = [("C11", "C11"), ("C33", "C33"), ("C12", "C12"), ("C13", "C13"),
                         ("C44", "C44"), ("C66", "C66"), ("E1", "E1"), ("E3", "E3"),
                         ("G12", "G12"), ("G13", "G13"), ("nu12", "nu12"), ("nu31", "nu31")]

DIFF_SERIES = [("E1", "E₁", "#17becf"), ("E3", "E₃", "#bcbd22"), ("G12", "G₁₂", "#e377c2"),
               ("G13", "G₁₃", "#7f7f7f"), ("nu12", "ν₁₂", "#d62728"), ("nu31", "ν₃₁", "#2ca02c")]


def generate_comparison_report(rows, values, rundir: Path, keys=None) -> None:
    """Numeric FFT vs ANSYS diff table — optional, off unless cfg.comparison_report is True."""
    keys = keys or COMPOSITE_REPORT_KEYS
    lines = ["=" * 90, "Порівняння розв'язувачів FFT та ANSYS", "=" * 90]
    csv_rows = []
    for v in values:
        for k, name in keys:
            fft, _, _ = extract_series(rows, [v], k, solver="fft")
            ansys, _, _ = extract_series(rows, [v], k, solver="ansys")
            f0, a0 = fft[0], ansys[0]
            if not np.isnan(f0) and not np.isnan(a0):
                diff = abs(f0 - a0)
                rel = diff / abs(a0) * 100 if abs(a0) > 1e-12 else 0.0
                lines.append(f"{v:<9.2f} | {name:<8} | FFT={f0:<12.5g} | ANSYS={a0:<12.5g} | diff={diff:<10.5g} | {rel:.3f}%")
                csv_rows.append({"sweep_value": f"{v:.4f}", "property": name, "fft": f"{f0:.6g}",
                                  "ansys": f"{a0:.6g}", "abs_diff": f"{diff:.6g}", "rel_diff_pct": f"{rel:.4f}"})
    text = "\n".join(lines)
    (rundir / "comparison_summary.txt").write_text(text + "\n", encoding="utf-8")
    if csv_rows:
        with (rundir / "comparison_summary.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["sweep_value", "property", "fft", "ansys", "abs_diff", "rel_diff_pct"])
            w.writeheader()
            w.writerows(csv_rows)
    print(text)


def plot_solver_diff(cfg: SweepConfig, rows, values, rundir: Path) -> Path:
    """Signed FFT vs ANSYS relative difference per sweep point, with the +/- tolerance band."""
    x = np.array(values)
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for key, label, color in DIFF_SERIES:
        f, _, _ = extract_series(rows, values, key, solver="fft")
        a, _, _ = extract_series(rows, values, key, solver="ansys")
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = (f - a) / np.abs(a) * 100
        if np.all(np.isnan(rel)):
            continue
        ax.plot(x, rel, color=color, marker="o", ms=5, lw=1.8, label=label)
    tol = cfg.solver_tolerance_pct
    ax.axhspan(-tol, tol, color="#eeeeee", zorder=0)
    for y in (-tol, tol):
        ax.axhline(y, linestyle=":", color="#555555", linewidth=1.3)
    ax.axhline(0.0, color="#555555", linewidth=0.8)
    ax.plot([], [], linestyle=":", color="#555555", label=f"допуск ±{tol:g}%")
    ax.set_title("Розбіжність FFT відносно ANSYS", fontsize=11, fontweight="bold", pad=10)
    ax.set_xlabel(cfg.axis_label, fontsize=10)
    ax.set_ylabel("(FFT − ANSYS) / ANSYS, %", fontsize=10)
    ax.legend(fontsize=8, frameon=True, facecolor="white", edgecolor="#d0d0d0", ncol=2)
    ax.grid(True, linestyle="--", linewidth=0.6, color="#dcdcdc")
    fig.tight_layout()
    png = rundir / "comparison.png"
    fig.savefig(png, dpi=cfg.dpi, bbox_inches="tight")
    fig.savefig(rundir / "comparison.eps", bbox_inches="tight")
    plt.close(fig)
    return png


def _bound_curves(cfg: SweepConfig, rows, values) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Voigt/Reuss E_i, G_ij at each sweep point, from the mean Vf actually built there."""
    if not (composite_ref.known_material(cfg.matrix_material) and composite_ref.known_material(cfg.fiber_material)):
        return {}
    vf, _, _ = extract_series(rows, values, "vf_actual")
    keys = ("E1", "E2", "E3", "G23", "G13", "G12")
    up = {k: np.full(len(values), np.nan) for k in keys}
    lo = {k: np.full(len(values), np.nan) for k in keys}
    for n, f in enumerate(vf):
        if np.isnan(f):
            continue
        Cv, Cr = composite_ref.bounds(cfg.matrix_material, cfg.fiber_material, float(f), cfg.composite_dim)
        ev, er = composite_ref.engineering_constants(Cv), composite_ref.engineering_constants(Cr)
        for k in keys:
            up[k][n], lo[k][n] = ev[k], er[k]
    return {k: (lo[k], up[k]) for k in keys}


def write_criteria_report(cfg: SweepConfig, rows, values, solvers, rundir: Path) -> Path:
    """Pass/fail summary of the composite acceptance criteria."""
    lines = ["=" * 90, f"Критерії прийнятності: {cfg.name}", "=" * 90,
             f"Vf: |досягнута - цільова| <= {cfg.vf_tolerance}",
             f"Межі: Reuss*(1-{cfg.bounds_tolerance}) <= E_i, G_ij <= Voigt*(1+{cfg.bounds_tolerance})",
             f"FFT vs ANSYS: розбіжність <= {cfg.solver_tolerance_pct}%", ""]
    n_bad = 0
    for r in rows:
        flags = []
        if str(r.get("vf_ok", "")) == "0":
            flags.append(f"Vf={r.get('vf_actual')} (ціль {r.get('vf_target')})")
        if str(r.get("bounds_ok", "")) == "0":
            flags.append(f"поза межами Voigt/Reuss: {r.get('bounds_violations')}")
        if flags:
            n_bad += 1
            lines.append(f"{r['solver'].upper():<6} x={float(r['sweep_value']):<8.4g} r={r['realization']}: " + "; ".join(flags))
    if n_bad == 0:
        lines.append(f"Усі {len(rows)} розрахунків відповідають критеріям Vf та меж.")

    if {"fft", "ansys"} <= set(solvers):
        lines.append("")
        worst = []
        for v in values:
            for k, name in COMPOSITE_REPORT_KEYS:
                f0 = extract_series(rows, [v], k, solver="fft")[0][0]
                a0 = extract_series(rows, [v], k, solver="ansys")[0][0]
                if np.isnan(f0) or np.isnan(a0) or abs(a0) < 1e-12:
                    continue
                rel = abs(f0 - a0) / abs(a0) * 100
                if rel > cfg.solver_tolerance_pct:
                    worst.append(f"x={v:<8.4g} {name:<5} FFT={f0:<10.5g} ANSYS={a0:<10.5g} {rel:.2f}%")
        lines += (["FFT vs ANSYS понад допуск:"] + worst) if worst else ["FFT vs ANSYS: усі величини в межах допуску."]

    path = rundir / "criteria_summary.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return path


def plot_composite(cfg: SweepConfig, rows, rundir: Path) -> tuple[Path, Path]:
    values = cfg.sweep_values
    x = np.array(values)
    present_solvers = sorted({r.get("solver", "fft").strip().lower() for r in rows})
    is_comparison = len(present_solvers) > 1
    has_spread = max((int(r.get("realization", 0)) for r in rows), default=0) > 0

    fig, ax = plt.subplots(1, 3, figsize=(17, 5.5), sharex=True)

    _plot_panel(ax[0], rows, x, values,
                [("C11", "C₁₁", "#1f77b4"), ("C33", "C₃₃", "#9467bd"), ("C12", "C₁₂", "#ff7f0e"),
                 ("C13", "C₁₃", "#2ca02c"), ("C44", "C₄₄", "#d62728"), ("C66", "C₆₆", "#8c564b")],
                present_solvers, cfg, is_comparison, has_spread,
                "Ефективні компоненти жорсткості C", "Компоненти C, ГПа")
    ax[0].set_yscale("log")

    moduli = [("E1", "E₁", "#17becf"), ("E3", "E₃", "#bcbd22"),
              ("G12", "G₁₂", "#e377c2"), ("G13", "G₁₃", "#7f7f7f")]
    _plot_panel(ax[1], rows, x, values, moduli, present_solvers, cfg, is_comparison, has_spread,
                "Пружні сталі та межі Фойгта/Ройсса", "Модулі, ГПа")
    for k, (lo, up) in _bound_curves(cfg, rows, values).items():
        color = next((c for kk, _, c in moduli if kk == k), None)
        if color is None:
            continue
        ax[1].plot(x, up, color=color, linestyle=":", lw=1.2, zorder=1)
        ax[1].plot(x, lo, color=color, linestyle="-.", lw=1.0, zorder=1)
    ax[1].plot([], [], color="#555555", linestyle=":", lw=1.2, label="межа Фойгта")
    ax[1].plot([], [], color="#555555", linestyle="-.", lw=1.0, label="межа Ройсса")
    ax[1].set_yscale("log")
    ax[1].legend(fontsize=8, frameon=True, facecolor="white", edgecolor="#d0d0d0", ncol=2)

    _plot_panel(ax[2], rows, x, values,
                [("anisoE", "E_max / E_min", "#b2182b")],
                present_solvers, cfg, is_comparison, has_spread,
                "Ступінь анізотропії", "E_max / E_min")
    ax[2].axhline(1.0, linestyle=":", color="#555555", linewidth=1.3, label="ізотропний стан")
    ax[2].legend(fontsize=8, frameon=True, facecolor="white", edgecolor="#d0d0d0")

    title = (f"{cfg.fiber_material} / {cfg.matrix_material}, {cfg.composite_dim}, {cfg.packing}: "
             f"{'FFT vs ANSYS' if is_comparison else present_solvers[0].upper()}")
    fig.suptitle(title, fontsize=12, fontweight="bold", y=1.02)
    fig.tight_layout()

    png = rundir / "sweep.png"
    eps = rundir / "sweep.eps"
    fig.savefig(png, dpi=cfg.dpi, bbox_inches="tight")
    fig.savefig(eps, bbox_inches="tight")
    plt.close(fig)

    write_criteria_report(cfg, rows, values, present_solvers, rundir)
    if is_comparison:
        plot_solver_diff(cfg, rows, values, rundir)
    if cfg.comparison_report and is_comparison:
        generate_comparison_report(rows, values, rundir, COMPOSITE_REPORT_KEYS)
    return png, eps


def plot_results(cfg: SweepConfig) -> tuple[Path, Path]:
    rundir = Path(cfg.rundir)
    rows = load_sweep_data(rundir / "results.csv")
    if not rows:
        raise ValueError("results.csv is empty")
    rows += reference_rows(cfg, rows)
    return plot_composite(cfg, rows, rundir)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in CONFIGS:
        print(f"Usage: python plot.py <config_name>\nAvailable: {', '.join(sorted(CONFIGS))}", file=sys.stderr)
        raise SystemExit(1)
    cfg = CONFIGS[sys.argv[1]]
    png, eps = plot_results(cfg)
    print(f"PNG -> {png}\nEPS -> {eps}")


if __name__ == "__main__":
    main()
