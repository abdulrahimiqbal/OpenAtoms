# OpenAtoms

**The Deterministic Execution Layer for Physical AI**

OpenAtoms is an open-source deterministic compiler for physical workflows. It converts probabilistic AI intent into validated, executable DAGs before commands ever reach real-world hardware.

## Why OpenAtoms?

Large language models are probabilistic. Pipettes, bioreactors, heaters, and robots are not.

That mismatch is where physical hallucinations become dangerous: invalid volumes, unsafe temperatures, impossible transitions, and brittle step ordering can all escape a pure text interface.

OpenAtoms acts as a physics linter and compilation layer between AI agents and instruments:
- It models matter, containers, and constraints as typed primitives.
- It validates action graphs (`dry_run`) before execution.
- It exports a universal deterministic protocol JSON.
- It compiles the same validated graph to heterogeneous targets (for example, Opentrons and IoT systems).

This lets teams build once, validate once, and execute safely across labs, factories, and autonomous hardware stacks.

## Quick Start

### 1) Define Matter and Containers

```python
from openatoms.core import Matter, Container, Phase

source = Container("Vessel_A", max_volume_ml=1000, max_temp_c=120)
dest = Container("Vessel_B", max_volume_ml=250, max_temp_c=120)
source.contents.append(Matter("H2O", Phase.LIQUID, 500, 500))
```

### 2) Build and Validate a DAG

```python
from openatoms.actions import Move, Transform
from openatoms.dag import ProtocolGraph

graph = ProtocolGraph("Transfer_and_Heat")
graph.add_step(Move(source, dest, 50))
graph.add_step(Transform(dest, "temperature_c", 90.0, 60))

ok = graph.dry_run()  # Physics lint + deterministic validation
```

### 3) Compile to Opentrons

```python
from openatoms.adapters import OpentronsAdapter

if ok:
    payload = graph.export_json()
    opentrons_script = OpentronsAdapter(payload).compile()
    print(opentrons_script)
```

### Run the Included Example

```bash
python examples/basic_compilation.py
```

## Repository Layout

```text
OpenAtoms/
  openatoms/
  examples/
  README.md
  requirements.txt
```

## Vision

OpenAtoms is building the software substrate for reliable physical AI: deterministic planning, static safety checks, and hardware-agnostic execution.
