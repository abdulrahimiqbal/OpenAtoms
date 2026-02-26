"""Noise injection and robustness sweep utilities.

Example:
    >>> from openatoms.sim.noise import SensorNoise
    >>> from openatoms.sim.types import SimulationParams
    >>> params = SimulationParams(pipette_cv=0.02, thermocouple_offset_c=0.0, pressure_scale_fraction=0.002)
    >>> SensorNoise().inject(params, "gaussian", seed=1).seed
    1
"""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Literal

from ..actions import Move, Transform
from ..dag import ProtocolGraph
from ..errors import PhysicsError
from ..units import Q_
from .types import RobustnessReport, SimulationParams


class SensorNoise:
    """Inject calibrated instrument noise and evaluate robustness.

    Instrument assumptions:
    - Pipette volume coefficient of variation: 1-3%.
    - Thermocouple accuracy: +/-0.5 degC.
    - Pressure transducer: +/-0.25% full scale.
    """

    def inject(
        self,
        params: SimulationParams,
        noise_model: Literal["gaussian", "uniform", "systematic"],
        seed: int,
    ) -> SimulationParams:
        """Return simulation parameters with deterministic seeded perturbation."""
        rng = random.Random(seed)

        if noise_model == "uniform":
            pipette_delta = rng.uniform(-params.pipette_cv, params.pipette_cv)
            thermo_delta = rng.uniform(-0.5, 0.5)
            pressure_delta = rng.uniform(-params.pressure_scale_fraction, params.pressure_scale_fraction)
        elif noise_model == "systematic":
            pipette_delta = params.pipette_cv
            thermo_delta = 0.5
            pressure_delta = params.pressure_scale_fraction
        else:
            pipette_delta = rng.gauss(0.0, params.pipette_cv)
            thermo_delta = rng.gauss(0.0, 0.5)
            pressure_delta = rng.gauss(0.0, params.pressure_scale_fraction)

        return SimulationParams(
            pipette_cv=max(params.pipette_cv + pipette_delta, 0.0),
            thermocouple_offset_c=params.thermocouple_offset_c + thermo_delta,
            pressure_scale_fraction=max(params.pressure_scale_fraction + pressure_delta, 0.0),
            seed=seed,
        )

    def robustness_sweep(
        self,
        graph: ProtocolGraph,
        n_trials: int = 100,
        noise_level: float = 0.02,
    ) -> RobustnessReport:
        """Run noisy trials and report robustness metrics.

        A pass rate threshold of 0.95 is used because common automation QA
        practice requires >=95% successful executions before release.
        """
        failures: dict[str, int] = {}
        max_failed_noise = 0.0
        successes = 0

        for trial in range(n_trials):
            trial_graph = deepcopy(graph)
            rng = random.Random(trial)
            trial_noise = max(abs(rng.gauss(0.0, noise_level)), 0.0)

            for action in trial_graph.sequence:
                if isinstance(action, Move):
                    scale = 1.0 + rng.gauss(0.0, noise_level)
                    action.amount = action.amount.to("milliliter") * scale
                elif isinstance(action, Transform):
                    if action.parameter == "temperature":
                        offset = rng.gauss(0.0, noise_level * 100.0)
                        action.target_value = action.target_value.to("degC") + Q_(offset, "delta_degC")

            try:
                trial_graph.dry_run()
                successes += 1
            except PhysicsError as exc:
                failures[exc.constraint_type] = failures.get(exc.constraint_type, 0) + 1
                max_failed_noise = max(max_failed_noise, trial_noise)

        pass_rate = successes / max(n_trials, 1)
        return RobustnessReport(
            pass_rate=pass_rate,
            n_trials=n_trials,
            failure_modes=failures,
            worst_case_parameter_sensitivity={"noise_level": max_failed_noise},
            research_ready=pass_rate >= 0.95,
        )
