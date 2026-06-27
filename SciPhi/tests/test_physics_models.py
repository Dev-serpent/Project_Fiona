"""Tests for the physics domain models.

Verifies that each model:
1. Can be instantiated.
2. Declares the correct domain and mathematical form.
3. Has at least one equation, variable, and parameter.
4. Returns proper metadata via the ``info()`` convenience method.
5. Is discoverable through the model registry.
"""

from __future__ import annotations

import pytest

from SciPhi.interfaces.model import (
    MathematicalForm,
    ModelInfo,
    ScientificDomain,
    ScientificModel,
)
from SciPhi.models import get_default_model_registry
from SciPhi.models.physics import (
    DynamicsModel,
    ElectromagnetismModel,
    KinematicsModel,
    QuantumModel,
    ThermodynamicsModel,
)

# ---------------------------------------------------------------------------
# Individual model instances (one per test class)
# ---------------------------------------------------------------------------

KINEMATICS = KinematicsModel()
DYNAMICS = DynamicsModel()
THERMO = ThermodynamicsModel()
EM = ElectromagnetismModel()
QUANTUM = QuantumModel()

ALL_MODELS: list[ScientificModel] = [
    KINEMATICS,
    DYNAMICS,
    THERMO,
    EM,
    QUANTUM,
]

# Expected metadata for each model class.
# (class_name, domain, mathematical_form)
EXPECTED_META: dict[str, tuple[str, ScientificDomain, MathematicalForm]] = {
    "KinematicsModel": (
        "KinematicsModel",
        ScientificDomain.PHYSICS,
        MathematicalForm.ALGEBRAIC,
    ),
    "DynamicsModel": (
        "DynamicsModel",
        ScientificDomain.PHYSICS,
        MathematicalForm.ODE_INITIAL_VALUE,
    ),
    "ThermodynamicsModel": (
        "ThermodynamicsModel",
        ScientificDomain.PHYSICS,
        MathematicalForm.ALGEBRAIC,
    ),
    "ElectromagnetismModel": (
        "ElectromagnetismModel",
        ScientificDomain.PHYSICS,
        MathematicalForm.HYBRID,
    ),
    "QuantumModel": (
        "QuantumModel",
        ScientificDomain.PHYSICS,
        MathematicalForm.PDE,
    ),
}


# =========================================================================
# Test 1 — Instantiation
# =========================================================================


class TestInstantiation:
    """Each model can be instantiated without errors."""

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_can_instantiate(self, model: ScientificModel) -> None:
        """Instance creation succeeds."""
        assert isinstance(model, ScientificModel)


# =========================================================================
# Test 2 — Domain and MathematicalForm
# =========================================================================


class TestDomainAndForm:
    """Each model declares the correct domain and mathematical form."""

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_domain_is_physics(self, model: ScientificModel) -> None:
        assert model.domain is ScientificDomain.PHYSICS

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_mathematical_form_matches_expected(
        self, model: ScientificModel
    ) -> None:
        name = type(model).__name__
        _name, _domain, expected_form = EXPECTED_META[name]
        assert model.mathematical_form is expected_form, (
            f"{name}.mathematical_form is {model.mathematical_form}, "
            f"expected {expected_form}"
        )


# =========================================================================
# Test 3 — At least one equation, variable, parameter
# =========================================================================


class TestContent:
    """Each model defines at least one equation, variable, and parameter."""

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_has_equations(self, model: ScientificModel) -> None:
        assert len(model.equations) >= 1

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_has_variables(self, model: ScientificModel) -> None:
        assert len(model.variables) >= 1

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_has_parameters(self, model: ScientificModel) -> None:
        assert len(model.parameters) >= 1

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_has_assumptions(self, model: ScientificModel) -> None:
        assert len(model.assumptions) >= 1

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_has_constraints(self, model: ScientificModel) -> None:
        assert len(model.constraints) >= 1


# =========================================================================
# Test 4 — info() convenience method
# =========================================================================


