"""OpenAtoms integration helpers for the BCI verification bottleneck example."""

from .bci_ir import BCIExperimentProtocol
from .bci_simulator import BCISimulator, SimulationResult

__all__ = ["BCIExperimentProtocol", "BCISimulator", "SimulationResult"]
