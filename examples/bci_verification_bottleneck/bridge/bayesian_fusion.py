"""Bayesian fusion helpers for combining neural evidence with LM priors."""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np

DEFAULT_CHARSET = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def normalize_probabilities(
    prior: Mapping[str, float],
    chars: tuple[str, ...] | None = None,
) -> dict[str, float]:
    """Normalize a character prior to a proper probability distribution."""
    support = tuple(chars or tuple(prior.keys()))
    if not support:
        raise ValueError("Prior support is empty.")

    values = np.asarray([max(float(prior.get(ch, 0.0)), 0.0) for ch in support], dtype=float)
    total = float(values.sum())
    if not math.isfinite(total) or total <= 0.0:
        uniform = 1.0 / float(len(support))
        return {ch: uniform for ch in support}

    values /= total
    return {ch: float(values[idx]) for idx, ch in enumerate(support)}


def uniform_prior(chars: tuple[str, ...] | None = None) -> dict[str, float]:
    """Return a uniform prior over characters."""
    support = tuple(chars or DEFAULT_CHARSET)
    p = 1.0 / float(len(support))
    return {ch: p for ch in support}


def posterior_from_scores(
    scores: Mapping[str, float],
    *,
    d_prime: float,
    prior: Mapping[str, float],
    chars: tuple[str, ...] | None = None,
) -> dict[str, float]:
    """Single-step posterior update for one repetition.

    Likelihood ratio for each candidate c:
        log p(x|target=c) - log p(x|non-target=c) = d' * x_c - 0.5 * d'^2
    """
    support = tuple(chars or tuple(prior.keys()))
    normalized = normalize_probabilities(prior, support)
    log_prior = np.log(np.clip([normalized[ch] for ch in support], 1e-15, 1.0))

    observed = np.asarray([float(scores[ch]) for ch in support], dtype=float)
    llr = d_prime * observed - 0.5 * (d_prime**2)
    logits = log_prior + llr

    max_logit = float(np.max(logits))
    probs = np.exp(logits - max_logit)
    probs /= float(np.sum(probs))
    return {ch: float(probs[idx]) for idx, ch in enumerate(support)}


def distribution_for_entropy(
    entropy_bits: float,
    *,
    chars: tuple[str, ...] | None = None,
    tol: float = 1e-6,
) -> dict[str, float]:
    """Construct a peaked distribution with approximately the requested entropy."""
    support = tuple(chars or DEFAULT_CHARSET)
    n = len(support)
    if n < 2:
        raise ValueError("Need at least 2 characters to build distribution.")

    max_entropy = math.log2(n)
    target = min(max(float(entropy_bits), 0.0), max_entropy)

    if abs(target - max_entropy) <= tol:
        return uniform_prior(support)
    if target <= tol:
        probs = np.zeros(n, dtype=float)
        probs[0] = 1.0
        return {ch: float(probs[idx]) for idx, ch in enumerate(support)}

    def entropy_for_top_prob(top_p: float) -> float:
        tail = (1.0 - top_p) / float(n - 1)
        probs = np.array([top_p] + [tail] * (n - 1), dtype=float)
        probs = np.clip(probs, 1e-15, 1.0)
        return float(-np.sum(probs * np.log2(probs)))

    lo, hi = 1.0 / n, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if entropy_for_top_prob(mid) > target:
            lo = mid
        else:
            hi = mid
    top_p = (lo + hi) / 2.0
    tail = (1.0 - top_p) / float(n - 1)

    probs = np.array([top_p] + [tail] * (n - 1), dtype=float)
    return {ch: float(probs[idx]) for idx, ch in enumerate(support)}
