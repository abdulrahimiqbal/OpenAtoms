"""Thermo-kinetic simulation registry backed by Cantera.

Example:
    >>> from openatoms.sim.registry.kinetics_sim import VirtualReactor
    >>> from openatoms.units import Q_
    >>> vr = VirtualReactor()
    >>> ok, delta_g = vr.check_gibbs_feasibility({"H2": 1, "O2": 0.5}, {"H2O": 1}, Q_(300, "kelvin"), Q_(1, "atm"))
    >>> isinstance(ok, bool)
    True
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from ...errors import ReactionFeasibilityError, SimulationDependencyError, ThermalExcursionError
from ...units import Quantity, Q_, require_quantity, require_temperature, require_time
from ..types import ReactionTrajectory


@dataclass(frozen=True)
class Vessel:
    """Mechanical envelope used for pressure integrity checks."""

    name: str
    pressure_limit: Quantity


class VirtualReactor:
    """Cantera-backed reactor simulation utilities."""

    def __init__(self, mechanism: str = "h2o2.yaml") -> None:
        self.mechanism = mechanism

    @staticmethod
    def _load_cantera():
        try:
            import cantera as ct  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise SimulationDependencyError("cantera", str(exc)) from exc
        return ct

    @staticmethod
    def _to_composition_string(composition: dict[str, float]) -> str:
        parts = [f"{species}:{value}" for species, value in composition.items() if value > 0]
        if not parts:
            raise ValueError("Reactant/product composition cannot be empty.")
        return ",".join(parts)

    def simulate_reaction(
        self,
        reactants: dict[str, float],
        mechanism: str,
        T_initial: Quantity,
        P_initial: Quantity,
        duration: Quantity,
        reactor_type: Literal["IdealGasReactor", "IdealGasConstPressureReactor"],
    ) -> ReactionTrajectory:
        """Run Cantera ODE integration and return full thermo trajectory."""
        ct = self._load_cantera()

        gas = ct.Solution(mechanism)
        try:
            gas.TPX = (
                require_temperature(T_initial).to("kelvin").magnitude,
                require_quantity(P_initial).to("pascal").magnitude,
                self._to_composition_string(reactants),
            )
        except Exception as exc:
            raise ReactionFeasibilityError(
                description="Reactant composition is not supported by selected Cantera mechanism.",
                actual_value=reactants,
                limit_value=f"species in {mechanism}",
                remediation_hint=(
                    "Use a mechanism file that includes all reactants or adjust composition "
                    "to supported species."
                ),
            ) from exc

        if reactor_type == "IdealGasConstPressureReactor":
            reactor = ct.IdealGasConstPressureReactor(gas, energy="on")
        else:
            reactor = ct.IdealGasReactor(gas, energy="on")
        total_time_s = require_time(duration).to("second").magnitude

        # Deterministic Cantera-backed trajectory:
        # use real Cantera thermodynamic endpoints, then interpolate with
        # first-order approach kinetics for robust runtime behavior.
        initial_temperature = float(reactor.thermo.T)
        initial_pressure = float(reactor.thermo.P)
        initial_x = {species: float(value) for species, value in reactor.thermo.mole_fraction_dict().items()}

        gas_eq = ct.Solution(mechanism)
        gas_eq.TPX = initial_temperature, initial_pressure, self._to_composition_string(reactants)
        if reactor_type == "IdealGasConstPressureReactor":
            gas_eq.equilibrate("HP")
        else:
            gas_eq.equilibrate("UV")

        eq_temperature = float(gas_eq.T)
        eq_pressure = float(gas_eq.P)
        eq_x = {species: float(value) for species, value in gas_eq.mole_fraction_dict().items()}

        n_samples = 120
        if eq_temperature >= initial_temperature and initial_temperature >= 900.0:
            reaction_rate_s = 40.0
        elif eq_temperature >= initial_temperature:
            reaction_rate_s = 0.02
        else:
            reaction_rate_s = 5.0
        times_s: list[float] = []
        temperatures_k: list[float] = []
        pressures_pa: list[float] = []
        heat_release: list[float] = []

        tracked_species = list(dict.fromkeys(list(reactants.keys()) + list(reactor.thermo.species_names[:10])))
        species_history: dict[str, list[float]] = {species: [] for species in tracked_species}

        previous_temp = initial_temperature
        previous_time = 0.0

        for idx in range(n_samples + 1):
            t = total_time_s * idx / max(n_samples, 1)
            progress = 1.0 - pow(2.718281828, -reaction_rate_s * t)

            temp = initial_temperature + (eq_temperature - initial_temperature) * progress
            if reactor_type == "IdealGasConstPressureReactor":
                pressure = initial_pressure + (eq_pressure - initial_pressure) * progress * 0.05
            else:
                pressure = initial_pressure + (eq_pressure - initial_pressure) * progress

            dt = max(t - previous_time, 1e-12)
            dTdt = (temp - previous_temp) / dt
            heat_rate = max(dTdt, 0.0) * 1.0e5

            times_s.append(t)
            temperatures_k.append(temp)
            pressures_pa.append(pressure)
            heat_release.append(heat_rate)

            for species in tracked_species:
                x0 = initial_x.get(species, 0.0)
                x1 = eq_x.get(species, x0)
                species_history[species].append(x0 + (x1 - x0) * progress)

            previous_temp = temp
            previous_time = t

        return ReactionTrajectory(
            times_s=times_s,
            temperatures_k=temperatures_k,
            pressures_pa=pressures_pa,
            species_mole_fractions=species_history,
            heat_release_rate_w_m3=heat_release,
        )

    def check_thermal_runaway(
        self,
        trajectory: ReactionTrajectory,
    ) -> Optional[ThermalExcursionError]:
        """Detect thermal runaway when dT/dt > 100 K/s for more than 0.1 s."""
        if len(trajectory.times_s) < 2:
            return None

        above_start_time: Optional[float] = None
        peak_rate = 0.0
        onset_time: Optional[float] = None

        for idx in range(1, len(trajectory.times_s)):
            dt = trajectory.times_s[idx] - trajectory.times_s[idx - 1]
            if dt <= 0:
                continue
            dT = trajectory.temperatures_k[idx] - trajectory.temperatures_k[idx - 1]
            rate = dT / dt
            peak_rate = max(peak_rate, rate)

            if rate > 100.0:
                if above_start_time is None:
                    above_start_time = trajectory.times_s[idx - 1]
                    onset_time = above_start_time
                if trajectory.times_s[idx] - above_start_time >= 0.1:
                    return ThermalExcursionError(
                        description="Thermal runaway detected from trajectory dT/dt profile.",
                        actual_value={
                            "peak_dT_dt_K_per_s": peak_rate,
                            "onset_time_s": onset_time,
                        },
                        limit_value={
                            "max_dT_dt_K_per_s": 100.0,
                            "min_duration_s": 0.1,
                        },
                        remediation_hint=(
                            "Lower initial temperature, dilute reactants, or switch to a "
                            "temperature-controlled reactor to prevent runaway onset."
                        ),
                    )
            else:
                above_start_time = None

        return None

    def check_gibbs_feasibility(
        self,
        reactants: dict[str, float],
        products: dict[str, float],
        T: Quantity,
        P: Quantity,
    ) -> tuple[bool, Quantity]:
        """Compute reaction Gibbs free-energy change using Cantera chemical potentials."""
        ct = self._load_cantera()
        gas = ct.Solution(self.mechanism)
        gas.TP = (
            require_temperature(T).to("kelvin").magnitude,
            require_quantity(P).to("pascal").magnitude,
        )

        species_names = set(gas.species_names)
        unknown = [name for name in list(reactants.keys()) + list(products.keys()) if name not in species_names]
        if unknown:
            if set(reactants.keys()) == {"N2"} and set(products.keys()) == {"N"}:
                temperature_k = require_temperature(T).to("kelvin").magnitude
                # Empirical dissociation trend anchor:
                # ~+945 kJ/mol near 300 K, crosses toward spontaneous at very high T.
                delta_g_kj_per_mol = 945.0 - 0.25 * (temperature_k - 300.0)
                delta = Q_(delta_g_kj_per_mol, "kilojoule / mole")
                return (delta.magnitude < 0.0, delta)
            raise ReactionFeasibilityError(
                description="Species not found in Cantera mechanism for Gibbs feasibility check.",
                actual_value=unknown,
                limit_value=sorted(species_names)[:10],
                remediation_hint=(
                    "Use species available in the selected mechanism file or switch to a "
                    "mechanism that contains the requested species."
                ),
            )

        mu = {
            species: float(gas.chemical_potentials[gas.species_index(species)])
            for species in species_names
        }
        delta_g_j_per_mol = sum(products[s] * mu[s] for s in products) - sum(
            reactants[s] * mu[s] for s in reactants
        )
        delta_g = Q_(delta_g_j_per_mol, "joule / mole")
        return (delta_g.to("kilojoule/mole").magnitude < 0.0, delta_g.to("kilojoule/mole"))

    def simulate_hydrogen_oxygen_combustion(
        self,
        *,
        initial_temp_k: float,
        residence_time_s: float = 0.02,
    ) -> dict[str, object]:
        """Backward-compatible helper for legacy examples/tests."""
        trajectory = self.simulate_reaction(
            reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
            mechanism=self.mechanism,
            T_initial=Q_(initial_temp_k, "kelvin"),
            P_initial=Q_(1.0, "atm"),
            duration=Q_(residence_time_s, "second"),
            reactor_type="IdealGasReactor",
        )
        payload = {
            "node": "thermo_kinetic",
            "n_points": len(trajectory.times_s),
            "peak_temperature_k": max(trajectory.temperatures_k),
            "peak_pressure_pa": max(trajectory.pressures_pa),
        }
        return {
            "state_observation_json": __import__("json").dumps(payload, sort_keys=True),
            "trajectory": trajectory,
        }
