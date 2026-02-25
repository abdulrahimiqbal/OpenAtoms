# OpenAtoms: Code for the Physical World

**Mission: Atoms for the Real World.**

OpenAtoms is the deterministic execution layer that bridges AI reasoning and physical systems.

## The Problem

LLMs live in a world of bits; reality lives in a world of atoms.

That gap is where physical hallucinations become expensive and dangerous. A plausible text plan can still violate volume limits, thermal constraints, ordering rules, and machine capabilities.

## The Solution

OpenAtoms provides a hardware-agnostic, deterministic compiler that translates AI intent into physical execution:

- Model physical entities with typed primitives (`Matter`, `Container`, `Action`).
- Compile agent plans into deterministic protocol graphs (`ProtocolGraph`).
- Validate constraints before execution with `dry_run()`.
- Export a universal machine-readable protocol JSON for downstream hardware runtimes.

## The Tooling

OpenAtoms includes:

- Built-in physics validation for volume, temperature, and operation safety checks.
- Machine-readable agent feedback via structured `PhysicsError` payloads for self-correction loops.
- Universal hardware adapters that compile one validated protocol to multiple execution targets.

## Quick Start

```python
from openatoms.core import Matter, Container, Phase
from openatoms.actions import Move
from openatoms.dag import ProtocolGraph

a = Container("A", max_volume_ml=100, max_temp_c=100)
b = Container("B", max_volume_ml=100, max_temp_c=100)
a.contents.append(Matter("H2O", Phase.LIQUID, mass_g=10, volume_ml=10))

graph = ProtocolGraph("Hello_Atoms")
graph.add_step(Move(a, b, 5))
graph.dry_run()
print(graph.export_json())
```

Run examples:

```bash
python examples/hello_atoms.py
python examples/openai_tool_calling.py
```

## Repository Layout

```text
openatoms/   # Core compiler, actions, adapters, and tool schemas
examples/    # Minimal and agent-loop integration examples
tests/       # Validation test suite
```
