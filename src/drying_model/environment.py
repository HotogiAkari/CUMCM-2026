"""Chamber environment T_a(t), C_a(t) built from attachment 1.

Piecewise linear interpolation over the measured window (0..14400 s); beyond the
window a configurable constant is used (default = mean of the last hour).
"""
from __future__ import annotations

import numpy as np


class Environment:
    def __init__(self, t, temperature_C, moisture, post_mode="tail_1h_mean", tail_window_s=3600.0):
        self.t = np.asarray(t, float)
        self.Ta = np.asarray(temperature_C, float)
        self.Ca = np.asarray(moisture, float)
        self.t_end = float(self.t[-1])
        self.post_mode = post_mode
        if post_mode == "tail_1h_mean":
            m = self.t >= self.t_end - float(tail_window_s)
            self.post = (float(self.Ta[m].mean()), float(self.Ca[m].mean()))
        elif post_mode == "constant_setpoint":
            self.post = (50.0, 0.05)
        elif post_mode == "last_value_hold":
            self.post = (float(self.Ta[-1]), float(self.Ca[-1]))
        else:
            raise ValueError("unknown post_mode %r" % post_mode)

    def __call__(self, t):
        scalar = np.ndim(t) == 0
        t = np.atleast_1d(np.asarray(t, float))
        tc = np.clip(t, self.t[0], self.t_end)
        ta = np.interp(tc, self.t, self.Ta)
        ca = np.interp(tc, self.t, self.Ca)
        late = t > self.t_end
        if late.any():
            ta = np.where(late, self.post[0], ta)
            ca = np.where(late, self.post[1], ca)
        if scalar:
            return float(ta[0]), float(ca[0])
        return ta, ca
