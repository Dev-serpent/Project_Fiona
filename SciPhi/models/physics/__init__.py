"""Physics domain models for SciPhi.

Provides concrete implementations of :class:`ScientificModel` covering
classical and quantum physics:

* :class:`KinematicsModel` — 1D/2D projectile motion (algebraic)
* :class:`DynamicsModel` — Newton's second law, harmonic oscillator (ODE)
* :class:`ThermodynamicsModel` — ideal gas law, thermal processes (algebraic)
* :class:`ElectromagnetismModel` — Coulomb/Ohm laws, RC circuits (hybrid)
* :class:`QuantumModel` — particle in a box, quantum harmonic oscillator (PDE)
"""

from __future__ import annotations

from SciPhi.models.physics.dynamics import DynamicsModel
from SciPhi.models.physics.electromagnetism import ElectromagnetismModel
from SciPhi.models.physics.kinematics import KinematicsModel
from SciPhi.models.physics.quantum import QuantumModel
from SciPhi.models.physics.thermodynamics import ThermodynamicsModel

__all__ = [
    "DynamicsModel",
    "ElectromagnetismModel",
    "KinematicsModel",
    "QuantumModel",
    "ThermodynamicsModel",
]