class TestInfo:
    """Model metadata is correctly returned via info()."""

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_info_returns_model_info(self, model: ScientificModel) -> None:
        info = model.info()
        assert isinstance(info, ModelInfo)

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_info_id_matches_class_name(self, model: ScientificModel) -> None:
        info = model.info()
        assert info.id == type(model).__name__
        assert info.name == type(model).__name__

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_info_domain(self, model: ScientificModel) -> None:
        info = model.info()
        assert info.domain is ScientificDomain.PHYSICS

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_info_equation_count(self, model: ScientificModel) -> None:
        info = model.info()
        assert info.equation_count == len(model.equations)

    @pytest.mark.parametrize("model", ALL_MODELS, ids=type)
    def test_info_description_not_empty(self, model: ScientificModel) -> None:
        info = model.info()
        assert len(info.description) > 0


# =========================================================================
# Test 5 — Model registry
# =========================================================================


class TestRegistry:
    """The model registry discovers all physics models."""

    def test_registry_returns_dict(self) -> None:
        registry = get_default_model_registry()
        assert isinstance(registry, dict)

    def test_registry_contains_all_physics_models(self) -> None:
        registry = get_default_model_registry()
        expected_ids = {
            "KinematicsModel",
            "DynamicsModel",
            "ThermodynamicsModel",
            "ElectromagnetismModel",
            "QuantumModel",
        }
        assert expected_ids.issubset(registry.keys())

    def test_registry_models_are_scientific_model_instances(self) -> None:
        registry = get_default_model_registry()
        for model in registry.values():
            assert isinstance(model, ScientificModel)

    def test_registry_is_cached(self) -> None:
        r1 = get_default_model_registry()
        r2 = get_default_model_registry()
        assert r1 is r2  # same object (cached)

    def test_registry_entries_are_physics_domain(self) -> None:
        registry = get_default_model_registry()
        physics_ids = {
            "KinematicsModel",
            "DynamicsModel",
            "ThermodynamicsModel",
            "ElectromagnetismModel",
            "QuantumModel",
        }
        for model_id, model in registry.items():
            if model_id in physics_ids:
                assert model.domain is ScientificDomain.PHYSICS, (
                    f"{model_id} should be PHYSICS domain"
                )


# =========================================================================
# Test 6 — Specific model invariants
# =========================================================================


class TestKinematicsSpecific:
    """Model-specific assertions for KinematicsModel."""

    def test_gravity_parameter_default(self) -> None:
        g_param = next(
            p for p in KINEMATICS.parameters if p.name == "gravitational_acceleration"
        )
        assert g_param.default_value == 9.80665  # standard gravity

    def test_has_time_variable(self) -> None:
        symbols = {v.symbol for v in KINEMATICS.variables}
        assert "t" in symbols


class TestDynamicsSpecific:
    """Model-specific assertions for DynamicsModel."""

    def test_damping_ratio_default(self) -> None:
        zeta = next(
            p for p in DYNAMICS.parameters if p.name == "damping_ratio"
        )
        assert zeta.default_value == 0.1


class TestThermodynamicsSpecific:
    """Model-specific assertions for ThermodynamicsModel."""

    def test_uses_gas_constant(self) -> None:
        const_names = {c.name for c in THERMO.constants}
        assert "Molar gas constant" in const_names

    def test_ideal_gas_law_present(self) -> None:
        eq_names = {e.name for e in THERMO.equations}
        assert "ideal_gas_law" in eq_names


class TestElectromagnetismSpecific:
    """Model-specific assertions for ElectromagnetismModel."""

    def test_coulomb_constant_in_constants(self) -> None:
        const_names = {c.name for c in EM.constants}
        assert "Coulomb constant" in const_names

    def test_vacuum_permittivity_in_constants(self) -> None:
        const_names = {c.name for c in EM.constants}
        assert "Vacuum electric permittivity" in const_names


class TestQuantumSpecific:
    """Model-specific assertions for QuantumModel."""

    def test_uses_planck_constant(self) -> None:
        const_names = {c.name for c in QUANTUM.constants}
        assert "Planck constant" in const_names

    def test_uses_reduced_planck_constant(self) -> None:
        const_names = {c.name for c in QUANTUM.constants}
        assert "Reduced Planck constant" in const_names

    def test_energy_equation_present(self) -> None:
        eq_names = {e.name for e in QUANTUM.equations}
        assert "particle_in_a_box_energy" in eq_names


# =========================================================================
# Run as script
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__])
