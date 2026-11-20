#!/usr/bin/env python3
"""
Run one of the fiber-composite sweep scenarios defined in config.py, then plot it.

    python run.py vf_sweep_cf_epoxy
    python run.py vf_sweep_cf_epoxy --plot-only
    python run.py vf_sweep_cf_epoxy --report --force

Each unit's result prints the moment it's computed, so you can watch the
numbers scroll by and catch a bad run mid-sweep instead of only at the end.
Finished units are checkpointed to results.csv; re-running the same
scenario skips whatever's already done.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

import h5py
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymv3d import MatViz3DLauncher, GenParams, StressParams, MatViz3DResult

from config import CONFIGS, SweepConfig, resolve_exe, resolve_dll_dirs
from plot import plot_results
import composite_ref

C_KEYS = ["C11", "C12", "C13", "C22", "C23", "C33", "C44", "C55", "C66"]
C_IDX = {
    "C11": (0, 0), "C12": (0, 1), "C13": (0, 2),
    "C22": (1, 1), "C23": (1, 2),
    "C33": (2, 2), "C44": (3, 3), "C55": (4, 4), "C66": (5, 5),
}

# Result rows: C in standard Voigt (engineering shear, 11,22,33,23,13,12), GPa,
# engineering constants, and the acceptance-criteria columns.
ENG_KEYS = ["E1", "E2", "E3", "G23", "G13", "G12", "nu12", "nu31"]
CRIT_KEYS = ["vf_target", "vf_actual", "vf_ok", "anisoE", "bounds_ok", "bounds_violations"]
FIELDS = ["sweep_value", "realization", "seed", "solver"] + C_KEYS + ENG_KEYS + CRIT_KEYS


def raw_path(cfg: SweepConfig, value: float, real: int, solver: str, raw_dir: Path) -> Path:
    """Per-unit HDF5 that MatViz3D writes (merged into the combined file afterwards)."""
    tag = f"{value:08.4f}"
    return raw_dir / f"{solver}_{cfg.sweep_axis}{tag}_r{real}.hdf5"


# Attributes that identify one unit inside the combined file.
UNIT_KEYS = ("sweep_axis", "sweep_value", "realization", "solver")


def merge_into_combined(src: Path, combined: Path, attrs: dict[str, Any]) -> str:
    """Append MatViz3D's set /1 from `src` to `combined` as the next set /n, tagged
    with `attrs`, keeping MatViz3D's own layout (/n groups + /last_set) so the
    file still opens in MatViz3D and pymv3d. Deletes `src` afterwards."""
    with h5py.File(src, "r") as fs, h5py.File(combined, "a") as fc:
        # A copy left behind by a run interrupted between merge and checkpoint.
        for k in [k for k in fc if k.isdigit()]:
            if all(str(fc[k].attrs.get(a)) == str(attrs[a]) for a in UNIT_KEYS):
                del fc[k]
        n = max((int(k) for k in fc if k.isdigit()), default=0) + 1
        fs.copy(fs["1"], fc, name=str(n))
        for a, v in attrs.items():
            fc[str(n)].attrs[a] = v
        if "last_set" in fc:
            fc["last_set"][()] = n
        else:
            fc.create_dataset("last_set", data=np.int32(n))
    src.unlink()
    return str(n)


def geometry_attrs(cfg: SweepConfig, value: float) -> dict[str, Any]:
    """Fiber-shape parameters of one composite unit, so a set stays self-describing
    once it is taken out of its scenario's file."""
    gen = composite_gen(cfg, value, cfg.seed_base)
    return {"fiber_aspect_ratio": float(gen.fiber_aspect_ratio),
            "fiber_angle_scatter": float(gen.fiber_angle_scatter)}


def backfill_geometry_attrs(cfg: SweepConfig, combined: Path) -> None:
    """Add geometry_attrs to sets stored before those attributes were recorded."""
    if not combined.exists():
        return
    with h5py.File(combined, "a") as fc:
        for k in [k for k in fc if k.isdigit()]:
            g = fc[k]
            if "fiber_aspect_ratio" in g.attrs or "sweep_value" not in g.attrs:
                continue
            for a, v in geometry_attrs(cfg, float(g.attrs["sweep_value"])).items():
                g.attrs[a] = v
            print(f"  backfilled fiber geometry attributes on /{k} in {combined}")


def load_done(csv_path: Path) -> tuple[list[dict[str, Any]], set[tuple[float, int, str]]]:
    if not csv_path.exists():
        return [], set()
    rows = list(csv.DictReader(csv_path.open(newline="", encoding="utf-8")))
    done = set()
    for r in rows:
        try:
            done.add((round(float(r["sweep_value"]), 4), int(r["realization"]), r.get("solver", "fft").strip().lower()))
        except (KeyError, ValueError):
            continue
    return rows, done


def save_atomic(csv_path: Path, rows: list[dict[str, Any]], fields: list[str] = FIELDS) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = csv_path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    os.replace(tmp, csv_path)


