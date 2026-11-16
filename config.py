"""
Configuration for the MatViz3D fiber-composite sweep tool.

One flat dataclass, no templates. To run something, edit one of the
scenarios below (or copy it under a new name) and run it from the
command line:

    python run.py vf_sweep_cf_epoxy
    python run.py vf_sweep_cf_epoxy --plot-only
    python run.py vf_sweep_cf_epoxy --report --force

Executable and DLL locations are read from environment variables so
nothing machine-specific is hardcoded in source:

    MATVIZ3D_EXE       -> full path to MatViz3D.exe
    MATVIZ3D_DLL_DIRS  -> DLL directories (Qt, HDF5, ...), separated by os.pathsep

Set them once in your shell/profile, or pass exe=/dll_dirs=... directly in
a config if you'd rather keep it explicit per-run.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SweepConfig:
    name: str

    # --- what's being swept --------------------------------------------
    sweep_axis: str = "vf"                       # "vf" | "size" | "jitter" | "fiber_scatter" | "aspect"
    start: float = 0.1
    stop: float = 0.6
    step: float = 0.1
    custom_values: Optional[List[float]] = None  # overrides start/stop/step if set

    # --- RVE and homogenization mode -------------------------------------
    mode: str = "stiffness"                        # "stiffness" (6 loads -> C, S) | "dataset" (+ random loads)
    size: int = 32                                 # voxel grid N, N^3 voxels (used when sweep_axis != "size")

    # --- fiber composite (MatViz3D "Composite" algorithm) ----------------------
    # Every parameter below is held fixed unless it is the swept one.
    # Fibers along Z for 1d, X+Y for 2d, X+Y+Z for 3d.
    matrix_material: str = "Epoxy"                 # any constituent in material_properties.db
    fiber_material: str = "C-fiber"                # C-fiber | E-glass | SiC | Al2O3 | ...
    composite_dim: str = "1d"                      # 1d | 2d | 3d
    packing: str = "hexagonal"                     # square | hexagonal
    vf: float = 0.4                                # target fiber volume fraction (sweep_axis != "vf")
    fibers_per_row: int = 4
    fiber_aspect_ratio: float = 1.0                # a/b of the cross-section, 1 = circular (sweep_axis != "aspect")
    fiber_angle_scatter: float = 0.0               # deg (sweep_axis != "fiber_scatter")
    fiber_center_jitter: float = 0.0               # half-pitches, 0..1 (sweep_axis != "jitter")
    fiber_allow_overlap: bool = False
    periodic: bool = True                          # FFT assumes a periodic cell; keep the geometry consistent

    # --- acceptance criteria (composite runs) ------------------------------------
    vf_tolerance: float = 0.01                     # |achieved - target| Vf above this is flagged
    bounds_tolerance: float = 0.01                 # relative slack on Reuss <= E_i, G_ij <= Voigt
    solver_tolerance_pct: float = 5.0              # FFT vs ANSYS difference flagged in the report

    # --- solvers & statistics --------------------------------------------
    solvers: List[str] = field(default_factory=lambda: ["fft", "ansys"])
    realizations: int = 5                          # seeds per sweep point (need >=2 for a nonzero band)
    seed_base: int = 1000

    # --- output -----------------------------------------------------------
    rundir: str = "runs/default"
    combined_hdf5: bool = True                     # collect every run as /1, /2, ... in <rundir>/<name>.hdf5
    dpi: int = 300
    band_sigma: float = 3.0                        # plotted band = mean +/- band_sigma * std
    comparison_report: bool = False                # also write the FFT vs ANSYS numeric table
    compare_with: Optional[str] = None             # scenario whose results.csv supplies the other solver

    # --- execution ----------------------------------------------------------
    exe: Optional[str] = None                      # None -> read MATVIZ3D_EXE env var
    dll_dirs: Optional[List[str]] = None            # None -> read MATVIZ3D_DLL_DIRS env var
    threads: Optional[int] = None
    ansys_np: int = 1                               # ANSYS DMP processes; each wants ~1-2 GB RAM up front
    stream: bool = True                             # stream MatViz3D's own stdout live
    force: bool = False                             # ignore checkpoint, recompute everything

    @property
    def sweep_values(self) -> List[float]:
        if self.custom_values is not None:
            return [round(float(v), 4) for v in self.custom_values]
        import numpy as np
        arr = np.arange(self.start, self.stop + 1e-6, self.step)
        return [round(float(v), 4) for v in arr]

    @property
    def is_comparison(self) -> bool:
        return len(self.solvers) > 1

    @property
    def axis_label(self) -> str:
        return {
            "size": "Розмір RVE N, вокселів",
            "vf": "Об'ємна частка волокон Vf",
            "jitter": "Зміщення центрів волокон, частка півкроку",
            "fiber_scatter": "Розкид кута повороту перерізу волокон, °",
            "aspect": "Відношення півосей перерізу волокна a/b",
        }[self.sweep_axis]


def resolve_exe(cfg: SweepConfig) -> str:
    """Find the MatViz3D executable: explicit cfg.exe, else MATVIZ3D_EXE env var."""
    exe = cfg.exe or os.environ.get("MATVIZ3D_EXE")
    if not exe or not os.path.isfile(exe):
        raise FileNotFoundError(
            "MatViz3D executable not found. Set the MATVIZ3D_EXE environment "
            f"variable or pass exe=... in the config. Got: {exe!r}"
        )
    return exe


def resolve_dll_dirs(cfg: SweepConfig) -> List[str]:
    """DLL search dirs: explicit cfg.dll_dirs, else MATVIZ3D_DLL_DIRS env var."""
    if cfg.dll_dirs is not None:
        return cfg.dll_dirs
    raw = os.environ.get("MATVIZ3D_DLL_DIRS", "")
    return [d for d in raw.split(os.pathsep) if d]


# ---------------------------------------------------------------------------
# Scenarios. Copy one and edit, or add your own — anything
# registered here shows up as a valid name on the command line.
# ---------------------------------------------------------------------------

CONFIGS: dict[str, SweepConfig] = {}


def _register(cfg: SweepConfig) -> SweepConfig:
    CONFIGS[cfg.name] = cfg
    return cfg


# ---------------------------------------------------------------------------
# Fiber composites. One fiber layout is deterministic,
# so realizations only matter when something random is switched on (center
# jitter); seeds are still passed for reproducibility.
# ---------------------------------------------------------------------------

# ANSYS runs with ansys_np = 1: by default MatViz3D starts one ANSYS process
# per core, and on an ~8 GB machine the workers fail to reserve memory
# (MatViz3D then crashes with 0xC0000005 on the missing results file).
COMPOSITE_SOLVERS = ["fft", "ansys"]

# Keep grid sizes at powers of two: MatViz3D's FFT is ~20x slower per voxel
# at N = 40 than at N = 32 (measured: 1.36 vs 0.054 GFLOP per iteration).

# Scenario 1: carbon/epoxy, effective constants vs fiber volume fraction
vf_sweep_cf_epoxy = _register(SweepConfig(
    name="vf_sweep_cf_epoxy", 
    sweep_axis="vf", start=0.1, stop=0.6, step=0.1,
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="square", fibers_per_row=2, size=32,
    solvers=COMPOSITE_SOLVERS, realizations=1,
    rundir="runs/vf_sweep_cf_epoxy",
))

# Scenario 2: same with isotropic E-glass fibers, the classic check against
# rule-of-mixtures / Voigt-Reuss bounds
vf_sweep_glass_epoxy = _register(SweepConfig(
    name="vf_sweep_glass_epoxy", 
    sweep_axis="vf", start=0.1, stop=0.6, step=0.1,
    matrix_material="Epoxy", fiber_material="E-glass",
    composite_dim="1d", packing="square", fibers_per_row=2, size=32,
    solvers=COMPOSITE_SOLVERS, realizations=1,
    rundir="runs/vf_sweep_glass_epoxy",
))

# Scenario 3: carbon/epoxy at Vf = 0.4, disorder of fiber placement
jitter_sweep_cf_epoxy = _register(SweepConfig(
    name="jitter_sweep_cf_epoxy", 
    sweep_axis="jitter", start=0.0, stop=0.6, step=0.1,
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="hexagonal", fibers_per_row=4, size=32, vf=0.4,
    solvers=COMPOSITE_SOLVERS, realizations=5,
    rundir="runs/jitter_sweep_cf_epoxy",
))

# Scenario 4: scenario 3 over the full jitter range MatViz3D accepts, 0..1
# half-pitches. Overlap stays off: a center that cannot be moved without touching
# a neighbour after 64 draws stays on its lattice site, and MatViz3D logs
# "[Composite] N fiber centers could not be jittered ..." to run.log -- watch for
# it near jitter = 1, where it means the effective disorder is below the nominal one.
jitter_full_sweep_cf_epoxy = _register(SweepConfig(
    name="jitter_full_sweep_cf_epoxy", 
    sweep_axis="jitter", start=0.0, stop=1.0, step=0.1,
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="hexagonal", fibers_per_row=4, size=32, vf=0.4,
    solvers=COMPOSITE_SOLVERS, realizations=5, comparison_report=True,
    rundir="runs/jitter_full_sweep_cf_epoxy",
))

# Scenario 5: carbon/epoxy at Vf = 0.4, voxel-resolution convergence of the RVE
size_sweep_cf_epoxy = _register(SweepConfig(
    name="size_sweep_cf_epoxy", 
    sweep_axis="size", custom_values=[16, 32, 64],
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="square", fibers_per_row=2, vf=0.4,
    solvers=COMPOSITE_SOLVERS, realizations=1,
    rundir="runs/size_sweep_cf_epoxy",
))

# Scenario 6: carbon/epoxy vs Vf in MatViz3D's full "dataset" mode -- the six
# canonical loads (-> C, S) plus MatViz3D's own default set of Hill-distributed
# random load cases, all stored per run in the scenario's combined HDF5. The
# number of load cases is left to MatViz3D. ANSYS first: it is much faster here.
vf_dataset_cf_epoxy = _register(SweepConfig(
    name="vf_dataset_cf_epoxy", mode="dataset",
    sweep_axis="vf", start=0.1, stop=0.6, step=0.1,
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="square", fibers_per_row=2, size=32,
    solvers=["ansys", "fft"], realizations=1,
    rundir="runs/vf_dataset_cf_epoxy",
))

# Scenario 7: scenario 6 at N = 25, ANSYS only. At 32^3 phase 2 ran out of RAM;
# 25^3 needs ~4x less time per ANSYS solve (measured 76 s vs ~5 min in stiffness
# mode). Close PyCharm and start it with run_detached.ps1, not from an IDE/Claude shell.
vf_dataset_cf_epoxy_n25 = _register(SweepConfig(
    name="vf_dataset_cf_epoxy_n25", mode="dataset",
    sweep_axis="vf", start=0.1, stop=0.6, step=0.1,
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="square", fibers_per_row=2, size=25,
    solvers=["ansys"], realizations=1, ansys_np=1,
    rundir="runs/vf_dataset_cf_epoxy_n25",
))

# Benchmark: one FFT stiffness solve set at N = 25 (Bluestein path), Vf = 0.1,
# to measure the time per load case before committing to an FFT dataset run.
fft_bench_n25 = _register(SweepConfig(
    name="fft_bench_n25", mode="stiffness",
    sweep_axis="vf", custom_values=[0.1],
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="square", fibers_per_row=2, size=25,
    solvers=["fft"], realizations=1,
    rundir="runs/fft_bench_n25",
))

# Scenario 8: scenario 7 with the FFT solver (same N = 25 geometry, for the
# FFT vs ANSYS comparison). Release build: ~25 s per solve, 456 solves per
# unit (6 + 150 calibration + 300), ~3 h per unit.
vf_dataset_cf_epoxy_n25_fft = _register(SweepConfig(
    name="vf_dataset_cf_epoxy_n25_fft", mode="dataset",
    sweep_axis="vf", start=0.1, stop=0.6, step=0.1,
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="square", fibers_per_row=2, size=25,
    solvers=["fft"], realizations=1,
    compare_with="vf_dataset_cf_epoxy_n25", comparison_report=True,
    rundir="runs/vf_dataset_cf_epoxy_n25_fft",
))

# ---------------------------------------------------------------------------
# Elliptical fibers: cross-section a/b and in-plane rotation scatter, one fiber
# per row (square packing -> exactly one fiber per periodic cell, so each
# realization is a single ellipse rotated by theta ~ U(-scatter/2, scatter/2)).
#
# MatViz3D switches lattice at scatter = 0: aligned ellipses get a lattice
# stretched by a/b (2 rows -> 2 fibers per cell at a/b = 2), any scatter > 0
# keeps it 1 x 1. "No scatter" is therefore 0.001 deg, so every point of the
# grid has the same single-fiber cell. Rotated ellipses must fit with their
# major axis in any direction: Vf_max = (pi/4) / (a/b) = 0.26 at a/b = 3, so
# Vf = 0.2 keeps all points below the packing limit (no clamping).
# ---------------------------------------------------------------------------

ELLIPSE_SCATTERS = [0.001, 30, 60, 90, 120, 150, 180]
ELLIPSE_ASPECTS = [1.5, 2.0, 3.0]

# Scenario 9: properties vs a/b at no rotation (deterministic, 1 realization)
aspect_sweep_cf_epoxy = _register(SweepConfig(
    name="aspect_sweep_cf_epoxy", 
    sweep_axis="aspect", custom_values=[1.0, 1.5, 2.0, 2.5, 3.0],
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="square", fibers_per_row=1, size=32, vf=0.2,
    fiber_angle_scatter=0.001,
    solvers=COMPOSITE_SOLVERS, realizations=1, comparison_report=True,
    rundir="runs/aspect_sweep_cf_epoxy",
))

# Scenarios 10-12: properties vs rotation scatter, one per a/b, FFT then ANSYS. Seeds are shared
# across scenarios, so realization r draws the same relative angle everywhere.
for _ab in ELLIPSE_ASPECTS:
    _tag = f"ab{_ab:g}".replace(".", "")
    _register(SweepConfig(
        name=f"fscatter_{_tag}_cf_epoxy", 
        sweep_axis="fiber_scatter", custom_values=ELLIPSE_SCATTERS,
        matrix_material="Epoxy", fiber_material="C-fiber",
        composite_dim="1d", packing="square", fibers_per_row=1, size=32, vf=0.2,
        fiber_aspect_ratio=_ab,
        solvers=COMPOSITE_SOLVERS, realizations=5, comparison_report=True,
        rundir=f"runs/fscatter_{_tag}_cf_epoxy",
    ))

# Scenarios 13-16: the same family in MatViz3D's "dataset" mode (six canonical
# loads + Hill-distributed random load cases, as in scenarios 6-8), ANSYS then
# FFT in one scenario. N = 25 because ANSYS dataset at 32^3 runs out of RAM.
# Reduced grid, one realization per point: ~1.4 h per unit in ANSYS, ~3.5 h in
# FFT. Close PyCharm while the ANSYS part runs (free RAM drops to a few MB).
DATASET_SCATTERS = [0.001, 90, 180]

aspect_dataset_cf_epoxy_n25 = _register(SweepConfig(
    name="aspect_dataset_cf_epoxy_n25", mode="dataset",
    sweep_axis="aspect", custom_values=[1.0],
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="square", fibers_per_row=1, size=25, vf=0.2,
    fiber_angle_scatter=0.001,
    solvers=["ansys", "fft"], realizations=1, ansys_np=1, comparison_report=True,
    rundir="runs/aspect_dataset_cf_epoxy_n25",
))

for _ab in ELLIPSE_ASPECTS:
    _tag = f"ab{_ab:g}".replace(".", "")
    _register(SweepConfig(
        name=f"fscatter_{_tag}_dataset_cf_epoxy_n25", mode="dataset",
        sweep_axis="fiber_scatter", custom_values=DATASET_SCATTERS,
        matrix_material="Epoxy", fiber_material="C-fiber",
        composite_dim="1d", packing="square", fibers_per_row=1, size=25, vf=0.2,
        fiber_aspect_ratio=_ab,
        solvers=["ansys", "fft"], realizations=1, ansys_np=1, comparison_report=True,
        rundir=f"runs/fscatter_{_tag}_dataset_cf_epoxy_n25",
    ))
