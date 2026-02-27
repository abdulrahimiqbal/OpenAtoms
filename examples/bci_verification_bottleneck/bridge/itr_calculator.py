"""Information transfer rate (ITR) utilities for BCI throughput."""

from __future__ import annotations

import math


def compute_itr_bits_per_trial(
    accuracy: float,
    n_choices: int,
) -> float:
    """Standard BCI information transfer rate formula."""
    if n_choices <= 1:
        raise ValueError("n_choices must be > 1.")

    p = min(max(float(accuracy), 0.0), 1.0)
    n = float(n_choices)

    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return math.log2(n)

    term_correct = p * math.log2(p)
    term_error = (1.0 - p) * math.log2((1.0 - p) / (n - 1.0))
    bits = math.log2(n) + term_correct + term_error
    return max(bits, 0.0)


def compute_throughput(
    itr_bits_per_trial: float,
    repetitions_per_trial: float,
    flash_duration_ms: float = 100.0,
    inter_stimulus_interval_ms: float = 75.0,
) -> float:
    """Return throughput in bits per minute."""
    reps = float(repetitions_per_trial)
    if reps <= 0.0:
        raise ValueError("repetitions_per_trial must be > 0.")

    trial_duration_s = (
        reps * (float(flash_duration_ms) + float(inter_stimulus_interval_ms)) / 1000.0
    )
    if trial_duration_s <= 0.0:
        raise ValueError("Trial duration must be > 0.")

    trials_per_minute = 60.0 / trial_duration_s
    return float(itr_bits_per_trial) * trials_per_minute


def compute_bridge_speedup(
    lm_entropy_bits: float,
    uniform_entropy_bits: float = 5.17,
) -> float:
    """Theoretical Bridge speedup from entropy reduction."""
    entropy = float(lm_entropy_bits)
    if entropy <= 0.0:
        raise ValueError("lm_entropy_bits must be > 0.")
    return float(uniform_entropy_bits) / entropy
