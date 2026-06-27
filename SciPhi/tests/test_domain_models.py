"""Tests for all non-physics domain models.

Verifies that every model in the chemistry, biology, earth science,
and engineering domains:

1. Can be instantiated.
2. Declares the correct domain and mathematical form.
3. Has at least one equation, variable, and parameter.
4. Returns proper metadata via the ``info()`` convenience method.
5. Is discoverable through the model registry.
6. Satisfies model-specific invariants.
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

# ---------------------------------------------------------------------------
# Individual model instances (one per test class)
# ---------------------------------------------------------------------------

KINETICS = ChemicalReactionKineticsModel()
EQUILIBRIUM = ChemicalEquilibriumModel()
STOICHIOMETRY = StoichiometryModel()
LOGISTIC = LogisticGrowthModel()
SIR = SIRModel()
CLIMATE = EnergyBalanceModel()
STRUCTURAL = StructuralModel()
CIRCUIT = CircuitModel()

ALL_NEW_MODELS: list[ScientificModel] = [
    KINETICS,
    EQUILIBRIUM,
    STOICHIOMETRY,
    LOGISTIC,
    SIR,
    CLIMATE,
    STRUCTURAL,
    CIRCUIT,
]

# Expected metadata for each model class.
# (class_name, domain, mathematical_form)
EXPECTED_META: dict[str, tuple[str, ScientificDomain, MathematicalForm]] = {
    "ChemicalReactionKineticsModel": (
        "ChemicalReactionKineticsModel",
        ScientificDomain.CHEMISTRY,
        MathematicalForm.ODE_INITIAL_VALUE,
    ),
    "ChemicalEquilibriumModel": (
        "ChemicalEquilibriumModel",
        ScientificDomain.CHEMISTRY,
        MathematicalForm.ALGEBRAIC,
    ),
    "StoichiometryModel": (
        "StoichiometryModel",
        ScientificDomain.CHEMISTRY,
        MathematicalForm.ALGEBRAIC,
    ),
    "LogisticGrowthModel": (
        "LogisticGrowthModel",
        ScientificDomain.BIOLOGY,
        MathematicalForm.ODE_INITIAL_VALUE,
    ),
    "SIRModel": (
        "SIRModel",
        ScientificDomain.BIOLOGY,
        MathematicalForm.ODE_INITIAL_VALUE,
    ),
    "EnergyBalanceModel": (
        "EnergyBalanceModel",
        ScientificDomain.EARTH_SCIENCE,
        MathematicalForm.HYBRID,
    ),
    "StructuralModel": (
        "StructuralModel",
        ScientificDomain.ENGINEERING,
        MathematicalForm.ALGEBRAIC,
    ),
    "CircuitModel": (
        "CircuitModel",
        ScientificDomain.ENGINEERING,
        MathematicalForm.HYBRID,
    ),
}


# =========================================================================
# Test 1 — Instantiation
# =========================================================================


class TestInstantiation:
    """Each new model can be instantiated without errors."""

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_can_instantiate(self, model: ScientificModel) -> None:
        """Instance creation succeeds."""
        assert isinstance(model, ScientificModel)


# =========================================================================
# Test 2 — Domain and MathematicalForm
# =========================================================================


class TestDomainAndForm:
    """Each model declares the correct domain and mathematical form."""

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_domain_correct(self, model: ScientificModel) -> None:
        name = type(model).__name__
        _name, expected_domain, _form = EXPECTED_META[name]
        assert model.domain is expected_domain, (
            f"{name}.domain is {model.domain}, expected {expected_domain}"
        )

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
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

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_has_equations(self, model: ScientificModel) -> None:
        assert len(model.equations) >= 1

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_has_variables(self, model: ScientificModel) -> None:
        assert len(model.variables) >= 1

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_has_parameters(self, model: ScientificModel) -> None:
        assert len(model.parameters) >= 1

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_has_assumptions(self, model: ScientificModel) -> None:
        assert len(model.assumptions) >= 1

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_has_constraints(self, model: ScientificModel) -> None:
        assert len(model.constraints) >= 1


# =========================================================================
# Test 4 — info() convenience method
# =========================================================================


class TestInfo:
    """Model metadata is correctly returned via info()."""

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_info_returns_model_info(self, model: ScientificModel) -> None:
        info = model.info()
        assert isinstance(info, ModelInfo)

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_info_id_matches_class_name(self, model: ScientificModel) -> None:
        info = model.info()
        assert info.id == type(model).__name__
        assert info.name == type(model).__name__

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_info_domain(self, model: ScientificModel) -> None:
        info = model.info()
        name = type(model).__name__
        _name, expected_domain, _form = EXPECTED_META[name]
        assert info.domain is expected_domain

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_info_equation_count(self, model: ScientificModel) -> None:
        info = model.info()
        assert info.equation_count == len(model.equations)

    @pytest.mark.parametrize("model", ALL_NEW_MODELS, ids=type)
    def test_info_description_not_empty(self, model: ScientificModel) -> None:
        info = model.info()
        assert len(info.description) > 0


# =========================================================================
# Test 5 — Model registry
# =========================================================================


class TestRegistry:
    """The model registry discovers all new models alongside physics."""

    def test_registry_returns_dict(self) -> None:
        registry = get_default_model_registry()
        assert isinstance(registry, dict)

    def test_registry_contains_all_new_models(self) -> None:
        registry = get_default_model_registry()
        expected_new_ids = {
            "ChemicalReactionKineticsModel",
            "ChemicalEquilibriumModel",
            "StoichiometryModel",
            "LogisticGrowthModel",
            "SIRModel",
            "EnergyBalanceModel",
            "StructuralModel",
            "CircuitModel",
        }
        assert expected_new_ids.issubset(registry.keys())

    def test_registry_still_contains_physics_models(self) -> None:
        registry = get_default_model_registry()
        expected_physics_ids = {
            "KinematicsModel",
            "DynamicsModel",
            "ThermodynamicsModel",
            "ElectromagnetismModel",
            "QuantumModel",
        }
        assert expected_physics_ids.issubset(registry.keys())

    def test_registry_total_count(self) -> None:
        registry = get_default_model_registry()
        # 5 physics + 3 chemistry + 2 biology + 1 earth + 2 engineering = 13
        assert len(registry) == 13

    def test_registry_models_are_scientific_model_instances(self) -> None:
        registry = get_default_model_registry()
        for model in registry.values():
            assert isinstance(model, ScientificModel)

    def test_registry_is_cached(self) -> None:
        r1 = get_default_model_registry()
        r2 = get_default_model_registry()
        assert r1 is r2  # same object (cached)

    def test_registry_new_models_have_correct_domains(self) -> None:
        registry = get_default_model_registry()
        domain_checks = {
            "ChemicalReactionKineticsModel": ScientificDomain.CHEMISTRY,
            "ChemicalEquilibriumModel": ScientificDomain.CHEMISTRY,
            "StoichiometryModel": ScientificDomain.CHEMISTRY,
            "LogisticGrowthModel": ScientificDomain.BIOLOGY,
            "SIRModel": ScientificDomain.BIOLOGY,
            "EnergyBalanceModel": ScientificDomain.EARTH_SCIENCE,
            "StructuralModel": ScientificDomain.ENGINEERING,
            "CircuitModel": ScientificDomain.ENGINEERING,
        }
        for model_id, expected_domain in domain_checks.items():
            assert registry[model_id].domain is expected_domain, (
                f"{model_id} has domain {registry[model_id].domain}, "
                f"expected {expected_domain}"
            )


# =========================================================================
# Test 6 — Model-specific invariants: Chemistry
# =========================================================================


class TestReactionKineticsSpecific:
    """Model-specific assertions for ChemicalReactionKineticsModel."""

    def test_uses_gas_constant(self) -> None:
        const_names = {c.name for c in KINETICS.constants}
        assert "Molar gas constant" in const_names

    def test_arrhenius_equation_present(self) -> None:
        eq_names = {e.name for e in KINETICS.equations}
        assert "arrhenius" in eq_names

    def test_concentration_variables(self) -> None:
        symbols = {v.symbol for v in KINETICS.variables}
        assert "[A]" in symbols
        assert "[B]" in symbols

    def test_reaction_order_parameters(self) -> None:
        param_names = {p.name for p in KINETICS.parameters}
        assert "reaction_order_m" in param_names
        assert "reaction_order_n" in param_names

    def test_is_ode_form(self) -> None:
        assert KINETICS.mathematical_form is MathematicalForm.ODE_INITIAL_VALUE


class TestEquilibriumSpecific:
    """Model-specific assertions for ChemicalEquilibriumModel."""

    def test_uses_gas_constant(self) -> None:
        const_names = {c.name for c in EQUILIBRIUM.constants}
        assert "Molar gas constant" in const_names

    def test_gibbs_equation_present(self) -> None:
        eq_names = {e.name for e in EQUILIBRIUM.equations}
        assert "gibbs_free_energy" in eq_names

    def test_vant_hoff_present(self) -> None:
        eq_names = {e.name for e in EQUILIBRIUM.equations}
        assert "vant_hoff" in eq_names

    def test_equilibrium_constant_variable(self) -> None:
        symbols = {v.symbol for v in EQUILIBRIUM.variables}
        assert "K_eq" in symbols

    def test_is_algebraic(self) -> None:
        assert EQUILIBRIUM.mathematical_form is MathematicalForm.ALGEBRAIC


class TestStoichiometrySpecific:
    """Model-specific assertions for StoichiometryModel."""

    def test_mole_ratio_equation_present(self) -> None:
        eq_names = {e.name for e in STOICHIOMETRY.equations}
        assert "mole_ratio" in eq_names

    def test_mass_mole_conversion_present(self) -> None:
        eq_names = {e.name for e in STOICHIOMETRY.equations}
        assert "mass_mole_conversion" in eq_names

    def test_limiting_reagent_present(self) -> None:
        eq_names = {e.name for e in STOICHIOMETRY.equations}
        assert "limiting_reagent" in eq_names

    def test_percent_yield_present(self) -> None:
        eq_names = {e.name for e in STOICHIOMETRY.equations}
        assert "percent_yield" in eq_names

    def test_has_amount_variables(self) -> None:
        symbols = {v.symbol for v in STOICHIOMETRY.variables}
        assert "n_A" in symbols
        assert "n_B" in symbols

    def test_no_physical_constants(self) -> None:
        assert len(STOICHIOMETRY.constants) == 0

    def test_is_algebraic(self) -> None:
        assert STOICHIOMETRY.mathematical_form is MathematicalForm.ALGEBRAIC


# =========================================================================
# Test 7 — Model-specific invariants: Biology
# =========================================================================


class TestLogisticGrowthSpecific:
    """Model-specific assertions for LogisticGrowthModel."""

    def test_carrying_capacity_parameter(self) -> None:
        param_names = {p.name for p in LOGISTIC.parameters}
        assert "carrying_capacity" in param_names

    def test_growth_rate_parameter(self) -> None:
        param_names = {p.name for p in LOGISTIC.parameters}
        assert "growth_rate" in param_names

    def test_logistic_equation_present(self) -> None:
        eq_names = {e.name for e in LOGISTIC.equations}
        assert "logistic_growth" in eq_names

    def test_closed_form_solution_present(self) -> None:
        eq_names = {e.name for e in LOGISTIC.equations}
        assert "carrying_capacity_solution" in eq_names

    def test_exponential_approximation_present(self) -> None:
        eq_names = {e.name for e in LOGISTIC.equations}
        assert "exponential_growth" in eq_names

    def test_no_physical_constants(self) -> None:
        assert len(LOGISTIC.constants) == 0

    def test_is_ode_form(self) -> None:
        assert LOGISTIC.mathematical_form is MathematicalForm.ODE_INITIAL_VALUE


class TestSIRSpecific:
    """Model-specific assertions for SIRModel."""

    def test_has_three_odes(self) -> None:
        """SIR model has exactly 3 ODE equations plus R0."""
        ode_names = {"susceptible_rate", "infected_rate", "recovered_rate"}
        eq_names = {e.name for e in SIR.equations}
        assert ode_names.issubset(eq_names)

    def test_basic_reproduction_number(self) -> None:
        eq_names = {e.name for e in SIR.equations}
        assert "basic_reproduction_number" in eq_names

    def test_has_sir_variables(self) -> None:
        symbols = {v.symbol for v in SIR.variables}
        assert "S" in symbols
        assert "I" in symbols
        assert "R" in symbols

    def test_transmission_rate_parameter(self) -> None:
        param_names = {p.name for p in SIR.parameters}
        assert "transmission_rate" in param_names

    def test_recovery_rate_parameter(self) -> None:
        param_names = {p.name for p in SIR.parameters}
        assert "recovery_rate" in param_names

    def test_total_population_parameter(self) -> None:
        param_names = {p.name for p in SIR.parameters}
        assert "total_population" in param_names

    def test_no_physical_constants(self) -> None:
        assert len(SIR.constants) == 0

    def test_is_ode_form(self) -> None:
        assert SIR.mathematical_form is MathematicalForm.ODE_INITIAL_VALUE


# =========================================================================
# Test 8 — Model-specific invariants: Earth Science
# =========================================================================


class TestEnergyBalanceSpecific:
    """Model-specific assertions for EnergyBalanceModel."""

    def test_uses_stefan_boltzmann(self) -> None:
        const_names = {c.name for c in CLIMATE.constants}
        assert "Stefan–Boltzmann constant" in const_names

    def test_energy_balance_equation_present(self) -> None:
        eq_names = {e.name for e in CLIMATE.equations}
        assert "energy_balance" in eq_names

    def test_albedo_feedback_present(self) -> None:
        eq_names = {e.name for e in CLIMATE.equations}
        assert "albedo_feedback" in eq_names

    def test_solar_constant_parameter(self) -> None:
        param_names = {p.name for p in CLIMATE.parameters}
        assert "solar_constant" in param_names

    def test_emissivity_parameter(self) -> None:
        param_names = {p.name for p in CLIMATE.parameters}
        assert "emissivity" in param_names

    def test_is_hybrid_form(self) -> None:
        assert CLIMATE.mathematical_form is MathematicalForm.HYBRID


# =========================================================================
# Test 9 — Model-specific invariants: Engineering
# =========================================================================


class TestStructuralSpecific:
    """Model-specific assertions for StructuralModel."""

    def test_hookes_law_present(self) -> None:
        eq_names = {e.name for e in STRUCTURAL.equations}
        assert "hookes_law" in eq_names

    def test_euler_buckling_present(self) -> None:
        eq_names = {e.name for e in STRUCTURAL.equations}
        assert "euler_buckling" in eq_names

    def test_cantilever_deflection_present(self) -> None:
        eq_names = {e.name for e in STRUCTURAL.equations}
        assert "cantilever_deflection" in eq_names

    def test_youngs_modulus_parameter(self) -> None:
        param_names = {p.name for p in STRUCTURAL.parameters}
        assert "youngs_modulus" in param_names

    def test_has_stress_variable(self) -> None:
        symbols = {v.symbol for v in STRUCTURAL.variables}
        assert "σ" in symbols or "sigma" in symbols

    def test_no_physical_constants(self) -> None:
        assert len(STRUCTURAL.constants) == 0

    def test_is_algebraic(self) -> None:
        assert STRUCTURAL.mathematical_form is MathematicalForm.ALGEBRAIC


class TestCircuitSpecific:
    """Model-specific assertions for CircuitModel."""

    def test_ohms_law_present(self) -> None:
        eq_names = {e.name for e in CIRCUIT.equations}
        assert "ohms_law" in eq_names

    def test_kirchhoff_laws_present(self) -> None:
        eq_names = {e.name for e in CIRCUIT.equations}
        assert "kirchhoff_voltage_law" in eq_names
        assert "kirchhoff_current_law" in eq_names

    def test_rc_charging_present(self) -> None:
        eq_names = {e.name for e in CIRCUIT.equations}
        assert "rc_charging" in eq_names

    def test_rl_charging_present(self) -> None:
        eq_names = {e.name for e in CIRCUIT.equations}
        assert "rl_charging" in eq_names

    def test_has_five_equations(self) -> None:
        assert len(CIRCUIT.equations) == 5

    def test_resistance_parameter(self) -> None:
        param_names = {p.name for p in CIRCUIT.parameters}
        assert "resistance" in param_names
        assert "capacitance" in param_names
        assert "inductance" in param_names

    def test_no_physical_constants(self) -> None:
        assert len(CIRCUIT.constants) == 0

    def test_is_hybrid_form(self) -> None:
        assert CIRCUIT.mathematical_form is MathematicalForm.HYBRID


# =========================================================================
# Run as script
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__])
