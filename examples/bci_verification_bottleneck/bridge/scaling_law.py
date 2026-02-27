"""Crossover and scaling-law computations for the Bridge architecture."""

from __future__ import annotations

import numpy as np

from .bayesian_fusion import DEFAULT_CHARSET, distribution_for_entropy, uniform_prior
from .itr_calculator import compute_itr_bits_per_trial, compute_throughput

_PANGRAM = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"


def _simulate_accuracy_vectorized(
    *,
    d_prime: float,
    prior_probs: np.ndarray,
    n_trials: int,
    n_repetitions: int,
    rng: np.random.Generator,
) -> float:
    n_chars = prior_probs.size

    targets = rng.integers(low=0, high=n_chars, size=n_trials)
    # scores shape: (n_trials, n_chars, n_repetitions)
    scores = rng.normal(loc=0.0, scale=1.0, size=(n_trials, n_chars, n_repetitions))
    scores[np.arange(n_trials), targets, :] += d_prime

    llr = d_prime * np.sum(scores, axis=2) - 0.5 * (d_prime**2) * n_repetitions
    log_post = np.log(np.clip(prior_probs, 1e-15, 1.0))[None, :] + llr
    preds = np.argmax(log_post, axis=1)
    return float(np.mean(preds == targets))


def compute_crossover_d_prime(
    lm_entropy_bits: float,
    d_prime_range: np.ndarray,
    n_trials_per_point: int = 1000,
    *,
    seed: int = 42,
) -> dict:
    """Find the d' where Bridge ITR approximately equals uniform ITR."""
    d_values = np.asarray(d_prime_range, dtype=float)
    if d_values.ndim != 1 or d_values.size == 0:
        raise ValueError("d_prime_range must be a non-empty 1D array.")

    chars = DEFAULT_CHARSET
    n_choices = len(chars)
    n_reps = 8.0

    bridge_prior = distribution_for_entropy(float(lm_entropy_bits), chars=chars)
    bridge_prior_vec = np.asarray([bridge_prior[ch] for ch in chars], dtype=float)
    uniform_prior_vec = np.asarray([uniform_prior(chars)[ch] for ch in chars], dtype=float)

    rng = np.random.default_rng(seed)

    bridge_itrs = np.zeros_like(d_values)
    uniform_itrs = np.zeros_like(d_values)

    for idx, d_prime in enumerate(d_values):
        bridge_acc = _simulate_accuracy_vectorized(
            d_prime=float(d_prime),
            prior_probs=bridge_prior_vec,
            n_trials=int(n_trials_per_point),
            n_repetitions=int(round(n_reps)),
            rng=rng,
        )
        uniform_acc = _simulate_accuracy_vectorized(
            d_prime=float(d_prime),
            prior_probs=uniform_prior_vec,
            n_trials=int(n_trials_per_point),
            n_repetitions=int(round(n_reps)),
            rng=rng,
        )

        bridge_itr_trial = compute_itr_bits_per_trial(bridge_acc, n_choices)
        uniform_itr_trial = compute_itr_bits_per_trial(uniform_acc, n_choices)

        bridge_itrs[idx] = compute_throughput(bridge_itr_trial, repetitions_per_trial=n_reps)
        uniform_itrs[idx] = compute_throughput(uniform_itr_trial, repetitions_per_trial=n_reps)

    delta = bridge_itrs - uniform_itrs
    if np.all(delta >= 0):
        crossover = float(d_values[-1])
    elif np.all(delta <= 0):
        crossover = float(d_values[0])
    else:
        # First non-negative crossing, linearly interpolated.
        crossing_idx = int(np.where(delta >= 0)[0][0])
        if crossing_idx == 0:
            crossover = float(d_values[0])
        else:
            x0, x1 = float(d_values[crossing_idx - 1]), float(d_values[crossing_idx])
            y0, y1 = float(delta[crossing_idx - 1]), float(delta[crossing_idx])
            if abs(y1 - y0) < 1e-12:
                crossover = x1
            else:
                t = -y0 / (y1 - y0)
                crossover = x0 + t * (x1 - x0)

    return {
        "crossover_d_prime": float(crossover),
        "bridge_itrs": bridge_itrs,
        "uniform_itrs": uniform_itrs,
        "d_prime_values": d_values,
        "lm_entropy_bits": float(lm_entropy_bits),
        "n_trials_per_point": int(n_trials_per_point),
        "text": _PANGRAM,
    }


def compute_scaling_law_curve(
    entropy_range_bits: np.ndarray,
) -> np.ndarray:
    """Return theoretical Bridge speedup = uniform_entropy / lm_entropy."""
    values = np.asarray(entropy_range_bits, dtype=float)
    if np.any(values <= 0.0):
        raise ValueError("All entropy values must be > 0.")
    return 5.17 / values
