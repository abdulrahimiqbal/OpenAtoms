"""Monte Carlo P300 speller simulation for Bridge Bayesian fusion."""

from __future__ import annotations

from typing import Callable, Mapping

import numpy as np

from .bayesian_fusion import DEFAULT_CHARSET, normalize_probabilities, uniform_prior


def _candidate_chars_from_prior(lm_prior: Mapping[str, float]) -> tuple[str, ...]:
    keys = tuple(sorted(lm_prior.keys()))
    if keys:
        return keys
    return DEFAULT_CHARSET


def _simulate_scores(
    *,
    target_idx: int,
    n_chars: int,
    n_repetitions: int,
    d_prime: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return scores with shape (n_chars, n_repetitions)."""
    scores = rng.normal(loc=0.0, scale=1.0, size=(n_chars, n_repetitions))
    scores[target_idx, :] += d_prime
    return scores


def simulate_p300_trial(
    target_char: str,
    d_prime: float,
    n_repetitions: int,
    lm_prior: dict[str, float],
    *,
    seed: int = 42,
    rng: np.random.Generator | None = None,
) -> dict:
    """Simulate one character-selection trial of a P300 speller."""
    local_rng = rng if rng is not None else np.random.default_rng(seed)
    chars = _candidate_chars_from_prior(lm_prior)
    if target_char not in chars:
        raise ValueError(f"Target character {target_char!r} is not in prior support.")

    target_idx = chars.index(target_char)
    prior = normalize_probabilities(lm_prior, chars)
    prior_vec = np.asarray([prior[ch] for ch in chars], dtype=float)

    scores = _simulate_scores(
        target_idx=target_idx,
        n_chars=len(chars),
        n_repetitions=n_repetitions,
        d_prime=d_prime,
        rng=local_rng,
    )

    # Sum log-likelihood ratio contributions over repetitions.
    llr = d_prime * np.sum(scores, axis=1) - 0.5 * (d_prime**2) * n_repetitions
    log_post = np.log(np.clip(prior_vec, 1e-15, 1.0)) + llr
    pred_idx = int(np.argmax(log_post))

    max_log = float(np.max(log_post))
    probs = np.exp(log_post - max_log)
    probs /= float(np.sum(probs))

    posterior = {ch: float(probs[idx]) for idx, ch in enumerate(chars)}
    selected_char = chars[pred_idx]

    return {
        "selected_char": selected_char,
        "correct": bool(selected_char == target_char),
        "posterior": posterior,
        "repetitions_used": int(n_repetitions),
        "method": "bridge",
    }


def simulate_p300_sequence(
    text: str,
    d_prime: float,
    lm_prior_fn: Callable[[str], Mapping[str, float]],
    *,
    n_repetitions: int = 8,
    seed: int = 42,
    method: str = "bridge",
    chars: tuple[str, ...] = DEFAULT_CHARSET,
) -> dict:
    """Simulate a text entry sequence character-by-character."""
    rng = np.random.default_rng(seed)

    trajectory: list[dict] = []
    typed_chars: list[str] = []
    n_correct = 0

    for target in text:
        if target == " ":
            typed_chars.append(" ")
            trajectory.append(
                {
                    "target_char": " ",
                    "selected_char": " ",
                    "correct": True,
                    "posterior": {},
                    "repetitions_used": 0,
                    "method": method,
                }
            )
            continue

        context = "".join(typed_chars)
        raw_prior = dict(lm_prior_fn(context))
        if method == "uniform":
            prior = uniform_prior(chars)
        else:
            prior = normalize_probabilities(raw_prior, chars)

        trial = simulate_p300_trial(
            target_char=target,
            d_prime=d_prime,
            n_repetitions=n_repetitions,
            lm_prior=prior,
            seed=seed,
            rng=rng,
        )
        trial["target_char"] = target
        trial["method"] = method
        trajectory.append(trial)
        typed_chars.append(str(trial["selected_char"]))
        n_correct += int(bool(trial["correct"]))

    effective_trials = sum(1 for ch in text if ch != " ")
    accuracy = (n_correct / effective_trials) if effective_trials else 1.0

    return {
        "target_text": text,
        "typed_text": "".join(typed_chars),
        "n_characters": int(effective_trials),
        "n_correct": int(n_correct),
        "accuracy": float(accuracy),
        "trajectory": trajectory,
        "d_prime": float(d_prime),
        "n_repetitions": int(n_repetitions),
        "method": method,
        "seed": int(seed),
    }
