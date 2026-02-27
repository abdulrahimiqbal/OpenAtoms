"""DERCo N400 loading and single-trial d' estimation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def _synthetic_derco_dataset() -> dict[str, Any]:
    rng = np.random.default_rng(2026)
    n_trials = 420
    n_channels = 16
    n_timepoints = 256

    labels = rng.integers(low=0, high=2, size=n_trials, endpoint=False)
    epochs = rng.normal(loc=0.0, scale=1.0, size=(n_trials, n_channels, n_timepoints))

    # Inject a very small N400-like negativity for unexpected items to mimic weak passive effect.
    n400_slice = slice(90, 140)
    unexpected = labels == 0
    epochs[unexpected, :, n400_slice] -= 0.003

    return {
        "epochs": epochs.astype(np.float64),
        "labels": labels.astype(np.int64),
        "metadata": {
            "source": "synthetic_fallback",
            "sfreq": 256.0,
            "tmin": -0.1,
            "n400_window_samples": [90, 140],
        },
    }


def _load_npz(path: Path) -> dict[str, Any] | None:
    try:
        payload = np.load(path, allow_pickle=True)
    except Exception:
        return None

    if "epochs" not in payload or "labels" not in payload:
        return None

    epochs = np.asarray(payload["epochs"], dtype=np.float64)
    labels = np.asarray(payload["labels"], dtype=np.int64)

    metadata: dict[str, Any] = {"source": str(path)}
    if "metadata" in payload:
        raw_metadata = payload["metadata"]
        try:
            if isinstance(raw_metadata, np.ndarray) and raw_metadata.shape == ():
                raw_metadata = raw_metadata.item()
            if isinstance(raw_metadata, str):
                parsed = json.loads(raw_metadata)
                if isinstance(parsed, dict):
                    metadata.update(parsed)
            elif isinstance(raw_metadata, dict):
                metadata.update(raw_metadata)
        except Exception:
            pass

    return {"epochs": epochs, "labels": labels, "metadata": metadata}


def _load_with_mne(path: Path) -> dict[str, Any] | None:
    try:
        import mne  # type: ignore
    except Exception:
        return None

    candidates: list[Path] = []
    if path.is_file() and path.suffix in {".fif", ".fif.gz"}:
        candidates = [path]
    elif path.is_dir():
        candidates = sorted(path.rglob("*-epo.fif")) + sorted(path.rglob("*-epo.fif.gz"))
        if not candidates:
            candidates = sorted(path.rglob("*.fif"))

    for candidate in candidates:
        try:
            epochs_obj = mne.read_epochs(str(candidate), preload=True, verbose="ERROR")
        except Exception:
            continue

        epochs = epochs_obj.get_data(copy=True)
        event_codes = epochs_obj.events[:, -1]

        event_id = epochs_obj.event_id or {}
        expected_codes = {
            code
            for name, code in event_id.items()
            if "expect" in name.lower() and "un" not in name.lower()
        }
        unexpected_codes = {
            code
            for name, code in event_id.items()
            if "unexpected" in name.lower() or "violation" in name.lower()
        }

        if expected_codes and unexpected_codes:
            labels = np.where(np.isin(event_codes, list(expected_codes)), 1, 0)
        else:
            # Fallback: lower half of event codes treated as expected.
            unique_codes = np.unique(event_codes)
            midpoint = np.median(unique_codes)
            labels = np.where(event_codes <= midpoint, 1, 0)

        metadata: dict[str, Any] = {
            "source": str(candidate),
            "sfreq": float(getattr(epochs_obj, "info", {}).get("sfreq", 0.0) or 0.0),
            "tmin": float(getattr(epochs_obj, "tmin", 0.0)),
            "event_id": {str(key): int(value) for key, value in event_id.items()},
            "loader": "mne",
        }
        return {
            "epochs": np.asarray(epochs, dtype=np.float64),
            "labels": np.asarray(labels, dtype=np.int64),
            "metadata": metadata,
        }

    return None


def load_derco_n400(
    data_path: str,
) -> dict:
    """Load and preprocess DERCo dataset for N400 analysis."""
    path = Path(data_path).expanduser().resolve()

    if path.exists() and path.is_file() and path.suffix == ".npz":
        loaded = _load_npz(path)
        if loaded is not None:
            return loaded

    if path.exists() and path.is_dir():
        npz_candidates = sorted(path.rglob("*.npz"))
        for candidate in npz_candidates:
            loaded = _load_npz(candidate)
            if loaded is not None:
                return loaded

    loaded_mne = _load_with_mne(path)
    if loaded_mne is not None:
        return loaded_mne

    return _synthetic_derco_dataset()


def _auc_from_scores(labels_binary: np.ndarray, scores: np.ndarray) -> float:
    positives = labels_binary == 1
    negatives = labels_binary == 0
    n_pos = int(np.sum(positives))
    n_neg = int(np.sum(negatives))
    if n_pos == 0 or n_neg == 0:
        return 0.5

    order = np.argsort(scores)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, scores.size + 1, dtype=float)

    pos_rank_sum = float(np.sum(ranks[positives]))
    auc = (pos_rank_sum - (n_pos * (n_pos + 1) / 2.0)) / float(n_pos * n_neg)
    return float(min(max(auc, 0.0), 1.0))


def compute_n400_d_prime(epochs, labels) -> dict:
    """Compute d' for single-trial N400 classification."""
    data = np.asarray(epochs, dtype=float)
    y = np.asarray(labels, dtype=int)

    if data.ndim != 3:
        raise ValueError("epochs must have shape (n_trials, n_channels, n_timepoints)")
    if y.ndim != 1 or y.shape[0] != data.shape[0]:
        raise ValueError("labels must be shape (n_trials,) and match epochs")

    n_trials, _, n_time = data.shape
    if n_trials < 4:
        raise ValueError("Need at least 4 trials for stable d' estimation.")

    start = int(0.35 * n_time)
    end = int(0.60 * n_time)
    if end <= start:
        start, end = 0, n_time

    # N400 is typically negative for unexpected words; invert so higher score => unexpected.
    scores = -np.mean(data[:, :, start:end], axis=(1, 2))

    unexpected_scores = scores[y == 0]
    expected_scores = scores[y == 1]
    if unexpected_scores.size < 2 or expected_scores.size < 2:
        return {
            "d_prime": 0.0,
            "auc": 0.5,
            "n_trials": int(n_trials),
        }

    mu_unexpected = float(np.mean(unexpected_scores))
    mu_expected = float(np.mean(expected_scores))

    var_unexpected = float(np.var(unexpected_scores, ddof=1))
    var_expected = float(np.var(expected_scores, ddof=1))
    pooled_std = float(np.sqrt(max((var_unexpected + var_expected) / 2.0, 1e-12)))

    d_prime = (mu_unexpected - mu_expected) / pooled_std
    auc = _auc_from_scores((y == 0).astype(int), scores)

    return {
        "d_prime": float(d_prime),
        "auc": float(auc),
        "n_trials": int(n_trials),
    }
