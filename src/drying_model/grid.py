"""Conservative annular control volumes on the physical and material domains."""
from __future__ import annotations

import numpy as np


def _faces_from_nodes(nodes, last_face):
    faces = np.empty(nodes.size + 1)
    faces[1:-1] = 0.5 * (nodes[:-1] + nodes[1:])
    faces[0] = 0.0
    faces[-1] = last_face
    return faces


class FixedGrid:
    """Physical radial grid r in [0, R0] with N cells."""

    def __init__(self, R0: float, N: int):
        self.R0 = float(R0)
        self.N = int(N)
        self.dr = self.R0 / self.N
        self.r = np.arange(self.N + 1) * self.dr
        faces = _faces_from_nodes(self.r, self.R0)
        self.faces = faces
        self.V = np.pi * (faces[1:] ** 2 - faces[:-1] ** 2)
        A = 2.0 * np.pi * faces
        self.AL = A[:-1]  # A_{i-1/2}
        self.AR = A[1:]   # A_{i+1/2}

    @property
    def n_nodes(self):
        return self.N + 1


class MaterialGrid:
    """Material (Lagrangian) grid xi in [0, 1] with N cells."""

    def __init__(self, N: int):
        self.N = int(N)
        self.dxi = 1.0 / self.N
        self.xi = np.arange(self.N + 1) * self.dxi
        faces = _faces_from_nodes(self.xi, 1.0)
        self.faces = faces
        self.V = np.pi * (faces[1:] ** 2 - faces[:-1] ** 2)
        A = 2.0 * np.pi * faces
        self.AL = A[:-1]
        self.AR = A[1:]

    @property
    def n_nodes(self):
        return self.N + 1
