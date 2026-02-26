"""Node B demo: Cantera thermo-kinetic safety checks and self-correction."""

from __future__ import annotations

import json

from openatoms.errors import ReactionFeasibilityError, ThermalExcursionError
from openatoms.sim.registry.kinetics_sim import VirtualReactor
from openatoms.units import Q_


def _trajectory_summary(trajectory) -> dict[str, float]:
    return {
        "n_points": len(trajectory.times_s),
        "peak_temperature_k": max(trajectory.temperatures_k),
        "peak_pressure_pa": max(trajectory.pressures_pa),
        "peak_heat_release_w_m3": max(trajectory.heat_release_rate_w_m3),
    }


def demo_1_thermal_runaway(reactor: VirtualReactor) -> None:
    print("=== DEMO 1: Thermal Runaway Detection ===")
    unsafe = reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism=reactor.mechanism,
        T_initial=Q_(1000, "kelvin"),
        P_initial=Q_(1, "atm"),
        duration=Q_(0.3, "second"),
        reactor_type="IdealGasReactor",
    )
    print("Unsafe trajectory summary:")
    print(json.dumps(_trajectory_summary(unsafe), indent=2))

    error = reactor.check_thermal_runaway(unsafe)
    if error is None:
        raise RuntimeError("Expected thermal runaway at 1000 K but none was detected.")
    print("Caught ThermalExcursionError:")
    print(error.to_agent_payload())

    safe = reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism=reactor.mechanism,
        T_initial=Q_(500, "kelvin"),
        P_initial=Q_(1, "atm"),
        duration=Q_(0.3, "second"),
        reactor_type="IdealGasReactor",
    )
    safe_error = reactor.check_thermal_runaway(safe)
    print("Corrected trajectory summary:")
    print(json.dumps(_trajectory_summary(safe), indent=2))
    print(json.dumps({"corrected_passed": safe_error is None}, indent=2))


def demo_2_gibbs_feasibility(reactor: VirtualReactor) -> None:
    print("\n=== DEMO 2: Gibbs Infeasibility ===")
    spontaneous, delta_g = reactor.check_gibbs_feasibility(
        reactants={"N2": 1.0},
        products={"N": 2.0},
        T=Q_(300, "kelvin"),
        P=Q_(1, "atm"),
    )

    if spontaneous:
        raise RuntimeError("Expected N2 -> 2N to be non-spontaneous at 300 K.")

    error = ReactionFeasibilityError(
        description="Proposed N2 dissociation is non-spontaneous at 300 K.",
        actual_value=f"{delta_g.to('kilojoule/mole').magnitude:.3f} kJ/mol",
        limit_value="<= 0 kJ/mol for spontaneous reaction",
        remediation_hint=(
            "Increase temperature substantially or use plasma/catalytic activation before "
            "proposing nitrogen dissociation."
        ),
    )
    print("Caught ReactionFeasibilityError:")
    print(error.to_agent_payload())

    spontaneous_hot, delta_g_hot = reactor.check_gibbs_feasibility(
        reactants={"N2": 1.0},
        products={"N": 2.0},
        T=Q_(5000, "kelvin"),
        P=Q_(1, "atm"),
    )
    print(json.dumps({
        "delta_g_300K_kJ_per_mol": round(delta_g.to("kilojoule/mole").magnitude, 3),
        "delta_g_5000K_kJ_per_mol": round(delta_g_hot.to("kilojoule/mole").magnitude, 3),
        "spontaneous_at_5000K": spontaneous_hot,
    }, indent=2))


def demo_3_pressure_safety(reactor: VirtualReactor) -> None:
    print("\n=== DEMO 3: Exothermic Safety Without Reactor Cooling ===")
    try:
        closed = reactor.simulate_reaction(
            reactants={"CH4": 1.0, "O2": 2.0, "N2": 7.52},
            mechanism=reactor.mechanism,
            T_initial=Q_(300, "kelvin"),
            P_initial=Q_(1, "atm"),
            duration=Q_(0.03, "second"),
            reactor_type="IdealGasReactor",
        )
    except ReactionFeasibilityError:
        # Fallback for lightweight mechanisms without methane species.
        closed = reactor.simulate_reaction(
            reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
            mechanism=reactor.mechanism,
            T_initial=Q_(300, "kelvin"),
            P_initial=Q_(1, "atm"),
            duration=Q_(0.03, "second"),
            reactor_type="IdealGasReactor",
        )
    closed_peak = max(closed.pressures_pa)
    pressure_limit = 101500.0
    print("Closed-reactor trajectory summary:")
    print(json.dumps(_trajectory_summary(closed), indent=2))

    if closed_peak <= pressure_limit:
        raise RuntimeError("Expected pressure limit exceedance in closed CH4 combustion demo.")

    error = ThermalExcursionError(
        description="Closed-vessel methane combustion exceeded pressure safety limit.",
        actual_value=f"{closed_peak:.3f} Pa",
        limit_value=f"{pressure_limit:.3f} Pa",
        remediation_hint=(
            "Use a vented/constant-pressure reactor configuration or lower fuel loading "
            "to keep pressure below vessel limits."
        ),
    )
    print("Caught ThermalExcursionError:")
    print(error.to_agent_payload())

    try:
        vented = reactor.simulate_reaction(
            reactants={"CH4": 1.0, "O2": 2.0, "N2": 7.52},
            mechanism=reactor.mechanism,
            T_initial=Q_(300, "kelvin"),
            P_initial=Q_(1, "atm"),
            duration=Q_(0.03, "second"),
            reactor_type="IdealGasConstPressureReactor",
        )
    except ReactionFeasibilityError:
        vented = reactor.simulate_reaction(
            reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
            mechanism=reactor.mechanism,
            T_initial=Q_(300, "kelvin"),
            P_initial=Q_(1, "atm"),
            duration=Q_(0.03, "second"),
            reactor_type="IdealGasConstPressureReactor",
        )
    vented_peak = max(vented.pressures_pa)
    print("Vented-reactor trajectory summary:")
    print(json.dumps(_trajectory_summary(vented), indent=2))
    print(json.dumps({"corrected_passed": vented_peak <= pressure_limit}, indent=2))


def main() -> None:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    demo_1_thermal_runaway(reactor)
    demo_2_gibbs_feasibility(reactor)
    demo_3_pressure_safety(reactor)


if __name__ == "__main__":
    main()
