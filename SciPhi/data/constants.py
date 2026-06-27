"""CODATA-based physical constants singleton.

Provides a single :class:`PhysicalConstants` registry that supplies common
physical constants as :class:`~SciPhi.interfaces.model.PhysicalConstant`
instances.  The values follow the 2018 CODATA recommended values where
applicable.
"""

from __future__ import annotations

from SciPhi.interfaces.model import PhysicalConstant


class PhysicalConstants:
    """Singleton-style registry of fundamental physical constants.

    All constants are exposed as a dictionary keyed by lowercase snake_case
    identifier (e.g. ``"speed_of_light"``) for convenient programmatic access.

    Usage::

        >>> c = PhysicalConstants.speed_of_light
        >>> c.value
        299792458.0
        >>> all_constants = PhysicalConstants.get_all()
    """

    # -- SI defining constants (exact) --------------------------------------

    speed_of_light: PhysicalConstant = PhysicalConstant(
        name="Speed of light in vacuum",
        symbol="c",
        value=299_792_458.0,
        unit="m s⁻¹",
        uncertainty=None,
    )

    planck_constant: PhysicalConstant = PhysicalConstant(
        name="Planck constant",
        symbol="h",
        value=6.626_070_15e-34,
        unit="J Hz⁻¹",
        uncertainty=None,
    )

    reduced_planck_constant: PhysicalConstant = PhysicalConstant(
        name="Reduced Planck constant",
        symbol="ħ",
        value=1.054_571_817e-34,
        unit="J s",
        uncertainty=None,
    )

    # -- Other fundamental constants ----------------------------------------

    gravitational_constant: PhysicalConstant = PhysicalConstant(
        name="Newtonian constant of gravitation",
        symbol="G",
        value=6.674_30e-11,
        unit="m³ kg⁻¹ s⁻²",
        uncertainty=1.5e-15,
    )

    elementary_charge: PhysicalConstant = PhysicalConstant(
        name="Elementary charge",
        symbol="e",
        value=1.602_176_634e-19,
        unit="C",
        uncertainty=None,
    )

    electron_mass: PhysicalConstant = PhysicalConstant(
        name="Electron mass",
        symbol="mₑ",
        value=9.109_383_7015e-31,
        unit="kg",
        uncertainty=2.8e-38,
    )

    proton_mass: PhysicalConstant = PhysicalConstant(
        name="Proton mass",
        symbol="mₚ",
        value=1.672_621_923_69e-27,
        unit="kg",
        uncertainty=5.1e-35,
    )

    neutron_mass: PhysicalConstant = PhysicalConstant(
        name="Neutron mass",
        symbol="mₙ",
        value=1.674_927_498_04e-27,
        unit="kg",
        uncertainty=5.1e-35,
    )

    boltzmann_constant: PhysicalConstant = PhysicalConstant(
        name="Boltzmann constant",
        symbol="k_B",
        value=1.380_649e-23,
        unit="J K⁻¹",
        uncertainty=None,
    )

    avogadro_number: PhysicalConstant = PhysicalConstant(
        name="Avogadro number",
        symbol="N_A",
        value=6.022_140_76e23,
        unit="mol⁻¹",
        uncertainty=None,
    )

    gas_constant: PhysicalConstant = PhysicalConstant(
        name="Molar gas constant",
        symbol="R",
        value=8.314_462_618,
        unit="J mol⁻¹ K⁻¹",
        uncertainty=None,
    )

    vacuum_permittivity: PhysicalConstant = PhysicalConstant(
        name="Vacuum electric permittivity",
        symbol="ε₀",
        value=8.854_187_8128e-12,
        unit="F m⁻¹",
        uncertainty=1.6e-21,
    )

    vacuum_permeability: PhysicalConstant = PhysicalConstant(
        name="Vacuum magnetic permeability",
        symbol="μ₀",
        value=1.256_637_061_27e-06,
        unit="N A⁻²",
        uncertainty=None,
    )

    fine_structure_constant: PhysicalConstant = PhysicalConstant(
        name="Fine-structure constant",
        symbol="α",
        value=7.297_352_5693e-3,
        unit="1",
        uncertainty=1.6e-12,
    )

    stefan_boltzmann_constant: PhysicalConstant = PhysicalConstant(
        name="Stefan–Boltzmann constant",
        symbol="σ",
        value=5.670_374_419e-8,
        unit="W m⁻² K⁻⁴",
        uncertainty=None,
    )

    standard_gravity: PhysicalConstant = PhysicalConstant(
        name="Standard acceleration of gravity",
        symbol="g₀",
        value=9.806_65,
        unit="m s⁻²",
        uncertainty=None,
    )

    atmospheric_pressure: PhysicalConstant = PhysicalConstant(
        name="Standard atmosphere",
        symbol="atm",
        value=101_325.0,
        unit="Pa",
        uncertainty=None,
    )

    # -- Registry -----------------------------------------------------------

    _REGISTRY: dict[str, PhysicalConstant] | None = None

    @classmethod
    def get_all(cls) -> dict[str, PhysicalConstant]:
        """Return a dictionary of every constant defined on this class.

        Returns:
            Mapping of snake-case constant names to their
            :class:`~SciPhi.interfaces.model.PhysicalConstant` instances.
        """
        if cls._REGISTRY is not None:
            return cls._REGISTRY

        registry: dict[str, PhysicalConstant] = {}
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, PhysicalConstant):
                registry[attr_name] = attr
        cls._REGISTRY = registry
        return registry

    @classmethod
    def get(cls, name: str) -> PhysicalConstant:
        """Look up a single constant by its snake-case identifier.

        Args:
            name: Lowercase snake-case name, e.g. ``"planck_constant"``.

        Returns:
            The matching :class:`~SciPhi.interfaces.model.PhysicalConstant`.

        Raises:
            KeyError: If the constant name is not found.
        """
        constants = cls.get_all()
        if name not in constants:
            raise KeyError(
                f"Unknown physical constant {name!r}. "
                f"Available constants: {sorted(constants)}"
            )
        return constants[name]
