"""Time integration: multi-leg BDF solves with dense output and events."""
from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq


def make_atol(n: int, atol_temperature: float, atol_moisture: float):
    return np.concatenate((np.full(n, atol_temperature), np.full(n, atol_moisture)))


class Trajectory:
    """Holds the dense interpolants of successive integration legs."""

    def __init__(self, n_state: int):
        self.n_state = int(n_state)
        self.legs = []

    def add(self, t0, t1, sol):
        self.legs.append((float(t0), float(t1), sol))

    def __call__(self, t):
        t = np.atleast_1d(np.asarray(t, float))
        out = np.full((t.size, self.n_state), np.nan)
        remaining = np.ones(t.size, dtype=bool)
        for (t0, t1, sol) in self.legs:
            m = remaining & (t >= t0 - 1e-9) & (t <= t1 + 1e-9)
            if m.any():
                out[m] = np.asarray(sol.sol(t[m])).T
                remaining &= ~m
        return out


def run_legs(fun, y0, legs, atol, rtol, jac_sparsity, event=None, dense=True):
    """Integrate y0 over the ordered legs [(t0, t1, max_step), ...].

    Returns (trajectory, y_final, t_final, event_info).
    """
    traj = Trajectory(len(y0))
    y = np.asarray(y0, float)
    t = float(legs[0][0])
    event_info = None

    for (t0, t1, max_step) in legs:
        t0 = max(float(t0), t)
        if t1 <= t0 + 1e-12:
            continue
        sol = solve_ivp(
            fun, (t0, float(t1)), y, method="BDF", rtol=rtol, atol=atol,
            jac_sparsity=jac_sparsity, dense_output=dense,
            max_step=float(max_step), events=event,
        )
        if not sol.success:
            raise RuntimeError("solve_ivp failed on leg [%g, %g]: %s" % (t0, t1, sol.message))
        traj.add(t0, float(sol.t[-1]), sol)
        y = sol.y[:, -1].copy()
        t = float(sol.t[-1])
        if event is not None and sol.t_events is not None and len(sol.t_events[0]) > 0:
            te = float(sol.t_events[0][0])
            ye = np.asarray(sol.y_events[0][0], float)
            event_info = {"t": te, "y": ye, "leg": [t0, float(t1)]}
            break

    return traj, y, t, event_info


def refine_event(traj, n: int, threshold: float, t_event: float, window: float = 120.0):
    """Brent refinement of the first crossing of max(C) - threshold.

    A genuine sign-change bracket [t_lo, t_hi] with g(t_lo) > 0 > g(t_hi) is
    located on the (previously extended) dense trajectory, then brentq is run.
    Returns a dict with the solver event time, the refined root and the bracket
    values; ``brent_executed`` reports whether brentq actually ran.
    """
    def g(t):
        y = traj(np.array([t]))[0]
        return float(np.max(y[n:]) - threshold)

    t_lo = max(0.0, t_event - window)
    t_hi = t_event + window
    g_lo, g_hi = g(t_lo), g(t_hi)
    for _ in range(8):
        if g_lo > 0.0 and g_hi < 0.0:
            break
        t_lo = max(0.0, t_lo - window)
        g_lo = g(t_lo)
        if t_lo == 0.0:
            break
    if g_lo > 0.0 and g_hi < 0.0:
        root = brentq(g, t_lo, t_hi, xtol=1e-12, rtol=8.9e-16, maxiter=200)
        return {"t_event": float(t_event), "t_refined": float(root),
                "g_left": float(g_lo), "g_right": float(g_hi), "brent_executed": True}
    return {"t_event": float(t_event), "t_refined": float(t_event),
            "g_left": float(g_lo), "g_right": float(g_hi), "brent_executed": False}
