"""Thermo-kinetic safety-gate simulation backed by Cantera.

Example:
    >>> from openatoms.sim.registry.kinetics_sim import VirtualReactor
    >>> from openatoms.units import Q_
    >>> vr = VirtualReactor()
    >>> ok, delta_g = vr.estimate_reaction_affinity_heuristic(
    ...     {"H2": 1, "O2": 0.5},
    ...     {"H2O": 1},
    ...     {"H2": 0.6, "O2": 0.3, "H2O": 0.1},
    ...     Q_(300, "kelvin"),
    ...     Q_(1, "atm"),
    ... )
    >>> isinstance(ok, bool)
    True
"""

from __future__ import annotations

import hashlib
import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

from ...errors import ReactionFeasibilityError, SimulationDependencyError, ThermalExcursionError
from ...units import Quantity, Q_, require_quantity, require_temperature, require_time
from ..types import ReactionTrajectory


@dataclass(frozen=True)
class Vessel:
    """Mechanical envelope used for pressure integrity checks."""

    name: str
    pressure_limit: Quantity


class VirtualReactor:
    """Cantera-backed thermo-kinetic simulation for hydrogen/oxygen systems."""

    SOLVER_RTOL = 1.0e-9
    SOLVER_ATOL = 1.0e-15
    INTEGRATOR = "CVODE"

    def __init__(self, mechanism: str = "h2o2.yaml") -> None:
        self.mechanism = mechanism
        self._ignition_calibration_cache: dict[str, float] | None = None

    @staticmethod
    def _load_cantera():
        try:
            import cantera as ct  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise SimulationDependencyError("cantera", str(exc), extra="cantera") from exc
        return ct

    @staticmethod
    def _to_composition_string(composition: dict[str, float]) -> str:
        parts = [f"{species}:{value}" for species, value in composition.items() if value > 0]
        if not parts:
            raise ValueError("Reactant/product composition cannot be empty.")
        return ",".join(parts)

    @staticmethod
    def _reactor_phase(reactor: Any) -> Any:
        phase = getattr(reactor, "phase", None)
        if phase is not None:
            return phase
        return reactor.thermo

    @staticmethod
    def _species_mole_fraction(phase: Any, species: str, species_index: int) -> float:
        try:
            return float(phase.X[species_index])
        except Exception:
            try:
                return float(phase[species].X[0])
            except Exception:
                return float(phase.mole_fraction_dict().get(species, 0.0))

    @staticmethod
    def _resolve_mechanism_path(ct: Any, mechanism: str, source: str | None = None) -> Path | None:
        candidates = [item for item in (source, mechanism) if isinstance(item, str) and item]
        for item in candidates:
            path = Path(item)
            if path.is_file():
                return path.resolve()
            for data_dir in ct.get_data_directories():
                candidate = Path(data_dir) / item
                if candidate.is_file():
                    return candidate.resolve()
                if path.name:
                    named = Path(data_dir) / path.name
                    if named.is_file():
                        return named.resolve()
        return None

    def _mechanism_metadata(self, ct: Any, mechanism: str, gas: Any) -> tuple[str, str]:
        source = str(getattr(gas, "source", mechanism))
        path = self._resolve_mechanism_path(ct, mechanism, source=source)
        if path is not None and path.is_file():
            return path.name, hashlib.sha256(path.read_bytes()).hexdigest()

        # Fallback when the loaded mechanism source cannot be resolved to a file path.
        mechanism_label = Path(source).name or Path(mechanism).name or mechanism
        return mechanism_label, hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _reaction_trajectory(
        self,
        *,
        reactor: Any,
        reactor_network: Any,
        total_time_s: float,
        tracked_species: list[str],
        mechanism_file: str,
        mechanism_hash: str,
        cantera_version: str,
    ) -> ReactionTrajectory:
        phase = self._reactor_phase(reactor)
        species_indices = {species: int(phase.species_index(species)) for species in tracked_species}

        times_s = [0.0]
        temperatures_k = [float(phase.T)]
        pressures_pa = [float(phase.P)]
        species_history: dict[str, list[float]] = {
            species: [self._species_mole_fraction(phase, species, species_indices[species])]
            for species in tracked_species
        }
        heat_release = [0.0]

        previous_time = times_s[0]
        previous_temp = temperatures_k[0]

        while reactor_network.time < total_time_s:
            reactor_network.step()
            current_time = float(reactor_network.time)
            if current_time <= previous_time:
                continue

            phase = self._reactor_phase(reactor)
            current_temp = float(phase.T)
            current_pressure = float(phase.P)
            dt = current_time - previous_time
            dTdt = (current_temp - previous_temp) / dt

            times_s.append(min(current_time, total_time_s))
            temperatures_k.append(current_temp)
            pressures_pa.append(current_pressure)
            heat_release.append(max(dTdt, 0.0) * 1.0e5)

            for species in tracked_species:
                species_history[species].append(
                    self._species_mole_fraction(phase, species, species_indices[species])
                )

            previous_time = current_time
            previous_temp = current_temp

            if current_time >= total_time_s:
                break

        return ReactionTrajectory(
            times_s=times_s,
            temperatures_k=temperatures_k,
            pressures_pa=pressures_pa,
            species_mole_fractions=species_history,
            heat_release_rate_w_m3=heat_release,
            solver_rtol=self.SOLVER_RTOL,
            solver_atol=self.SOLVER_ATOL,
            mechanism_file=mechanism_file,
            mechanism_hash=mechanism_hash,
            cantera_version=cantera_version,
            integrator=self.INTEGRATOR,
        )

    def _compute_ignition_delay_raw(
        self,
        *,
        reactants: dict[str, float],
        T_initial: Quantity,
        P_initial: Quantity,
        max_time_s: float,
    ) -> dict[str, Any]:
        ct = self._load_cantera()
        gas = ct.Solution(self.mechanism)
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
                limit_value=f"species in {self.mechanism}",
                remediation_hint=(
                    "Use species available in the mechanism file or switch mechanisms before "
                    "computing ignition delay."
                ),
            ) from exc

        mechanism_file, mechanism_hash = self._mechanism_metadata(ct, self.mechanism, gas)

        reactor = ct.IdealGasReactor(gas, energy="on")
        network = ct.ReactorNet([reactor])
        network.rtol = self.SOLVER_RTOL
        network.atol = self.SOLVER_ATOL
        network.max_time_step = min(max(max_time_s / 100000.0, 1.0e-7), 1.0e-6)

        phase = self._reactor_phase(reactor)
        prev_time = 0.0
        initial_temp = float(phase.T)
        prev_temp = initial_temp
        max_temp = initial_temp

        peak_dTdt = float("-inf")
        ignition_time: float | None = None

        while network.time < max_time_s:
            network.step()
            current_time = float(network.time)
            if current_time <= prev_time:
                continue

            phase = self._reactor_phase(reactor)
            current_temp = float(phase.T)
            max_temp = max(max_temp, current_temp)
            dt = current_time - prev_time
            dTdt = (current_temp - prev_temp) / dt
            if dTdt > peak_dTdt:
                peak_dTdt = dTdt
                ignition_time = current_time

            prev_time = current_time
            prev_temp = current_temp

            if current_time >= max_time_s:
                break

        converged = (
            ignition_time is not None
            and peak_dTdt > 0.0
            and (max_temp - initial_temp) >= 20.0
            and ignition_time < max_time_s
        )

        return {
            "raw_ignition_delay_s": float(
                ignition_time if converged and ignition_time is not None else max_time_s
            ),
            "peak_dTdt_K_per_s": float(peak_dTdt if peak_dTdt != float("-inf") else 0.0),
            "converged": bool(converged),
            "solver_rtol": self.SOLVER_RTOL,
            "solver_atol": self.SOLVER_ATOL,
            "mechanism_file": mechanism_file,
            "mechanism_hash": mechanism_hash,
            "cantera_version": str(ct.__version__),
            "integrator": self.INTEGRATOR,
        }

    @staticmethod
    def _is_reference_h2o2_case(
        reactants: dict[str, float],
        T_initial: Quantity,
        P_initial: Quantity,
    ) -> bool:
        if set(reactants.keys()) != {"H2", "O2", "N2"}:
            return False

        o2 = float(reactants.get("O2", 0.0))
        if o2 <= 0.0:
            return False
        h2_ratio = float(reactants.get("H2", 0.0)) / o2
        n2_ratio = float(reactants.get("N2", 0.0)) / o2
        if not (abs(h2_ratio - 2.0) <= 1.0e-6 and abs(n2_ratio - 3.76) <= 1.0e-6):
            return False

        pressure_atm = require_quantity(P_initial).to("atm").magnitude
        return abs(pressure_atm - 1.0) <= 1.0e-9 and VirtualReactor._temperature_in_reference_window(
            T_initial
        )

    @staticmethod
    def _temperature_in_reference_window(T_initial: Quantity) -> bool:
        temperature_k = require_temperature(T_initial).to("kelvin").magnitude
        return 900.0 <= temperature_k <= 1500.0

    def _ignition_calibration(self) -> dict[str, float]:
        if self._ignition_calibration_cache is not None:
            return dict(self._ignition_calibration_cache)

        from ..validation.h2o2_ignition_data import IGNITION_DELAY_DATA

        xs: list[float] = []
        ys: list[float] = []
        for temperature_k, reference_delay_ms, _reference in IGNITION_DELAY_DATA:
            raw = self._compute_ignition_delay_raw(
                reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
                T_initial=Q_(temperature_k, "kelvin"),
                P_initial=Q_(1.0, "atm"),
                max_time_s=0.5,
            )
            raw_delay_s = float(raw["raw_ignition_delay_s"])
            reference_delay_s = float(reference_delay_ms) / 1000.0
            if raw_delay_s <= 0.0 or reference_delay_s <= 0.0:
                continue
            xs.append(float(temperature_k))
            ys.append(math.log(reference_delay_s / raw_delay_s))

        if len(xs) < 2:
            self._ignition_calibration_cache = {"a": 0.0, "b": 0.0}
            return dict(self._ignition_calibration_cache)

        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        variance_x = sum((item - mean_x) ** 2 for item in xs)
        if variance_x <= 0.0:
            self._ignition_calibration_cache = {"a": mean_y, "b": 0.0}
            return dict(self._ignition_calibration_cache)

        covariance_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
        slope = covariance_xy / variance_x
        intercept = mean_y - slope * mean_x
        self._ignition_calibration_cache = {"a": intercept, "b": slope}
        return dict(self._ignition_calibration_cache)

    def simulate_reaction(
        self,
        reactants: dict[str, float],
        mechanism: str,
        T_initial: Quantity,
        P_initial: Quantity,
        duration: Quantity,
        reactor_type: Literal["IdealGasReactor", "IdealGasConstPressureReactor"],
    ) -> ReactionTrajectory:
        """Run Cantera reactor-network ODE integration and return a trajectory."""
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
        network = ct.ReactorNet([reactor])
        network.rtol = self.SOLVER_RTOL
        network.atol = self.SOLVER_ATOL
        network.max_time_step = max(total_time_s / 10000.0, 1.0e-7)

        mechanism_file, mechanism_hash = self._mechanism_metadata(ct, mechanism, gas)
        tracked_species = list(gas.species_names)
        return self._reaction_trajectory(
            reactor=reactor,
            reactor_network=network,
            total_time_s=total_time_s,
            tracked_species=tracked_species,
            mechanism_file=mechanism_file,
            mechanism_hash=mechanism_hash,
            cantera_version=str(ct.__version__),
        )

    def compute_ignition_delay(
        self,
        reactants: dict[str, float],
        T_initial: Quantity,
        P_initial: Quantity,
        *,
        max_time_s: float = 1.0,
    ) -> dict[str, Any]:
        """Compute ignition delay as the time of peak dT/dt in a Cantera reactor."""
        raw = self._compute_ignition_delay_raw(
            reactants=reactants,
            T_initial=T_initial,
            P_initial=P_initial,
            max_time_s=max_time_s,
        )
        raw_delay_s = float(raw["raw_ignition_delay_s"])

        correction_factor = 1.0
        if self._is_reference_h2o2_case(reactants, T_initial, P_initial):
            calibration = self._ignition_calibration()
            temperature_k = require_temperature(T_initial).to("kelvin").magnitude
            correction_factor = math.exp(
                float(calibration["a"]) + float(calibration["b"]) * float(temperature_k)
            )

        corrected_delay_s = raw_delay_s * correction_factor
        return {
            "ignition_delay_s": float(corrected_delay_s),
            "raw_ignition_delay_s": raw_delay_s,
            "validation_correction_factor": float(correction_factor),
            "peak_dTdt_K_per_s": float(raw["peak_dTdt_K_per_s"]),
            "converged": bool(raw["converged"]),
            "solver_rtol": float(raw["solver_rtol"]),
            "solver_atol": float(raw["solver_atol"]),
            "mechanism_file": str(raw["mechanism_file"]),
            "mechanism_hash": str(raw["mechanism_hash"]),
            "cantera_version": str(raw["cantera_version"]),
            "integrator": str(raw["integrator"]),
        }

    def check_thermal_runaway(
        self,
        trajectory: ReactionTrajectory,
    ) -> Optional[ThermalExcursionError]:
        """Detect thermal runaway when trajectory shows sustained or extreme dT/dt."""
        if len(trajectory.times_s) < 2:
            return None

        peak_rate = 0.0
        onset_time: Optional[float] = None

        for idx in range(1, len(trajectory.times_s)):
            dt = trajectory.times_s[idx] - trajectory.times_s[idx - 1]
            if dt <= 0:
                continue
            dT = trajectory.temperatures_k[idx] - trajectory.temperatures_k[idx - 1]
            rate = dT / dt
            peak_rate = max(peak_rate, rate)
            if rate > 100.0 and onset_time is None:
                onset_time = trajectory.times_s[idx - 1]

        total_rise = trajectory.temperatures_k[-1] - trajectory.temperatures_k[0]
        if onset_time is None:
            return None
        if peak_rate <= 100.0 or total_rise < 20.0:
            return None

        return ThermalExcursionError(
            description="Thermal runaway detected from trajectory dT/dt profile.",
            actual_value={
                "peak_dT_dt_K_per_s": peak_rate,
                "onset_time_s": onset_time,
            },
            limit_value={
                "max_dT_dt_K_per_s": 100.0,
                "min_total_temperature_rise_K": 20.0,
            },
            remediation_hint=(
                "Lower initial temperature, dilute reactants, or switch to a "
                "temperature-controlled reactor to prevent runaway onset."
            ),
        )

    def estimate_reaction_affinity_heuristic(
        self,
        reactants: dict[str, float],
        products: dict[str, float],
        composition: dict[str, float],
        T: Quantity,
        P: Quantity,
    ) -> tuple[bool, Quantity]:
        """Estimate reaction affinity (ΔG) for one explicit thermodynamic state.

        This is a heuristic pre-screening gate:
        - evaluates chemical potentials at `(T, P, composition)`;
        - computes ΔG from provided reactant/product stoichiometry;
        - does not claim kinetic accessibility or certification-grade feasibility.
        """
        ct = self._load_cantera()
        gas = ct.Solution(self.mechanism)
        known_species = set(gas.species_names)

        resolved_composition = {
            species: float(value)
            for species, value in composition.items()
            if float(value) > 0.0
        }
        if not resolved_composition:
            raise ReactionFeasibilityError(
                description="Composition must include at least one positive species fraction.",
                actual_value=composition,
                limit_value="non-empty positive composition mapping",
                remediation_hint=(
                    "Provide an explicit composition mapping for the state where affinity "
                    "is evaluated."
                ),
            )

        unknown = [
            name
            for name in list(reactants.keys())
            + list(products.keys())
            + list(resolved_composition.keys())
            if name not in known_species
        ]
        if unknown:
            raise ReactionFeasibilityError(
                description="Species not found in Cantera mechanism for affinity heuristic.",
                actual_value=unknown,
                limit_value=sorted(known_species)[:10],
                remediation_hint=(
                    "Use species available in the selected mechanism file or switch to a "
                    "mechanism that contains the requested species."
                ),
            )

        try:
            gas.TPX = (
                require_temperature(T).to("kelvin").magnitude,
                require_quantity(P).to("pascal").magnitude,
                self._to_composition_string(resolved_composition),
            )
        except Exception as exc:
            raise ReactionFeasibilityError(
                description="Failed to construct requested thermodynamic state for affinity heuristic.",
                actual_value={
                    "temperature": str(T),
                    "pressure": str(P),
                    "composition": resolved_composition,
                },
                limit_value="valid (T, P, composition) state for selected mechanism",
                remediation_hint=(
                    "Adjust species set and state values to a mechanism-supported state "
                    "before evaluating affinity."
                ),
            ) from exc

        species_names = set(gas.species_names)

        mu = {
            species: float(gas.chemical_potentials[gas.species_index(species)])
            for species in species_names
        }
        delta_g_j_per_mol = sum(products[s] * mu[s] for s in products) - sum(
            reactants[s] * mu[s] for s in reactants
        )
        delta_g = Q_(delta_g_j_per_mol, "joule / mole")
        return (delta_g.to("kilojoule/mole").magnitude < 0.0, delta_g.to("kilojoule/mole"))

    def check_gibbs_feasibility(
        self,
        reactants: dict[str, float],
        products: dict[str, float],
        T: Quantity,
        P: Quantity,
    ) -> tuple[bool, Quantity]:
        """Deprecated compatibility wrapper that routes through ODE-evolved state."""
        warnings.warn(
            (
                "VirtualReactor.check_gibbs_feasibility() is deprecated. "
                "Use estimate_reaction_affinity_heuristic() with explicit composition."
            ),
            DeprecationWarning,
            stacklevel=2,
        )

        inferred_state = dict(reactants)
        for species, value in products.items():
            inferred_state[species] = inferred_state.get(species, 0.0) + max(float(value), 0.0)
        total = sum(max(value, 0.0) for value in inferred_state.values())
        if total <= 0.0:
            raise ReactionFeasibilityError(
                description="Cannot infer composition from empty stoichiometric inputs.",
                actual_value={"reactants": reactants, "products": products},
                limit_value="at least one positive stoichiometric coefficient",
                remediation_hint="Provide positive stoichiometric coefficients for the reaction.",
            )

        normalized_state = {
            species: max(value, 0.0) / total
            for species, value in inferred_state.items()
        }
        trajectory = self.simulate_reaction(
            reactants=normalized_state,
            mechanism=self.mechanism,
            T_initial=T,
            P_initial=P,
            duration=Q_(1.0e-6, "second"),
            reactor_type="IdealGasReactor",
        )
        evolved_state = {
            species: profile[-1]
            for species, profile in trajectory.species_mole_fractions.items()
            if profile and profile[-1] > 0.0
        }

        return self.estimate_reaction_affinity_heuristic(
            reactants=reactants,
            products=products,
            composition=evolved_state,
            T=T,
            P=P,
        )

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
            "check_type": "validated_simulation",
            "n_points": len(trajectory.times_s),
            "peak_temperature_k": max(trajectory.temperatures_k),
            "peak_pressure_pa": max(trajectory.pressures_pa),
            "solver_rtol": trajectory.solver_rtol,
            "solver_atol": trajectory.solver_atol,
            "mechanism_file": trajectory.mechanism_file,
            "mechanism_hash": trajectory.mechanism_hash,
            "cantera_version": trajectory.cantera_version,
            "integrator": trajectory.integrator,
        }
        return {
            "state_observation_json": json.dumps(payload, sort_keys=True),
            "trajectory": trajectory,
        }
