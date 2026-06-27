"""SciPhi model registry.

This package contains all domain-specific scientific model implementations.
Sub-packages group models by scientific domain:

* :mod:`SciPhi.models.physics` — Physics models
* :mod:`SciPhi.models.chemistry` — Chemistry models
* :mod:`SciPhi.models.biology` — Biology models
* :mod:`SciPhi.models.earth` — Earth science models
* :mod:`SciPhi.models.engineering` — Engineering models
* :mod:`SciPhi.models.math` — Mathematical models *(planned)*
"""

from __future__ import annotations

from SciPhi.interfaces.model import ScientificModel

# ---------------------------------------------------------------------------
# Lazy-load helpers
# ---------------------------------------------------------------------------

_registry: dict[str, ScientificModel] | None = None


def get_default_model_registry() -> dict[str, ScientificModel]:
    """Return a dictionary mapping model id → model instance for all
    registered models.

    The registry is built once and cached.  Each call returns the same
    (singleton) instances so that downstream code can rely on referential
    identity across lookups.

    Currently registered domains:

    * **physics** — 5 models (kinematics, dynamics, thermodynamics,
      electromagnetism, quantum mechanics)
    * **chemistry** — 3 models (reaction kinetics, equilibrium,
      stoichiometry)
    * **biology** — 2 models (logistic growth, SIR epidemiology)
    * **earth** — 1 model (energy balance climate)
    * **engineering** — 2 models (structures, circuits)

    Returns:
        A ``dict[str, ScientificModel]`` keyed by the class name of each
        model (e.g. ``"KinematicsModel"``).
    """
    global _registry  # noqa: PLW0603
    if _registry is not None:
        return _registry

    # Import domain packages here to avoid circular imports at the package
    # level and to keep start-up time reasonable.
    from SciPhi.models.physics import (
        DynamicsModel,
        ElectromagnetismModel,
        KinematicsModel,
        QuantumModel,
        ThermodynamicsModel,
    )
    from SciPhi.models.chemistry import (
        ChemicalEquilibriumModel,
        ChemicalReactionKineticsModel,
        StoichiometryModel,
    )
    from SciPhi.models.biology import (
        LogisticGrowthModel,
        SIRModel,
    )
    from SciPhi.models.earth import (
        EnergyBalanceModel,
    )
    from SciPhi.models.engineering import (
        CircuitModel,
        StructuralModel,
    )

    models: list[ScientificModel] = [
        # Physics
        KinematicsModel(),
        DynamicsModel(),
        ThermodynamicsModel(),
        ElectromagnetismModel(),
        QuantumModel(),
        # Chemistry
        ChemicalReactionKineticsModel(),
        ChemicalEquilibriumModel(),
        StoichiometryModel(),
        # Biology
        LogisticGrowthModel(),
        SIRModel(),
        # Earth
        EnergyBalanceModel(),
        # Engineering
        CircuitModel(),
        StructuralModel(),
    ]

    _registry = {type(m).__name__: m for m in models}
    return _registry
