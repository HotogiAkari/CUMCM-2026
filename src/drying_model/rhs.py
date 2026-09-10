"""Semi-discrete right-hand sides (method of lines) for the drying model.

State layout: y = [T_0..T_N, C_0..C_N] for the fixed domain and
              y = [theta_0..theta_N, c_0..c_N] for the material domain.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp


def harmonic_mean(a):
    """Harmonic mean of neighbouring entries (length len(a)-1)."""
    a = np.asarray(a, float)
    denom = a[1:] + a[:-1]
    out = np.zeros_like(denom)
    nz = denom != 0.0
    out[nz] = 2.0 * a[1:][nz] * a[:-1][nz] / denom[nz]
    return out


def _jac_sparsity(n: int):
    """Block tridiagonal boolean pattern for [T, C] blocks with local coupling."""
    rows, cols = [], []
    for i in range(n):
        for d in (-1, 0, 1):
            j = i + d
            if 0 <= j < n:
                rows.append(i); cols.append(j)          # J_TT
                rows.append(i); cols.append(n + j)      # J_TC (via rho, cp, k)
                rows.append(n + i); cols.append(j)      # J_CT (via D)
                rows.append(n + i); cols.append(n + j)  # J_CC
    data = np.ones(len(rows), dtype=bool)
    return sp.csr_matrix((data, (rows, cols)), shape=(2 * n, 2 * n))


def make_fixed_rhs(props, grid, env, hT=25.0, hC=8.0e-7):
    n = grid.n_nodes
    dr = grid.dr
    V = grid.V
    AL = grid.AL
    AR = grid.AR

    def fun(t, y):
        T = y[:n]
        C = y[n:]
        Ta, Ca = env(t)
        rho = props.rho(C)
        cp = props.cp(C)
        k = props.k(C)
        D = props.D(C, T)

        kh = harmonic_mean(k)
        Dh = harmonic_mean(D)

        qT = np.empty(n + 1)
        qC = np.empty(n + 1)
        qT[0] = 0.0
        qC[0] = 0.0
        qT[1:n] = -kh * (T[1:] - T[:-1]) / dr
        qC[1:n] = -Dh * (C[1:] - C[:-1]) / dr
        qT[n] = hT * (T[-1] - Ta)
        qC[n] = hC * (C[-1] - Ca)

        divT = AL * qT[:-1] - AR * qT[1:]
        divC = AL * qC[:-1] - AR * qC[1:]

        dTdt = divT / (rho * cp * V)
        dCdt = divC / V
        return np.concatenate((dTdt, dCdt))

    return fun, _jac_sparsity(n)


def make_shrink_rhs(props, grid, radius, env, hT=25.0, hC=8.0e-7):
    n = grid.n_nodes
    dxi = grid.dxi
    V = grid.V
    AL = grid.AL
    AR = grid.AR

    def fun(t, y):
        R = radius(t)
        theta = y[:n]
        c = y[n:]
        Ta, Ca = env(t)
        rho = props.rho(c)
        cp = props.cp(c)
        k = props.k(c)
        D = props.D(c, theta)

        kh = harmonic_mean(k)
        Dh = harmonic_mean(D)

        qT = np.empty(n + 1)
        qC = np.empty(n + 1)
        qT[0] = 0.0
        qC[0] = 0.0
        qT[1:n] = -kh * (theta[1:] - theta[:-1]) / dxi
        qC[1:n] = -Dh * (c[1:] - c[:-1]) / dxi
        qT[n] = R * hT * (theta[-1] - Ta)
        qC[n] = R * hC * (c[-1] - Ca)

        divT = AL * qT[:-1] - AR * qT[1:]
        divC = AL * qC[:-1] - AR * qC[1:]

        dTdt = divT / (R * R * rho * cp * V)
        dCdt = divC / (R * R * V)
        return np.concatenate((dTdt, dCdt))

    return fun, _jac_sparsity(n)


def make_drying_event(n: int, threshold: float = 0.15):
    def event(t, y):
        return float(np.max(y[n:]) - threshold)

    event.terminal = True
    event.direction = -1.0
    return event
