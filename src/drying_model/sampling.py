"""Sampling of the solution onto the required time/space output grids."""
from __future__ import annotations

import numpy as np


def sample_fixed(traj, grid, times, positions_m):
    times = np.atleast_1d(np.asarray(times, float))
    positions_m = np.asarray(positions_m, float)
    Y = traj(times)
    n = grid.n_nodes
    T = np.full((times.size, positions_m.size), np.nan)
    C = np.full((times.size, positions_m.size), np.nan)
    for i in range(times.size):
        y = Y[i]
        T[i] = np.interp(positions_m, grid.r, y[:n])
        C[i] = np.interp(positions_m, grid.r, y[n:])
    return T, C


def sample_shrink(traj, grid, radius, times, positions_m):
    """Physical positions in a shrinking domain.

    A physical position r_k is sampled only while r_k <= R(t); outside the
    material the value is NaN (left blank in the spreadsheet).  The moving
    surface is always returned as a separate column.
    """
    times = np.atleast_1d(np.asarray(times, float))
    positions_m = np.asarray(positions_m, float)
    Y = traj(times)
    R = np.asarray(radius(times), float)
    R = np.atleast_1d(R)
    n = grid.n_nodes
    xi = grid.xi
    T = np.full((times.size, positions_m.size), np.nan)
    C = np.full((times.size, positions_m.size), np.nan)
    surf_T = np.full(times.size, np.nan)
    surf_C = np.full(times.size, np.nan)
    for i in range(times.size):
        r_t = R[i]
        y = Y[i]
        mask = positions_m <= r_t + 1e-12
        if mask.any():
            xk = np.clip(positions_m[mask] / r_t, 0.0, 1.0)
            T[i, mask] = np.interp(xk, xi, y[:n])
            C[i, mask] = np.interp(xk, xi, y[n:])
        surf_T[i] = y[:n][-1]
        surf_C[i] = y[n:][-1]
    return T, C, surf_T, surf_C
