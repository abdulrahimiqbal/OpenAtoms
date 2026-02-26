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

## Simulation Registry

The Research Suite registry now tracks three science nodes:

| Node | Domain | Goal | Platform |
| --- | --- | --- | --- |
| Node A: Bio-Kinetic | Biotech | Pipetting accuracy, deck collisions, molarity tracking | `opentrons.simulate` |
| Node B: Thermo-Kinetic | Chemistry | `dT/dt` lag, exothermic safety, Gibbs free-energy evolution | Cantera |
| Node C: Contact-Kinetic | Robotics | Torque, friction, vial-shattering thresholds | MuJoCo (planned) |

Current registry implementation lives in `openatoms/sim/registry/`:
- `kinetics_sim.py`: Cantera-backed `VirtualReactor` for hydrogen-oxygen combustion.
- `opentrons_sim.py`: Opentrons protocol simulation wrapper with structured deck-boundary errors.

All registry simulations emit a `StateObservation` JSON payload.

## 🔬 The Science Research Protocol
OpenAtoms is not a calculator; it is a **Proprioceptive Bridge** for AI Agents.

* **Nervous System for AI:** Agents currently lack "physical common sense." OpenAtoms simulations provide an observation loop where constraints (collisions, heat-up times) act as a nervous system.
* **Stochastic Robustness:** We inject "Real World Noise" into simulations. If a protocol fails with ±2% sensor variance, it's not research-ready.
* **Sim-to-Real Trust:** A $100k robot should never be an LLM's "first try." OpenAtoms enforces a Mandatory Digital Twin Pass (MDTP) to ensure hardware safety.
* **Deterministic Provenance:** Every experiment generates a machine-readable DAG, solving the Reproducibility Crisis by recording every physical variable in the "State Snapshot."

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

# Science-mode dry run (Cantera/Opentrons hooks)
graph.dry_run(mode="science")
```

Run examples:

```bash
python examples/hello_atoms.py
python examples/openai_tool_calling.py
python examples/research_loop.py
```

## Repository Layout

```text
openatoms/   # Core compiler, actions, adapters, and tool schemas
openatoms/sim/registry/  # Science simulation registry (Cantera + Opentrons)
examples/    # Minimal and agent-loop integration examples
tests/       # Validation test suite
```
