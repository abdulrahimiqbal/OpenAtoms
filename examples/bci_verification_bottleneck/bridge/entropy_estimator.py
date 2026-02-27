"""Character-level entropy estimation using Anthropic, with Groq fallback."""

from __future__ import annotations

import hashlib
import json
import os
import random
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

CACHE_PATH = Path(__file__).resolve().parents[1] / "cache" / "entropy_cache.json"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, sort_keys=True, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def _cache_key(model: str, context: str, candidate_chars: list[str]) -> str:
    force_local = os.getenv("OPENATOMS_BCI_FORCE_LOCAL_LM", "").lower() in {"1", "true", "yes"}
    digest = hashlib.sha256(context.encode("utf-8")).hexdigest()
    chars_key = "".join(sorted(candidate_chars))
    mode = "local" if force_local else "api"
    return f"v2::{mode}::{model}::{digest}::{chars_key}"


def _extract_first_candidate_char(text: str, candidate_chars: set[str]) -> str | None:
    for char in text:
        c = char.upper()
        if c in candidate_chars:
            return c
    return None


def _prompt_for_next_char(context: str) -> str:
    return (
        "Continue the text naturally. Return at least one character and no explanation.\n"
        f"TEXT:\n{context}"
    )


def _sample_with_anthropic(model: str, context: str) -> str:
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    from anthropic import Anthropic  # Imported lazily to keep dependency optional at runtime.

    client = Anthropic(api_key=anthropic_key)
    response = client.messages.create(
        model=model,
        max_tokens=8,
        temperature=1.0,
        system="You are sampling next-character continuations for entropy measurement.",
        messages=[{"role": "user", "content": _prompt_for_next_char(context)}],
    )

    parts = []
    for block in response.content:
        text = getattr(block, "text", "")
        if text:
            parts.append(text)
    return "".join(parts)


def _sample_with_groq(model: str, context: str) -> str:
    key = os.getenv("GROQ_API_KEY") or os.getenv("OPENATOMS_GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")

    payload = {
        "model": DEFAULT_GROQ_MODEL if model.startswith("claude-") else model,
        "temperature": 1.0,
        "max_tokens": 8,
        "messages": [
            {
                "role": "system",
                "content": "You are sampling next-character continuations for entropy measurement.",
            },
            {"role": "user", "content": _prompt_for_next_char(context)},
        ],
    }
    request = urllib.request.Request(
        url="https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Groq request failed: {exc}") from exc

    data = json.loads(raw)
    choices = data.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    return str(message.get("content", ""))


def _local_fallback_sample(context: str, candidate_chars: list[str], rng: random.Random) -> str:
    # Deterministic local fallback with a peaked distribution to emulate a strong LM prior.
    filtered = [ch for ch in context.upper() if ch in candidate_chars]
    if not filtered:
        return rng.choice(candidate_chars)

    counts = {ch: 1 for ch in candidate_chars}
    for ch in filtered:
        counts[ch] += 1

    mode_char = max(counts, key=lambda key: counts[key])
    if rng.random() < 0.85:
        return mode_char
    return rng.choice(candidate_chars)


def estimate_character_entropy(
    context: str,
    candidate_chars: list[str],
    *,
    model: str = "claude-sonnet-4-6",
    n_samples: int = 200,
) -> dict:
    """Estimate character-level entropy via API sampling (cached)."""
    if n_samples <= 0:
        raise ValueError("n_samples must be > 0")

    cache = _load_cache()
    key = _cache_key(model, context, candidate_chars)
    if key in cache:
        cached = dict(cache[key])
        cached["from_cache"] = True
        return cached

    chars = [ch.upper() for ch in candidate_chars]
    char_set = set(chars)
    counts = {ch: 0 for ch in chars}
    rng = random.Random(42 + len(context))
    force_local = os.getenv("OPENATOMS_BCI_FORCE_LOCAL_LM", "").lower() in {"1", "true", "yes"}

    provider_used = "anthropic"
    valid_samples = 0
    max_attempts = max(n_samples * 5, 20)

    for _ in range(max_attempts):
        if valid_samples >= n_samples:
            break

        completion = ""
        if force_local:
            completion = _local_fallback_sample(context, chars, rng)
            provider_used = "local_fallback"
        else:
            try:
                completion = _sample_with_anthropic(model=model, context=context)
                provider_used = "anthropic"
            except Exception:
                try:
                    completion = _sample_with_groq(model=model, context=context)
                    provider_used = "groq"
                except Exception:
                    completion = _local_fallback_sample(context, chars, rng)
                    provider_used = "local_fallback"

        chosen = _extract_first_candidate_char(completion, char_set)
        if chosen is None:
            if provider_used == "local_fallback":
                chosen = _local_fallback_sample(context, chars, rng)
            else:
                continue

        counts[chosen] += 1
        valid_samples += 1

    if valid_samples == 0:
        raise RuntimeError("Failed to collect any valid samples for entropy estimation.")

    probabilities = {ch: counts[ch] / float(valid_samples) for ch in chars}
    probs = np.asarray(list(probabilities.values()), dtype=float)
    probs = np.clip(probs, 1e-12, 1.0)
    probs /= float(np.sum(probs))
    entropy_bits = float(-np.sum(probs * np.log2(probs)))

    result = {
        "entropy_bits": float(entropy_bits),
        "character_probabilities": {ch: float(probabilities[ch]) for ch in chars},
        "model": model,
        "n_samples": int(valid_samples),
        "context_length": int(len(context)),
        "provider": provider_used,
    }

    cache[key] = dict(result)
    _save_cache(cache)
    result["from_cache"] = False
    return result


def estimate_corpus_entropy(
    corpus_texts: list[str],
    *,
    model: str = "claude-sonnet-4-6",
    sample_positions: int = 50,
) -> dict:
    """Estimate average character entropy across a corpus."""
    if sample_positions <= 0:
        raise ValueError("sample_positions must be > 0")

    candidate_chars = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    rng = random.Random(123)

    available_contexts: list[str] = []
    for text in corpus_texts:
        cleaned = text.strip()
        if len(cleaned) < 3:
            continue
        max_positions = min(len(cleaned) - 1, 64)
        for _ in range(max_positions):
            idx = rng.randint(1, len(cleaned) - 1)
            available_contexts.append(cleaned[:idx])

    if not available_contexts:
        raise ValueError("No usable corpus contexts for entropy estimation.")

    rng.shuffle(available_contexts)
    selected = available_contexts[:sample_positions]

    entropies: list[float] = []
    providers: list[str] = []
    for context in selected:
        estimate = estimate_character_entropy(
            context,
            candidate_chars,
            model=model,
            n_samples=80,
        )
        entropies.append(float(estimate["entropy_bits"]))
        providers.append(str(estimate.get("provider", "unknown")))

    values = np.asarray(entropies, dtype=float)
    return {
        "mean_entropy_bits": float(np.mean(values)),
        "std_entropy_bits": float(np.std(values)),
        "model": model,
        "n_positions_sampled": int(values.size),
        "per_position_entropies": [float(value) for value in values.tolist()],
        "providers": providers,
    }
