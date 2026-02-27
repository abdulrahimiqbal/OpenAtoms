"""OpenAtoms IR extension for BCI experiment protocols."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BCIExperimentProtocol:
    """OpenAtoms IR node for a BCI experiment configuration."""

    paradigm: str  # "p300_speller" | "n400_verification"
    d_prime_hypothesis: float  # predicted signal quality
    lm_model: str  # LLM used for prior
    lm_entropy_bits: float  # measured entropy
    corpus_text: str  # text to spell
    n_repetitions: int
    flash_duration_ms: float
    fusion_method: str  # "bayesian" | "uniform"
    seed: int

    # filled after simulation
    result_accuracy: float | None = None
    result_itr_bpm: float | None = None
    result_crossover_d_prime: float | None = None
    check_type: str = "validated_simulation"
