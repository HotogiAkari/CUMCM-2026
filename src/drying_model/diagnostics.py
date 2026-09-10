"""Physical / numerical sanity checks and diagnostics."""
from __future__ import annotations

import numpy as np


def check_trajectory_finite(Y, name="trajectory"):
    if not np.isfinite(Y).all():
        bad = np.argwhere(~np.isfinite(Y))
        raise AssertionError("%s contains NaN/Inf at %d places (first %s)" % (name, bad.shape[0], bad[0]))


def check_grid_geometry(grid, kind="fixed", tol=1e-12):
    if kind == "fixed":
        total = grid.V.sum()
        expected = np.pi * grid.R0 ** 2
        assert abs(total - expected) <= tol * expected + 1e-18, "fixed grid volume mismatch"
        assert abs(grid.AL[0]) < 1e-18, "inner face area must be zero"
        assert abs(grid.AR[-1] - 2 * np.pi * grid.R0) < 1e-12, "outer face area mismatch"
    else:
        total = grid.V.sum()
        assert abs(total - np.pi) <= tol, "material grid volume mismatch"
        assert abs(grid.AL[0]) < 1e-18
        assert abs(grid.AR[-1] - 2 * np.pi) < 1e-12
    return True


def check_physical_ranges(T, C, T_lo=-50.0, T_hi=120.0, C_lo=-1e-9, C_hi=3.0):
    problems = []
    if np.nanmin(T) < T_lo or np.nanmax(T) > T_hi:
        problems.append("temperature out of [%g,%g]: min=%g max=%g" % (T_lo, T_hi, np.nanmin(T), np.nanmax(T)))
    if np.nanmin(C) < C_lo or np.nanmax(C) > C_hi:
        problems.append("moisture out of [%g,%g]: min=%g max=%g" % (C_lo, C_hi, np.nanmin(C), np.nanmax(C)))
    return problems


def moisture_balance_fixed(grid, traj, t_span, env, hC, R0, n_points=12001):
    """Moisture budget of the fixed domain: dM/dt = -A_R h_C (C_s - C_a)."""
    n = grid.n_nodes
    tg = np.linspace(t_span[0], t_span[1], n_points)
    Y = traj(tg)
    M = Y[:, n:] @ grid.V
    cs = Y[:, n:][:, -1]
    Ta, Ca = env(tg)
    flux = 2 * np.pi * R0 * hC * (cs - Ca)
    integral = np.trapz(flux, tg)
    resid = (M[-1] - M[0]) + integral
    scale = max(abs(M[0]), 1e-30)
    return {"M0": float(M[0]), "M_end": float(M[-1]), "flux_integral": float(integral),
            "absolute_residual": float(resid), "relative_residual": float(abs(resid) / scale)}


def moisture_balance_material(grid, traj, t_span, radius, env, hC, n_points=12001):
    """Reference (material-coordinate) moisture balance for question 4.

    M_xi(t) = sum_i V_i^xi c_i(t) with the *material* volumes, so geometry
    shrinkage is not mistaken for moisture loss:
        dM_xi/dt = -(2 pi hC / R(t)) [c_s(t) - C_a(t)].
    """
    n = grid.n_nodes
    tg = np.linspace(t_span[0], t_span[1], n_points)
    Y = traj(tg)
    M = Y[:, n:] @ grid.V
    cs = Y[:, n:][:, -1]
    R = np.atleast_1d(np.asarray(radius(tg), float))
    Ta, Ca = env(tg)
    flux = 2.0 * np.pi * hC / R * (cs - Ca)
    integral = np.trapz(flux, tg)
    resid = (M[-1] - M[0]) + integral
    scale = max(abs(M[0]), 1e-30)
    return {"M0": float(M[0]), "M_end": float(M[-1]), "flux_integral": float(integral),
            "absolute_residual": float(resid), "relative_residual": float(abs(resid) / scale)}
