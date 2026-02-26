from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProtocolRanges:
    source_volume_ul: tuple[int, int] = (50, 300)
    transfer_ul: tuple[int, int] = (5, 350)
    destination_start_ul: tuple[int, int] = (0, 220)
    destination_capacity_ul: tuple[int, int] = (150, 300)
    target_temp_c: tuple[int, int] = (20, 180)
    max_temp_c: tuple[int, int] = (60, 120)


def generate_protocols(seed: int, n: int, ranges: ProtocolRanges | None = None) -> list[dict[str, Any]]:
    """Generate deterministic protocol candidates with a controlled mix of valid/invalid cases."""
    ranges = ranges or ProtocolRanges()
    rng = random.Random(seed)
    protocols: list[dict[str, Any]] = []

    for index in range(n):
        source = rng.randint(*ranges.source_volume_ul)
        transfer = rng.randint(*ranges.transfer_ul)
        destination_start = rng.randint(*ranges.destination_start_ul)
        destination_capacity = rng.randint(*ranges.destination_capacity_ul)
        target_temp = rng.randint(*ranges.target_temp_c)
        max_temp = rng.randint(*ranges.max_temp_c)

        mode = index % 4
        if mode == 0:
            # Force source depletion violation.
            transfer = source + rng.randint(1, 80)
        elif mode == 1:
            # Force destination overflow violation.
            destination_start = max(destination_capacity - rng.randint(0, 5), 0)
            transfer = max(transfer, rng.randint(20, 120))
        elif mode == 2:
            # Force thermal violation.
            target_temp = max_temp + rng.randint(5, 80)
        else:
            # Keep valid by construction.
            destination_start = min(destination_start, max(destination_capacity - 5, 0))
            transfer = min(transfer, source, max(destination_capacity - destination_start, 1))
            target_temp = min(target_temp, max_temp)

        protocols.append(
            {
                "protocol_id": f"protocol-{index:05d}",
                "source_volume_ul": source,
                "transfer_ul": transfer,
                "destination_start_ul": destination_start,
                "destination_capacity_ul": destination_capacity,
                "target_temp_c": target_temp,
                "max_temp_c": max_temp,
            }
        )

    return protocols


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic benchmark protocols.")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(generate_protocols(seed=args.seed, n=args.n), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
