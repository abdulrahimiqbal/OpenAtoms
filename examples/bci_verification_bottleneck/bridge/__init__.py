"""Bridge architecture modules for the BCI verification bottleneck example."""

from .bayesian_fusion import (
    DEFAULT_CHARSET,
    distribution_for_entropy,
    normalize_probabilities,
    posterior_from_scores,
    uniform_prior,
)
from .entropy_estimator import estimate_character_entropy, estimate_corpus_entropy
from .itr_calculator import compute_bridge_speedup, compute_itr_bits_per_trial, compute_throughput
from .p300_simulator import simulate_p300_sequence, simulate_p300_trial
from .scaling_law import compute_crossover_d_prime, compute_scaling_law_curve

__all__ = [
    "DEFAULT_CHARSET",
    "compute_bridge_speedup",
    "compute_crossover_d_prime",
    "compute_itr_bits_per_trial",
    "compute_scaling_law_curve",
    "compute_throughput",
    "distribution_for_entropy",
    "estimate_character_entropy",
    "estimate_corpus_entropy",
    "normalize_probabilities",
    "posterior_from_scores",
    "simulate_p300_sequence",
    "simulate_p300_trial",
    "uniform_prior",
]
