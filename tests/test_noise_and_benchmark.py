from pathlib import Path

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.eval.benchmark import ProtocolBenchmark, run_and_save
from openatoms.eval.mock_llm import MockLLM
from openatoms.sim.noise import SensorNoise
from openatoms.sim.types import SimulationParams
from openatoms.units import Q_


def test_sensor_noise_injection_and_robustness() -> None:
    noise = SensorNoise()
    params = SimulationParams(
        pipette_cv=0.02,
        thermocouple_offset_c=0.0,
        pressure_scale_fraction=0.0025,
    )
    perturbed = noise.inject(params, noise_model="gaussian", seed=7)
    assert perturbed.seed == 7

    a = Container(id="a", label="A", max_volume=Q_(500, "microliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
    b = Container(id="b", label="B", max_volume=Q_(500, "microliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
    a.contents.append(Matter(name="water", phase=Phase.LIQUID, mass=Q_(300, "milligram"), volume=Q_(300, "microliter")))
    graph = ProtocolGraph("noise")
    graph.add_step(Move(a, b, Q_(100, "microliter")))

    report = noise.robustness_sweep(graph, n_trials=15, noise_level=0.01)
    assert report.n_trials == 15
    assert 0.0 <= report.pass_rate <= 1.0


def test_benchmark_mock_pipeline_writes_outputs(tmp_path: Path) -> None:
    output_json = tmp_path / "benchmark.json"
    output_md = tmp_path / "report.md"

    baseline, enhanced, comparison = run_and_save(
        llm_client=MockLLM(seed=11),
        model="mock-llm",
        n_protocols=10,
        max_correction_rounds=3,
        output_json=output_json,
        output_markdown=output_md,
    )

    assert baseline.total == 10
    assert enhanced.total == 10
    assert output_json.exists()
    assert output_md.exists()
    assert comparison.enhanced_violation_rate <= comparison.baseline_violation_rate