def solver_np(cfg: SweepConfig, solver: str) -> int | None:
    """--np for this solver: FFT threads, or ANSYS distributed processes."""
    return cfg.ansys_np if solver == "ansys" else cfg.threads


def stress_params(cfg: SweepConfig, solver: str, raw_dir: Path) -> StressParams:
    # ANSYS scratch goes under raw/ instead of littering the directory run.py is started from.
    workdir = str((raw_dir / "ansys_work").resolve()) if solver == "ansys" else None
    if workdir:
        os.makedirs(workdir, exist_ok=True)
    return StressParams(run=True, solver=solver, mode=cfg.mode, working_directory=workdir)


def composite_gen(cfg: SweepConfig, value: float, seed: int, solver: str = "fft") -> GenParams:
    """GenParams for one fiber-composite RVE, with the swept quantity set to `value`."""
    return GenParams(
        size=int(round(value)) if cfg.sweep_axis == "size" else cfg.size,
        algorithm="Composite", seed=seed, np=solver_np(cfg, solver), periodic=cfg.periodic,
        concentration=None,
        composite_dim=cfg.composite_dim, composite_packing=cfg.packing,
        fiber_volume_fraction=value if cfg.sweep_axis == "vf" else cfg.vf,
        fibers_per_row=cfg.fibers_per_row,
        fiber_aspect_ratio=value if cfg.sweep_axis == "aspect" else cfg.fiber_aspect_ratio,
        fiber_angle_scatter=value if cfg.sweep_axis == "fiber_scatter" else cfg.fiber_angle_scatter,
        fiber_center_jitter=value if cfg.sweep_axis == "jitter" else cfg.fiber_center_jitter,
        fiber_allow_overlap=cfg.fiber_allow_overlap,
        matrix_material=cfg.matrix_material, fiber_material=cfg.fiber_material,
    )


def _c_shear_basis(r: "MatViz3DResult", g: int) -> str:
    """shear_basis attribute of C_matrix ("engineering" in newer MatViz3D builds, "" if absent)."""
    with h5py.File(r.file_path, "r") as f:
        ds = f[r._group_name(g)].get("C_matrix")
        if ds is None:
            return ""
        v = ds.attrs.get("shear_basis", "")
        return (v.decode() if isinstance(v, bytes) else str(v)).strip().lower()


def composite_row(cfg: SweepConfig, r: "MatViz3DResult", gen: GenParams) -> dict[str, Any] | None:
    """Effective constants + acceptance criteria for one result."""
    Cp = r.stiffness(0)
    if Cp is None:
        return None
    C = composite_ref.pipeline_to_voigt(Cp, engineering_shear=_c_shear_basis(r, 0) == "engineering") / 1e9  # GPa, standard Voigt
    eng = composite_ref.engineering_constants(C)

    # Matrix voxels carry grain id 1 (Composite::MatrixId); every fiber has its own id.
    vf_actual = float(np.mean(r.voxels(0) != 1)) if r.has_voxels(0) else float("nan")
    vf_target = gen.fiber_volume_fraction

    row: dict[str, Any] = {"vf_target": f"{vf_target:.4f}", "vf_actual": f"{vf_actual:.4f}"}
    row["vf_ok"] = int(abs(vf_actual - vf_target) <= cfg.vf_tolerance) if np.isfinite(vf_actual) else ""
    for k in C_KEYS:
        i, j = C_IDX[k]
        row[k] = f"{C[i, j]:.6g}"
    for k in ENG_KEYS:
        row[k] = f"{eng[k]:.6g}"
    Es = [eng["E1"], eng["E2"], eng["E3"]]
    row["anisoE"] = f"{max(Es) / min(Es):.6g}"

    # Reuss <= effective <= Voigt for every modulus, at the voxel fraction actually built.
    if np.isfinite(vf_actual) and composite_ref.known_material(cfg.matrix_material) \
            and composite_ref.known_material(cfg.fiber_material):
        Cv, Cr = composite_ref.bounds(cfg.matrix_material, cfg.fiber_material, vf_actual, cfg.composite_dim)
        up, lo = composite_ref.engineering_constants(Cv), composite_ref.engineering_constants(Cr)
        tol = cfg.bounds_tolerance
        bad = [k for k in ("E1", "E2", "E3", "G23", "G13", "G12")
               if not lo[k] * (1 - tol) <= eng[k] <= up[k] * (1 + tol)]
        row["bounds_ok"] = int(not bad)
        row["bounds_violations"] = " ".join(bad)
    return row


def run_one(mv: "MatViz3DLauncher", cfg: SweepConfig, value: float, real: int, raw_dir: Path,
            solver: str) -> dict[str, Any] | None:
    """Generate one composite RVE, homogenize it with `solver` and extract the properties."""
    seed = cfg.seed_base + real
    out = raw_path(cfg, value, real, solver, raw_dir)
    if out.exists():
        try:
            out.unlink()  # avoid appending into a half-written file
        except OSError:
            pass

    gen = composite_gen(cfg, value, seed, solver)
    stress = stress_params(cfg, solver, raw_dir)
    res = mv.run(gen, stress, output=str(out), nologo=False, stream=cfg.stream)
    if not res.ok:
        return None
    try:
        row = composite_row(cfg, MatViz3DResult(str(out)), gen)
    except Exception as e:
        print(f"  -> Error reading output {out}: {e}", file=sys.stderr)
        return None
    if row is not None:
        row.update({"sweep_value": f"{value:.4f}", "realization": real, "seed": seed, "solver": solver})
    return row


