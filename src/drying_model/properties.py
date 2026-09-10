"""Effective material properties for the three question groups.

Appendix 2 -> Q1, appendix 3 -> Q2/Q3, appendix 4 -> Q4.

The temperature dependent diffusivity term exp(-3850 T) from the problem text is
implemented as an inverse absolute temperature Arrhenius term
exp(-3850 / T_K).  The literal (down-flowing) reading is available for magnitude
diagnostics only.
"""
from __future__ import annotations

import numpy as np


def temperature_term(temperature_C, mode="arrhenius_inverse_T"):
    tk = np.asarray(temperature_C, float) + 273.15
    if mode == "arrhenius_inverse_T":
        return np.exp(-3850.0 / tk)
    if mode == "strict_problem_text":
        return np.exp(-3850.0 * tk)
    raise ValueError("unknown diffusivity temperature mode %r" % mode)


class PropertiesQ1:
    name = "appendix2"
    rho_value = 820.0
    cp_value = 2600.0
    k_value = 0.36

    def rho(self, C):
        return np.full(np.shape(C), self.rho_value, float)

    def cp(self, C):
        return np.full(np.shape(C), self.cp_value, float)

    def k(self, C):
        return np.full(np.shape(C), self.k_value, float)

    def D(self, C, T_C):
        return 7.0e-9 * np.exp(-0.89 * np.asarray(C, float))


class PropertiesQ23:
    name = "appendix3"

    def __init__(self, temperature_mode="arrhenius_inverse_T"):
        self.temperature_mode = temperature_mode

    def rho(self, C):
        return 650.0 + 128.0 * np.asarray(C, float)

    def cp(self, C):
        C = np.asarray(C, float)
        return 1450.0 + 2736.0 * C / (C + 1.0)

    def k(self, C):
        C = np.asarray(C, float)
        return 0.21 + 0.38 * C / (C + 1.0)

    def D(self, C, T_C):
        return 2.4e-3 * np.exp(-0.45 * np.asarray(C, float)) * temperature_term(T_C, self.temperature_mode)


class PropertiesQ4:
    name = "appendix4"

    def __init__(self, temperature_mode="arrhenius_inverse_T"):
        self.temperature_mode = temperature_mode

    def rho(self, C):
        return 760.0 + 90.0 * np.asarray(C, float)

    def cp(self, C):
        C = np.asarray(C, float)
        return 1850.0 + 2150.0 * C / (C + 1.0)

    def k(self, C):
        C = np.asarray(C, float)
        return 0.12 + 0.20 * C / (C + 1.0)

    def D(self, C, T_C):
        return 4.2e-4 * np.exp(-0.30 * np.asarray(C, float)) * temperature_term(T_C, self.temperature_mode)
