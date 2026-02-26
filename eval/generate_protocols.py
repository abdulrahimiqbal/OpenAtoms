from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProtocolRanges:
    source_volume_ul: tuple[int, int]
    transfer_ul: tuple[int, int]
    destination_start_ul: tuple[int, int]
    destination_capacity_ul: tuple[int, int]
    target_temp_c: tuple[int, int]
    max_temp_c: tuple[int, int]


@dataclass(frozen=True)
class SuiteSpec:
    name: str
    description: str
    ranges: ProtocolRanges
    default_violation_probability: float
    edge_biased_sampling: bool = False


@dataclass(frozen=True)
class GenerationBatch:
    protocols: list[dict[str, Any]]
    suite_name: str
    suite_description: str
    violation_probability: float
    injection_method: str


SUITES: dict[str, SuiteSpec] = {
    "realistic": SuiteSpec(
        name="realistic",
        description="Plausible protocol envelopes with low-rate injected violations.",
        ranges=ProtocolRanges(
            source_volume_ul=(80, 300),
            transfer_ul=(5, 120),
            destination_start_ul=(0, 120),
            destination_capacity_ul=(150, 320),
            target_temp_c=(20, 65),
            max_temp_c=(45, 85),
        ),
        default_violation_probability=0.1,
    ),
    "stress": SuiteSpec(
        name="stress",
        description="Edge-adjacent protocol envelopes with higher violation pressure.",
        ranges=ProtocolRanges(
            source_volume_ul=(1, 400),
            transfer_ul=(1, 400),
            destination_start_ul=(0, 350),
            destination_capacity_ul=(80, 400),
            target_temp_c=(-10, 220),
            max_temp_c=(20, 120),
        ),
        default_violation_probability=0.3,
    ),
    "fuzz": SuiteSpec(
        name="fuzz",
        description="Edge-biased generation for property-style fuzzing with deterministic seeds.",
        ranges=ProtocolRanges(
            source_volume_ul=(1, 500),
            transfer_ul=(1, 500),
            destination_start_ul=(0, 450),
            destination_capacity_ul=(50, 500),
            target_temp_c=(-20, 260),
            max_temp_c=(10, 140),
        ),
        default_violation_probability=0.2,
        edge_biased_sampling=True,
    ),
}

VIOLATION_TYPES = ("source_depletion", "destination_overflow", "thermal_limit")


def _draw_int(rng: random.Random, bounds: tuple[int, int], edge_biased: bool) -> int:
    low, high = bounds
    if not edge_biased:
        return rng.randint(low, high)
    if rng.random() < 0.60:
        middle = (low + high) // 2
        candidates = [low, min(low + 1, high), middle, max(high - 1, low), high]
        return candidates[rng.randrange(len(candidates))]
    return rng.randint(low, high)


def _build_valid_protocol(
    *,
    index: int,
    rng: random.Random,
    suite: SuiteSpec,
) -> dict[str, Any]:
    ranges = suite.ranges
    edge = suite.edge_biased_sampling

    source = max(_draw_int(rng, ranges.source_volume_ul, edge), 1)
    destination_capacity = max(_draw_int(rng, ranges.destination_capacity_ul, edge), 2)
    destination_start_upper = min(ranges.destination_start_ul[1], destination_capacity - 1)
    destination_start = _draw_int(
        rng,
        (ranges.destination_start_ul[0], max(destination_start_upper, ranges.destination_start_ul[0])),
        edge,
    )
    destination_start = min(destination_start, destination_capacity - 1)
    available_room = max(destination_capacity - destination_start, 1)

    transfer_upper = min(ranges.transfer_ul[1], source, available_room)
    transfer_lower = min(ranges.transfer_ul[0], transfer_upper)
    transfer = _draw_int(rng, (max(transfer_lower, 1), max(transfer_upper, 1)), edge)

    max_temp = _draw_int(rng, ranges.max_temp_c, edge)
    target_upper = min(ranges.target_temp_c[1], max_temp)
    target_lower = min(ranges.target_temp_c[0], target_upper)
    target_temp = _draw_int(rng, (target_lower, target_upper), edge)

    return {
        "protocol_id": f"{suite.name}-{index:05d}",
        "suite": suite.name,
        "source_volume_ul": source,
        "transfer_ul": transfer,
        "destination_start_ul": destination_start,
        "destination_capacity_ul": destination_capacity,
        "target_temp_c": target_temp,
        "max_temp_c": max_temp,
        "expected_violation": False,
        "injected_violation_type": None,
    }


def _inject_violation(protocol: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    mutated = dict(protocol)
    violation = VIOLATION_TYPES[rng.randrange(len(VIOLATION_TYPES))]

    if violation == "source_depletion":
        delta = rng.randint(1, max(1, mutated["source_volume_ul"] // 2))
        mutated["transfer_ul"] = mutated["source_volume_ul"] + delta
    elif violation == "destination_overflow":
        available = max(mutated["destination_capacity_ul"] - mutated["destination_start_ul"], 0)
        delta = rng.randint(1, max(1, mutated["destination_capacity_ul"] // 3))
        mutated["transfer_ul"] = available + delta
    else:
        delta = rng.randint(1, max(5, abs(mutated["max_temp_c"]) // 4))
        mutated["target_temp_c"] = mutated["max_temp_c"] + delta

    mutated["expected_violation"] = True
    mutated["injected_violation_type"] = violation
    return mutated


def generate_protocol_batch(
    *,
    seed: int,
    n: int,
    suite: str = "realistic",
    violation_probability: float | None = None,
) -> GenerationBatch:
    if suite not in SUITES:
        supported = ", ".join(sorted(SUITES))
        raise ValueError(f"Unknown suite '{suite}'. Supported suites: {supported}")
    suite_spec = SUITES[suite]
    injection_probability = (
        suite_spec.default_violation_probability if violation_probability is None else violation_probability
    )
    if not (0.0 <= injection_probability <= 1.0):
        raise ValueError("violation_probability must be within [0.0, 1.0].")

    rng = random.Random(seed)
    protocols: list[dict[str, Any]] = []
    for index in range(n):
        protocol = _build_valid_protocol(index=index, rng=rng, suite=suite_spec)
        if rng.random() < injection_probability:
            protocol = _inject_violation(protocol, rng)
        protocols.append(protocol)

    return GenerationBatch(
        protocols=protocols,
        suite_name=suite_spec.name,
        suite_description=suite_spec.description,
        violation_probability=round(injection_probability, 6),
        injection_method=(
            "Violations are injected independently per protocol with Bernoulli(p), then sampled "
            "uniformly from {source_depletion, destination_overflow, thermal_limit}."
        ),
    )


def generate_protocols(
    seed: int,
    n: int,
    suite: str = "realistic",
    violation_probability: float | None = None,
) -> list[dict[str, Any]]:
    """Backward-compatible list-returning API."""
    batch = generate_protocol_batch(
        seed=seed,
        n=n,
        suite=suite,
        violation_probability=violation_probability,
    )
    return batch.protocols


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic benchmark protocols.")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--suite", choices=sorted(SUITES.keys()), default="realistic")
    parser.add_argument("--violation-probability", type=float, default=None)
    args = parser.parse_args()
    batch = generate_protocol_batch(
        seed=args.seed,
        n=args.n,
        suite=args.suite,
        violation_probability=args.violation_probability,
    )
    print(
        json.dumps(
            {
                "injection_method": batch.injection_method,
                "n": args.n,
                "protocols": batch.protocols,
                "seed": args.seed,
                "suite": batch.suite_name,
                "suite_description": batch.suite_description,
                "violation_probability": batch.violation_probability,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
