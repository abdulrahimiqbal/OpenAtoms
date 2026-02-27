"""OpenAtoms-compatible simulator node for BCI experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from bridge.bayesian_fusion import DEFAULT_CHARSET, distribution_for_entropy, uniform_prior
from bridge.itr_calculator import compute_itr_bits_per_trial, compute_throughput
from bridge.p300_simulator import simulate_p300_sequence
from bridge.scaling_law import compute_crossover_d_prime
from validation import reference_data

from openatoms_integration.bci_ir import BCIExperimentProtocol


@dataclass(frozen=True)
class SimulationResult:
    status: str
    check_type: str
    payload: dict[str, Any]
    reason: str | None = None


class BCISimulator:
    """OpenAtoms-compatible simulator node for BCI experiments."""

    def __init__(
        self,
        *,
        model_version: str = "bci-sim-1.0",
        entropy_source: str = "measured_api",
        n_monte_carlo_trials: int = 750,
    ):
        self._model_version = model_version
        self._entropy_source = entropy_source
        self._n_monte_carlo_trials = int(n_monte_carlo_trials)

    @property
    def check_type(self) -> str:
        return "validated_simulation"

    def _prior_from_protocol(self, protocol: BCIExperimentProtocol) -> dict[str, float]:
        if protocol.fusion_method == "uniform":
            return uniform_prior(DEFAULT_CHARSET)
        return distribution_for_entropy(protocol.lm_entropy_bits, chars=DEFAULT_CHARSET)

    def run(self, protocol: BCIExperimentProtocol) -> SimulationResult:
        prior = self._prior_from_protocol(protocol)

        sequence = simulate_p300_sequence(
            text=protocol.corpus_text,
            d_prime=protocol.d_prime_hypothesis,
            lm_prior_fn=lambda _context: prior,
            n_repetitions=protocol.n_repetitions,
            seed=protocol.seed,
            method="bridge" if protocol.fusion_method == "bayesian" else "uniform",
            chars=DEFAULT_CHARSET,
        )

        accuracy = float(sequence["accuracy"])
        itr_bits = compute_itr_bits_per_trial(accuracy, n_choices=len(DEFAULT_CHARSET))
        itr_bpm = compute_throughput(
            itr_bits,
            repetitions_per_trial=float(protocol.n_repetitions),
            flash_duration_ms=protocol.flash_duration_ms,
            inter_stimulus_interval_ms=75.0,
        )

        d_range = np.linspace(0.1, 3.0, 30)
        crossover = compute_crossover_d_prime(
            lm_entropy_bits=protocol.lm_entropy_bits,
            d_prime_range=d_range,
            n_trials_per_point=self._n_monte_carlo_trials,
            seed=protocol.seed,
        )
        measured_crossover = float(crossover["crossover_d_prime"])

        within_tolerance = (
            abs(measured_crossover - reference_data.CROSSOVER_D_PRIME)
            <= reference_data.CROSSOVER_TOLERANCE
        )

        payload = {
            "protocol": asdict(protocol),
            "accuracy": accuracy,
            "itr_bits_per_trial": float(itr_bits),
            "itr_bpm": float(itr_bpm),
            "lm_model": protocol.lm_model,
            "lm_entropy_bits": float(protocol.lm_entropy_bits),
            "simulation_seed": int(protocol.seed),
            "n_monte_carlo_trials": int(self._n_monte_carlo_trials),
            "crossover_d_prime_measured": measured_crossover,
            "crossover_d_prime_published": float(reference_data.CROSSOVER_D_PRIME),
            "crossover_within_tolerance": bool(within_tolerance),
            "entropy_source": self._entropy_source,
            "model_version": self._model_version,
            "check_type": "validated_simulation",
        }

        return SimulationResult(
            status="ok",
            check_type="validated_simulation",
            payload=payload,
            reason=None,
        )
