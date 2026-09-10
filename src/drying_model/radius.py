"""Material radius R(t) for question 4 (attachment 2)."""
from __future__ import annotations

import numpy as np
from scipy.interpolate import PchipInterpolator


class RadiusFunction:
    def __init__(self, t, r_m, interp="pchip", post="last_value_hold"):
        self.t = np.asarray(t, float)
        self.R = np.asarray(r_m, float)
        self.t_end = float(self.t[-1])
        self.r_last = float(self.R[-1])
        self.interp = interp
        self.post = post
        if interp == "pchip":
            self._f = PchipInterpolator(self.t, self.R, extrapolate=False)
        elif interp == "linear":
            self._f = None
        else:
            raise ValueError("unknown radius interpolation %r" % interp)

    def __call__(self, t):
        scalar = np.ndim(t) == 0
        t = np.atleast_1d(np.asarray(t, float))
        tc = np.clip(t, self.t[0], self.t_end)
        if self._f is None:
            v = np.interp(tc, self.t, self.R)
        else:
            v = self._f(tc)
        if self.post == "last_value_hold":
            v = np.where(t > self.t_end, self.r_last, v)
        if scalar:
            return float(v[0])
        return v

    @property
    def initial_radius(self):
        return float(self.R[0])