def obtain_data(cfg: SweepConfig, limit: int | None = None) -> Path:
    for d in resolve_dll_dirs(cfg):
        if d and os.path.isdir(d) and d.lower() not in os.environ.get("PATH", "").lower():
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")

    exe_path = resolve_exe(cfg)
    rundir = Path(cfg.rundir)
    raw_dir = rundir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_path = rundir / "results.csv"

    mv = MatViz3DLauncher(exe_path)
    values = cfg.sweep_values
    solvers = [s.strip().lower() for s in cfg.solvers]
    rows, done = ([], set()) if cfg.force else load_done(csv_path)
    # Solver-major order: one solver's whole sweep is finished before the next starts.
    plan = [(v, r, s) for s in solvers for v in values for r in range(cfg.realizations)]
    todo = [u for u in plan if u not in done]
    if limit is not None:
        todo = todo[:limit]
    combined = rundir / f"{cfg.name}.hdf5" if cfg.combined_hdf5 else None

    print(f"=== {cfg.name} ===")
    print(f"Sweeping    : {cfg.sweep_axis} over {values}")
    print(f"Composite   : {cfg.fiber_material} fibers in {cfg.matrix_material}, {cfg.composite_dim} "
          f"{cfg.packing}, {cfg.fibers_per_row}/row, solvers: {', '.join(solvers).upper()}")
    print(f"Realizations: {cfg.realizations} per point")
    print(f"Total units : {len(plan)} ({len(done)} done, {len(todo)} to do)\n")
    if combined is not None:
        backfill_geometry_attrs(cfg, combined)

    try:
        for n, (value, real, solv) in enumerate(todo, 1):
            print(f"[{n}/{len(todo)}] solver={solv.upper()} {cfg.sweep_axis}={value} r={real} ...", flush=True)
            row = run_one(mv, cfg, value, real, raw_dir, solv)
            if row is None:
                print("  -> FAILED (will retry on next run)")
                continue
            if combined is not None:
                attrs = {"sweep_axis": cfg.sweep_axis, "sweep_value": float(value),
                         "realization": real, "solver": solv, "seed": cfg.seed_base + real,
                         "mode": cfg.mode}
                attrs.update(geometry_attrs(cfg, value))
                attrs.update({k: row[k] for k in ("vf_target", "vf_actual") if row.get(k) not in (None, "")})
                set_id = merge_into_combined(raw_path(cfg, value, real, solv, raw_dir), combined, attrs)
                print(f"  -> stored as /{set_id} in {combined}")
            rows.append(row)
            save_atomic(csv_path, rows)
            flags = []
            if row.get("vf_ok") == 0:
                flags.append(f"Vf off target ({row['vf_actual']} vs {row['vf_target']})")
            if row.get("bounds_ok") == 0:
                flags.append(f"outside Voigt/Reuss: {row['bounds_violations']}")
            print(f"  -> OK: Vf={row['vf_actual']} E1={row['E1']} E3={row['E3']} "
                  f"G12={row['G12']} G13={row['G13']} GPa"
                  + (f"  !! {'; '.join(flags)}" if flags else ""))
    except KeyboardInterrupt:
        print("\nInterrupted. Finished units are saved; re-run to resume.")

    return csv_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", choices=sorted(CONFIGS), help="which scenario to run (see config.py)")
    ap.add_argument("--plot-only", action="store_true", help="skip simulation, just redraw from results.csv")
    ap.add_argument("--force", action="store_true", help="ignore checkpoint, recompute everything")
    ap.add_argument("--report", action="store_true", help="also write the FFT vs ANSYS comparison table")
    ap.add_argument("--threads", "--np", type=int, default=None, metavar="N",
                     help="OpenMP worker threads passed to MatViz3D as --np (default: config's value, or auto)")
    ap.add_argument("--ansys-np", type=int, default=None, metavar="N",
                     help="ANSYS distributed processes (default: config's ansys_np)")
    ap.add_argument("--limit", type=int, default=None, metavar="N",
                     help="compute at most N of the remaining units, then stop")
    args = ap.parse_args()

    cfg = CONFIGS[args.config]
    if args.force:
        cfg.force = True
    if args.report:
        cfg.comparison_report = True
    if args.threads is not None:
        cfg.threads = args.threads
    if args.ansys_np is not None:
        cfg.ansys_np = args.ansys_np

    if not args.plot_only:
        obtain_data(cfg, args.limit)

    csv_path = Path(cfg.rundir) / "results.csv"
    if csv_path.exists():
        png, eps = plot_results(cfg)
        print(f"\nPNG -> {png}\nEPS -> {eps}")
    else:
        print(f"No results yet at {csv_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
