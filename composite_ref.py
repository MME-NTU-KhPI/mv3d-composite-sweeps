"""
Reference values for fiber-composite runs: constituent stiffnesses, Voigt/Reuss
bounds, and engineering constants from an effective stiffness tensor.

The constituent table mirrors the "Composite constituents" seeds in MatViz3D's
dbmanager.cpp (material_properties.db, GPa, standard Voigt order
11,22,33,23,13,12). Update it in lockstep if the DB values change.

Bounds are what the homogenized result is checked against:
    Reuss (uniform stress)  <=  effective  <=  Voigt (uniform strain)
For composite_dim 2d/3d each fiber family is given an equal share of the fiber
volume, which ignores who owns the voxels where families cross -- so for those
the bounds are approximate; for 1d they are exact.
"""
from __future__ import annotations

import numpy as np

# Upper triangle per row: c11 c12 c13 | c22 c23 | c33 | c44 | c55 | c66 (GPa).
# All constituents in the DB are iso or transversely isotropic about axis 3,
# so the off-orthotropic terms are zero.
_DB = {
    #           c11     c12     c13     c22     c23     c33     c44     c55     c66
    "Epoxy":   (5.62,   3.02,   3.02,   5.62,   3.02,   5.62,   1.30,   1.30,   1.30),
    "E-glass": (82.20,  23.19,  23.19,  82.20,  23.19,  82.20,  29.51,  29.51,  29.51),
    "Al2O3":   (433.85, 122.37, 122.37, 433.85, 122.37, 433.85, 155.74, 155.74, 155.74),
    "SiC":     (429.58, 69.93,  69.93,  429.58, 69.93,  429.58, 179.82, 179.82, 179.82),
    "C-fiber": (15.12,  1.10,   3.24,   15.12,  3.24,   231.30, 15.00,  15.00,  7.01),
}

# Fiber families per composite_dim, as the global axis (0=X, 1=Y, 2=Z) each runs along.
_FAMILIES = {"1d": [2], "2d": [0, 1], "3d": [0, 1, 2]}

# Voigt index pairs in the standard order used by the DB.
_VOIGT = [(0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1)]


# MatViz3D's C_matrix is in its "pipeline" basis: column j is the stress from a
# unit TENSOR strain, components ordered (xx, yy, zz, xy, yz, xz) -- so its
# shear diagonal is 2G and the normal/shear block is (2X, X), not symmetric.
# Standard Voigt index -> pipeline index:
_PIPE_OF_STD = [0, 1, 2, 4, 5, 3]


def pipeline_to_voigt(Cp: np.ndarray, engineering_shear: bool = False) -> np.ndarray:
    """MatViz3D pipeline-basis C -> standard Voigt C (engineering shear, order 11,22,33,23,13,12).

    Older MatViz3D builds wrote C_matrix columns for a unit *tensor* shear strain
    (no attribute), so its shear columns are twice the engineering ones and are
    halved here. Newer builds tag C_matrix with shear_basis="engineering" and
    already use unit engineering shear; pass engineering_shear=True for those.
    """
    C = Cp[np.ix_(_PIPE_OF_STD, _PIPE_OF_STD)].astype(float).copy()
    if not engineering_shear:
        C[:, 3:] *= 0.5    # unit tensor shear strain = engineering shear strain of 2
    return C


def known_material(name: str) -> bool:
    return name in _DB


def constituent_C(name: str) -> np.ndarray:
    """6x6 stiffness (GPa) of a DB constituent, material frame, standard Voigt."""
    c11, c12, c13, c22, c23, c33, c44, c55, c66 = _DB[name]
    return np.array([
        [c11, c12, c13, 0, 0, 0],
        [c12, c22, c23, 0, 0, 0],
        [c13, c23, c33, 0, 0, 0],
        [0, 0, 0, c44, 0, 0],
        [0, 0, 0, 0, c55, 0],
        [0, 0, 0, 0, 0, c66],
    ], dtype=float)


def _voigt_to_tensor(C: np.ndarray) -> np.ndarray:
    T = np.zeros((3, 3, 3, 3))
    for I, (i, j) in enumerate(_VOIGT):
        for J, (k, l) in enumerate(_VOIGT):
            for a, b in ((i, j), (j, i)):
                for c, d in ((k, l), (l, k)):
                    T[a, b, c, d] = C[I, J]
    return T


def _tensor_to_voigt(T: np.ndarray) -> np.ndarray:
    return np.array([[T[i, j, k, l] for (k, l) in _VOIGT] for (i, j) in _VOIGT])


def _fiber_C_along(C_mat: np.ndarray, axis: int) -> np.ndarray:
    """Rotate a fiber's stiffness so its material axis 3 lies along global `axis`."""
    if axis == 2:
        return C_mat
    # Cyclic permutation taking material 3 -> global `axis`; transverse
    # isotropy makes the in-plane assignment irrelevant.
    perm = {0: (1, 2, 0), 1: (2, 0, 1)}[axis]   # perm[m] = global index of material axis m
    Q = np.zeros((3, 3))
    for m, g in enumerate(perm):
        Q[g, m] = 1.0
    T = np.einsum("ai,bj,ck,dl,ijkl->abcd", Q, Q, Q, Q, _voigt_to_tensor(C_mat))
    return _tensor_to_voigt(T)


def bounds(matrix: str, fiber: str, vf: float, dim: str = "1d") -> tuple[np.ndarray, np.ndarray]:
    """(C_voigt, C_reuss), 6x6 in GPa, standard Voigt order."""
    Cm = constituent_C(matrix)
    Cf = constituent_C(fiber)
    fams = _FAMILIES[dim]
    share = vf / len(fams)
    C_v = (1 - vf) * Cm
    S_r = (1 - vf) * np.linalg.inv(Cm)
    for ax in fams:
        Cfa = _fiber_C_along(Cf, ax)
        C_v = C_v + share * Cfa
        S_r = S_r + share * np.linalg.inv(Cfa)
    return C_v, np.linalg.inv(S_r)


def engineering_constants(C: np.ndarray) -> dict[str, float]:
    """E_i, G_ij, nu_ij from a 6x6 stiffness in standard Voigt order (11,22,33,23,13,12)."""
    S = np.linalg.inv(C)
    return {
        "E1": 1 / S[0, 0], "E2": 1 / S[1, 1], "E3": 1 / S[2, 2],
        "G23": 1 / S[3, 3], "G13": 1 / S[4, 4], "G12": 1 / S[5, 5],
        "nu12": -S[0, 1] / S[0, 0],   # transverse plane for 1d fibers along Z
        "nu31": -S[0, 2] / S[2, 2],   # major (load along Z, contraction along X)
    }
