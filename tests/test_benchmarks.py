"""Independent benchmark tests for the drying model.

Runs with pytest (`pytest -q tests`) or directly (`python tests/test_benchmarks.py`).
"""
from __future__ import annotations

import os
import sys

import numpy as np
from scipy.special import j0, j1, jn_zeros

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from drying_model.grid import FixedGrid, MaterialGrid          # noqa: E402
from drying_model.rhs import make_fixed_rhs, make_shrink_rhs   # noqa: E402
from drying_model.solve import make_atol, run_legs             # noqa: E402


class _ConstProps:
    def rho(self, C):
        return np.full(np.shape(C), 1.0)

    def cp(self, C):
        return np.full(np.shape(C), 1.0)

    def k(self, C):
        return np.full(np.shape(C), 1.0)


class _ZeroEnv:
    def __call__(self, t):
        s = np.ndim(t) == 0
        t = np.atleast_1d(np.asarray(t, float))
        z = np.zeros_like(t)
        return (0.0, 0.0) if s else (z, z)


class _ConstRadius:
    def __init__(self, v):
        self.v = float(v)

    def __call__(self, t):
        return self.v if np.ndim(t) == 0 else np.full(np.shape(t), self.v, float)


def test_grid_geometry():
    g = FixedGrid(0.02, 320)
    assert abs(g.V.sum() - np.pi * 0.02 ** 2) < 1e-15
    assert abs(g.AL[0]) < 1e-18
    assert abs(g.AR[-1] - 2 * np.pi * 0.02) < 1e-14
    m = MaterialGrid(320)
    assert abs(m.V.sum() - np.pi) < 1e-14
    assert abs(m.AR[-1] - 2 * np.pi) < 1e-14


def test_dirichlet_cylinder_analytic():
    R0, D, N, t = 0.02, 1e-8, 320, 1000.0
    grid = FixedGrid(R0, N)
    n = grid.n_nodes

    class P(_ConstProps):
        def D(self, C, T):
            return np.full(np.shape(C), D)

    fun, sp = make_fixed_rhs(P(), grid, _ZeroEnv(), hT=0.0, hC=1e3)
    y0 = np.concatenate((np.zeros(n), np.ones(n)))
    atol = make_atol(n, 1e-10, 1e-12)
    traj, _, _, _ = run_legs(fun, y0, [[0.0, t, 10.0]], atol, 1e-10, sp)
    C = traj(np.array([t]))[0][n:]

    lam = jn_zeros(0, 60)
    ana = np.zeros_like(grid.r)
    for lm in lam:
        ana += 2.0 * j0(lm * grid.r / R0) / (lm * j1(lm)) * np.exp(-lm ** 2 * D * t / R0 ** 2)
    assert np.max(np.abs(C - ana)) < 1e-4


def test_shrink_fixed_radius_limit():
    R0, N, t = 0.02, 320, 1000.0
    g = FixedGrid(R0, N)
    n = g.n_nodes

    class P(_ConstProps):
        def D(self, C, T):
            return np.full(np.shape(C), 1e-8)

    atol = make_atol(n, 1e-10, 1e-12)
    funF, spF = make_fixed_rhs(P(), g, _ZeroEnv(), hT=0.0, hC=1e3)
    y0 = np.concatenate((np.zeros(n), np.ones(n)))
    trajF, _, _, _ = run_legs(funF, y0, [[0.0, t, 10.0]], atol, 1e-10, spF)
    CF = trajF(np.array([t]))[0][n:]

    mg = MaterialGrid(N)
    funS, spS = make_shrink_rhs(P(), mg, _ConstRadius(R0), _ZeroEnv(), hT=0.0, hC=1e3)
    trajS, _, _, _ = run_legs(funS, y0, [[0.0, t, 10.0]], atol, 1e-10, spS)
    CS = trajS(np.array([t]))[0][n:]
    CS_on_r = np.interp(g.r / R0, mg.xi, CS)
    assert np.max(np.abs(CS_on_r - CF)) < 1e-12


if __name__ == "__main__":
    test_grid_geometry()
    print("test_grid_geometry OK")
    test_dirichlet_cylinder_analytic()
    print("test_dirichlet_cylinder_analytic OK")
    test_shrink_fixed_radius_limit()
    print("test_shrink_fixed_radius_limit OK")
    print("ALL BENCHMARK TESTS PASSED")
