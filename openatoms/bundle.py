"""OpenAtoms Experiment Bundle (OEB) creation, verification, replay, and signing."""

from __future__ import annotations

import hashlib
import hmac
import importlib.metadata
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .dag import ProtocolGraph
from .ir import canonical_json, schema_version, validate_ir

BUNDLE_VERSION = "1.0"
BUNDLE_SPEC_NAME = "OpenAtoms Experiment Bundle"
DETERMINISTIC_TIMESTAMP = "2026-01-01T00:00:00Z"

OEB001_MISSING_FILE = "OEB001"
OEB002_HASH_MISMATCH = "OEB002"
OEB003_SCHEMA_INCOMPAT = "OEB003"
OEB004_SIGNATURE_INVALID = "OEB004"
OEB005_REPLAY_MISMATCH = "OEB005"
OEB006_BUNDLE_INVALID = "OEB006"

REQUIRED_FILES = (
    "manifest.json",
    "protocol.ir.json",
    "provenance.json",
    "environment/python.txt",
    "environment/platform.txt",
    "environment/dependencies.txt",
    "environment/pyproject.toml",
    "checks/validate.json",
    "checks/dry_run.json",
)

_SIMULATOR_NAMES = {"opentrons", "cantera", "mujoco"}

_SECRET_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|passwd|access[_-]?key|bearer)"
)
_SECRET_VALUE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,'\"}]+"),
]


class BundleError(RuntimeError):
    """Stable OpenAtoms Experiment Bundle error with machine-readable code."""

    def __init__(self, code: str, message: str, *, path: str | None = None):
        super().__init__(message)
        self.code = code
        self.path = path


@dataclass(frozen=True)
class BundleIssue:
    """A machine-readable verification/replay issue."""

    code: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"code": self.code, "message": self.message}
        if self.path is not None:
            payload["path"] = self.path
        return payload


@dataclass(frozen=True)
class BundleVerificationReport:
    """Verification report for one OEB."""

    ok: bool
    bundle_path: str
    bundle_version: str | None
    schema_version: str | None
    verified_files: int
    errors: tuple[BundleIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "bundle_path": self.bundle_path,
            "bundle_version": self.bundle_version,
            "schema_version": self.schema_version,
            "verified_files": self.verified_files,
            "errors": [error.to_dict() for error in self.errors],
        }


@dataclass(frozen=True)
class BundleReplayReport:
    """Replay report comparing regenerated checks to recorded checks."""

    ok: bool
    bundle_path: str
    strict: bool
    checks: Mapping[str, Any]
    errors: tuple[BundleIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "bundle_path": self.bundle_path,
            "strict": self.strict,
            "checks": dict(self.checks),
            "errors": [error.to_dict() for error in self.errors],
        }


def _utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _created_at(*, deterministic: bool) -> str:
    return DETERMINISTIC_TIMESTAMP if deterministic else _utc_now_rfc3339()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dumps(payload), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BundleError(OEB006_BUNDLE_INVALID, f"Expected JSON object in {path}.", path=str(path))
    return data


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _ensure_relative_path(path: Path) -> None:
    if path.is_absolute():
        raise BundleError(OEB006_BUNDLE_INVALID, "Bundle-relative paths must be relative.")


def _project_root() -> Path:
    return Path.cwd()


def _openatoms_version() -> str:
    try:
        return importlib.metadata.version("openatoms")
    except importlib.metadata.PackageNotFoundError:
        pyproject = _project_root() / "pyproject.toml"
        if pyproject.exists():
            text = pyproject.read_text(encoding="utf-8")
            match = re.search(r"(?m)^version\s*=\s*\"([^\"]+)\"", text)
            if match:
                return match.group(1)
        return "0+unknown"


def _git_sha() -> str | None:
    head = _project_root() / ".git" / "HEAD"
    if not head.exists():
        return None
    try:
        raw = head.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if raw.startswith("ref:"):
        ref = raw.split(" ", 1)[1].strip()
        ref_path = _project_root() / ".git" / ref
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8").strip() or None
        return None
    return raw or None


def _default_seeds(seeds: Mapping[str, int] | None) -> dict[str, int]:
    resolved = {
        "python_random": 0,
        "numpy": 0,
        "openatoms_internal": 0,
    }
    if seeds:
        for key, value in seeds.items():
            resolved[str(key)] = int(value)
    return dict(sorted(resolved.items(), key=lambda item: item[0]))


def _minimal_pyproject_projection() -> str:
    version = _openatoms_version()
    return (
        "[project]\n"
        'name = "openatoms"\n'
        f'version = "{version}"\n'
        'description = "Minimal reproducibility projection"\n'
    )


def _collect_dependencies_lines() -> list[str]:
    rows: set[str] = set()
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name") if dist.metadata else None
        if not name:
            continue
        rows.add(f"{name}=={dist.version}")
    return sorted(rows, key=lambda item: item.lower())


def _write_environment(root: Path) -> None:
    env_dir = root / "environment"
    env_dir.mkdir(parents=True, exist_ok=True)

    py_runtime = f"{platform.python_implementation()} {sys.version.split()[0]}\n"
    (env_dir / "python.txt").write_text(py_runtime, encoding="utf-8")

    platform_text = f"{platform.system()} {platform.release()} ({platform.machine()})\n"
    (env_dir / "platform.txt").write_text(platform_text, encoding="utf-8")

    dependencies = "\n".join(_collect_dependencies_lines()) + "\n"
    (env_dir / "dependencies.txt").write_text(dependencies, encoding="utf-8")

    project_pyproject = _project_root() / "pyproject.toml"
    if project_pyproject.exists():
        shutil.copy2(project_pyproject, env_dir / "pyproject.toml")
    else:
        (env_dir / "pyproject.toml").write_text(_minimal_pyproject_projection(), encoding="utf-8")

    lock_candidates = (
        "poetry.lock",
        "uv.lock",
        "Pipfile.lock",
        "pdm.lock",
        "requirements.lock",
        "conda-lock.yml",
    )
    for name in lock_candidates:
        source = _project_root() / name
        if source.exists() and source.is_file():
            target = env_dir / f"lockfile.{name}"
            shutil.copy2(source, target)


def _normalize_ir_payload(ir_payload: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(ir_payload, Mapping):
        payload = dict(ir_payload)
    elif isinstance(ir_payload, Path):
        payload = json.loads(ir_payload.read_text(encoding="utf-8"))
    else:
        candidate_path = Path(ir_payload)
        if candidate_path.exists():
            payload = json.loads(candidate_path.read_text(encoding="utf-8"))
        else:
            payload = json.loads(ir_payload)

    if not isinstance(payload, dict):
        raise BundleError(OEB006_BUNDLE_INVALID, "IR payload must decode to a JSON object.")
    return payload


def _redact_secret_text(raw: str) -> str:
    redacted = raw
    for pattern in _SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _redact_object(obj: Any) -> Any:
    if isinstance(obj, dict):
        redacted: dict[str, Any] = {}
        for key, value in obj.items():
            key_text = str(key)
            if _SECRET_KEY_PATTERN.search(key_text):
                redacted[key_text] = "[REDACTED]"
            else:
                redacted[key_text] = _redact_object(value)
        return redacted
    if isinstance(obj, list):
        return [_redact_object(item) for item in obj]
    if isinstance(obj, str):
        return _redact_secret_text(obj)
    return obj


def _write_agent_files(
    root: Path,
    *,
    tool_calls: Iterable[Mapping[str, Any] | str] | str | Path | None,
    prompts: Mapping[str, Any] | str | Path | None,
    model: Mapping[str, Any] | str | Path | None,
) -> None:
    agent_dir = root / "agent"

    if tool_calls is not None:
        agent_dir.mkdir(parents=True, exist_ok=True)
        output = agent_dir / "tool_calls.jsonl"

        lines: list[str] = []
        if isinstance(tool_calls, (str, Path)):
            candidate = Path(tool_calls)
            if candidate.exists():
                raw_lines = candidate.read_text(encoding="utf-8").splitlines()
            else:
                raw_lines = str(tool_calls).splitlines()
            for line in raw_lines:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    lines.append(_redact_secret_text(stripped))
                else:
                    lines.append(_json_dumps(_redact_object(parsed)))
        else:
            for item in tool_calls:
                if isinstance(item, str):
                    lines.append(_redact_secret_text(item))
                else:
                    lines.append(_json_dumps(_redact_object(dict(item))))

        output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _write_optional_json(value: Mapping[str, Any] | str | Path | None, filename: str) -> None:
        if value is None:
            return
        agent_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(value, Mapping):
            payload: Any = dict(value)
        elif isinstance(value, Path):
            payload = json.loads(value.read_text(encoding="utf-8"))
        else:
            candidate = Path(value)
            if candidate.exists():
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            else:
                payload = json.loads(value)
        _write_json(agent_dir / filename, _redact_object(payload))

    _write_optional_json(prompts, "prompts.json")
    _write_optional_json(model, "model.json")


def _copy_results(root: Path, results_paths: Sequence[str | Path] | None) -> None:
    if not results_paths:
        return

    results_dir = root / "results"
    data_dir = results_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[dict[str, Any]] = []

    for index, candidate in enumerate(results_paths, start=1):
        source = Path(candidate)
        if not source.exists():
            raise BundleError(
                OEB001_MISSING_FILE,
                f"Result path does not exist: {source}",
                path=str(source),
            )

        if source.is_file():
            target_name = f"{index:03d}_{source.name}"
            target = data_dir / target_name
            shutil.copy2(source, target)
            artifacts.append(
                {
                    "path": f"results/data/{target_name}",
                    "sha256": _sha256_file(target),
                    "semantic_type": "result_artifact",
                }
            )
            continue

        target_dir = data_dir / f"{index:03d}_{source.name}"
        shutil.copytree(source, target_dir)
        for path in sorted(target_dir.rglob("*")):
            if path.is_file():
                artifacts.append(
                    {
                        "path": _relative(path, root),
                        "sha256": _sha256_file(path),
                        "semantic_type": "result_artifact",
                    }
                )

    _write_json(results_dir / "artifacts.json", {"artifacts": artifacts})


def _ensure_bundle_root(path: Path) -> Path:
    if path.exists():
        if not path.is_dir():
            raise BundleError(
                OEB006_BUNDLE_INVALID, f"Output path exists and is not a directory: {path}"
            )
        if any(path.iterdir()):
            raise BundleError(
                OEB006_BUNDLE_INVALID,
                f"Output directory must be empty for bundle creation: {path}",
            )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_report(ir_payload: dict[str, Any]) -> dict[str, Any]:
    from .api import validate_protocol_ir

    try:
        validate_protocol_ir(ir_payload)
    except Exception as exc:
        code = getattr(exc, "code", OEB006_BUNDLE_INVALID)
        return {
            "status": "failed",
            "validator": "openatoms.api.validate_protocol_ir",
            "schema_version": schema_version(),
            "error": {"code": str(code), "message": str(exc)},
        }
    return {
        "status": "ok",
        "validator": "openatoms.api.validate_protocol_ir",
        "schema_version": schema_version(),
        "error": None,
    }


def _dry_run_report(ir_payload: dict[str, Any]) -> dict[str, Any]:
    try:
        validate_ir(ir_payload)
        step_ids: list[str] = []
        for expected, step in enumerate(ir_payload.get("steps", []), start=1):
            if step.get("step") != expected:
                raise ValueError("steps must be contiguous and start at 1")
            current_id = step.get("step_id")
            if not isinstance(current_id, str):
                raise ValueError("step_id must be a string")
            depends_on = step.get("depends_on", [])
            if not isinstance(depends_on, list):
                raise ValueError("depends_on must be a list")
            for dep in depends_on:
                if dep not in step_ids:
                    raise ValueError("depends_on references undefined predecessor")
            step_ids.append(current_id)
    except Exception as exc:
        return {
            "status": "failed",
            "mode": "deterministic_ir_gate",
            "scope": "heuristic",
            "error": {"code": OEB006_BUNDLE_INVALID, "message": str(exc)},
            "statement": (
                "Dry-run replay checks deterministic IR-level invariants only; "
                "it does not certify scientific validity."
            ),
        }

    return {
        "status": "ok",
        "mode": "deterministic_ir_gate",
        "scope": "heuristic",
        "error": None,
        "statement": (
            "Dry-run replay checks deterministic IR-level invariants only; "
            "it does not certify scientific validity."
        ),
    }


def _run_simulators(
    protocol: ProtocolGraph | None,
    simulators: Sequence[str],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    from .api import invoke_optional_simulator

    simulator_status: list[dict[str, Any]] = []
    simulator_reports: dict[str, dict[str, Any]] = {}

    for simulator in simulators:
        name = str(simulator)
        if name not in _SIMULATOR_NAMES:
            simulator_status.append(
                {"name": name, "status": "failed", "reason": "unknown simulator"}
            )
            simulator_reports[name] = {
                "status": "failed",
                "reason": "unknown simulator",
                "statement": "Simulator validity is outside OpenAtoms certification scope.",
            }
            continue

        if protocol is None:
            reason = "protocol object not supplied; simulator replay skipped"
            simulator_status.append({"name": name, "status": "skipped", "reason": reason})
            simulator_reports[name] = {
                "status": "skipped",
                "reason": reason,
                "statement": "Simulator validity is outside OpenAtoms certification scope.",
            }
            continue

        try:
            result = invoke_optional_simulator(protocol, simulator=name)  # type: ignore[arg-type]
            if result.status == "ok":
                simulator_status.append({"name": name, "status": "ran", "reason": None})
                simulator_reports[name] = {
                    "status": "ran",
                    "payload": dict(result.payload),
                    "statement": "Simulator output is heuristic unless independently validated.",
                }
            else:
                reason = result.reason or "optional dependency unavailable"
                simulator_status.append({"name": name, "status": "skipped", "reason": reason})
                simulator_reports[name] = {
                    "status": "skipped",
                    "reason": reason,
                    "payload": dict(result.payload),
                    "statement": "Simulator output is heuristic unless independently validated.",
                }
        except Exception as exc:
            simulator_status.append({"name": name, "status": "failed", "reason": str(exc)})
            simulator_reports[name] = {
                "status": "failed",
                "reason": str(exc),
                "statement": "Simulator output is heuristic unless independently validated.",
            }

    return simulator_status, simulator_reports


def _build_provenance(
    *,
    simulator_reports: Mapping[str, Mapping[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    agents = [
        {
            "id": "agent:openatoms",
            "name": "OpenAtoms",
            "type": "software-agent",
        },
        {
            "id": "agent:human",
            "name": "human-operator",
            "type": "human-agent",
        },
    ]

    entities = [
        {"id": "entity:protocol-ir", "path": "protocol.ir.json", "type": "protocol_ir"},
        {
            "id": "entity:validate-report",
            "path": "checks/validate.json",
            "type": "validation_report",
        },
        {
            "id": "entity:dry-run-report",
            "path": "checks/dry_run.json",
            "type": "dry_run_report",
        },
    ]

    activities = [
        {"id": "activity:protocol-generation", "type": "protocol_generation", "time": created_at},
        {"id": "activity:validation", "type": "validation", "time": created_at},
        {"id": "activity:dry-run", "type": "dry_run", "time": created_at},
    ]

    relations: list[dict[str, str]] = [
        {
            "type": "wasAssociatedWith",
            "activity": "activity:protocol-generation",
            "agent": "agent:human",
        },
        {
            "type": "wasAssociatedWith",
            "activity": "activity:protocol-generation",
            "agent": "agent:openatoms",
        },
        {
            "type": "generated",
            "activity": "activity:protocol-generation",
            "entity": "entity:protocol-ir",
        },
        {
            "type": "used",
            "activity": "activity:validation",
            "entity": "entity:protocol-ir",
        },
        {
            "type": "generated",
            "activity": "activity:validation",
            "entity": "entity:validate-report",
        },
        {
            "type": "used",
            "activity": "activity:dry-run",
            "entity": "entity:protocol-ir",
        },
        {
            "type": "generated",
            "activity": "activity:dry-run",
            "entity": "entity:dry-run-report",
        },
    ]

    for name in sorted(simulator_reports):
        activity_id = f"activity:simulator:{name}"
        entity_id = f"entity:simulator-report:{name}"
        activities.append(
            {"id": activity_id, "type": "simulator", "name": name, "time": created_at}
        )
        entities.append(
            {
                "id": entity_id,
                "type": "simulator_report",
                "path": f"checks/simulators/{name}/report.json",
            }
        )
        relations.append({"type": "used", "activity": activity_id, "entity": "entity:protocol-ir"})
        relations.append({"type": "generated", "activity": activity_id, "entity": entity_id})
        relations.append(
            {"type": "wasAssociatedWith", "activity": activity_id, "agent": "agent:openatoms"}
        )

    return {
        "agents": agents,
        "entities": entities,
        "activities": activities,
        "relations": relations,
    }


def _collect_file_hashes(root: Path) -> dict[str, str]:
    file_hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = _relative(path, root)
        if rel == "manifest.json":
            continue
        file_hashes[rel] = _sha256_file(path)
    return dict(sorted(file_hashes.items(), key=lambda item: item[0]))


def _manifest_signature_payload(manifest: Mapping[str, Any]) -> bytes:
    payload = dict(manifest)
    payload.pop("signature", None)
    return canonical_json(payload).encode("utf-8")


def _resolve_secret_key(secret: str | bytes | None, *, key_env: str) -> bytes:
    if secret is None:
        env_value = os.getenv(key_env)
        if env_value is None or not env_value:
            raise BundleError(
                OEB004_SIGNATURE_INVALID,
                f"Missing signing secret. Provide key or set environment variable {key_env}.",
            )
        return env_value.encode("utf-8")
    if isinstance(secret, str):
        return secret.encode("utf-8")
    return secret


def _write_zip(bundle_root: Path, zip_path: Path, *, deterministic: bool) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_name = bundle_root.name
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_root.rglob("*")):
            if not path.is_file():
                continue
            rel = _relative(path, bundle_root)
            arcname = f"{bundle_name}/{rel}"
            info = zipfile.ZipInfo(arcname)
            if deterministic:
                info.date_time = (1980, 1, 1, 0, 0, 0)
            else:
                now = datetime.now()
                info.date_time = (now.year, now.month, now.day, now.hour, now.minute, now.second)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


@contextmanager
def _bundle_root(path: str | Path):
    bundle_path = Path(path)
    if bundle_path.is_dir():
        yield bundle_path
        return

    if bundle_path.is_file() and bundle_path.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="openatoms-oeb-") as tmp:
            tmp_root = Path(tmp)
            with zipfile.ZipFile(bundle_path, mode="r") as archive:
                archive.extractall(tmp_root)

            entries = [item for item in tmp_root.iterdir() if item.name != "__MACOSX"]
            if (
                len(entries) == 1
                and entries[0].is_dir()
                and (entries[0] / "manifest.json").exists()
            ):
                yield entries[0]
                return
            yield tmp_root
            return

    raise BundleError(
        OEB001_MISSING_FILE,
        f"Bundle path must be a directory or .zip file: {bundle_path}",
        path=str(bundle_path),
    )


def _load_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise BundleError(OEB001_MISSING_FILE, "Missing manifest.json.", path="manifest.json")
    return _read_json(manifest_path)


def create_bundle(
    *,
    output_path: str | Path,
    protocol: ProtocolGraph | None = None,
    ir_payload: Mapping[str, Any] | str | Path | None = None,
    agent_tool_calls: Iterable[Mapping[str, Any] | str] | str | Path | None = None,
    agent_prompts: Mapping[str, Any] | str | Path | None = None,
    agent_model: Mapping[str, Any] | str | Path | None = None,
    results_paths: Sequence[str | Path] | None = None,
    simulators: Sequence[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    seeds: Mapping[str, int] | None = None,
    deterministic: bool = False,
    zip_output: bool = False,
) -> Path:
    """Create an OpenAtoms Experiment Bundle (OEB) directory or .zip wrapper."""
    if protocol is not None and ir_payload is not None:
        raise BundleError(
            OEB006_BUNDLE_INVALID,
            "Provide exactly one of protocol or ir_payload when creating a bundle.",
        )
    if protocol is None and ir_payload is None:
        raise BundleError(OEB006_BUNDLE_INVALID, "Either protocol or ir_payload is required.")

    output = Path(output_path)
    as_zip = zip_output or output.suffix.lower() == ".zip"

    with tempfile.TemporaryDirectory(prefix="openatoms-oeb-build-") as staging_tmp:
        if as_zip:
            bundle_root = Path(staging_tmp) / (output.stem or "oeb_bundle")
            _ensure_bundle_root(bundle_root)
        else:
            bundle_root = _ensure_bundle_root(output)

        created_at = _created_at(deterministic=deterministic)

        if protocol is not None:
            protocol.dry_run(mode="mock")
            payload = protocol.to_payload()
        else:
            payload = _normalize_ir_payload(ir_payload)  # type: ignore[arg-type]

        validate_result = _validate_report(payload)
        if validate_result["status"] != "ok":
            error = validate_result["error"]
            code = str(error.get("code")) if isinstance(error, dict) else OEB006_BUNDLE_INVALID
            message = (
                str(error.get("message")) if isinstance(error, dict) else "IR validation failed"
            )
            raise BundleError(code, message)

        protocol_ir = canonical_json(payload)
        protocol_path = bundle_root / "protocol.ir.json"
        protocol_path.write_text(protocol_ir, encoding="utf-8")

        checks_dir = bundle_root / "checks"
        checks_dir.mkdir(parents=True, exist_ok=True)

        dry_run_result = _dry_run_report(payload)
        _write_json(checks_dir / "validate.json", validate_result)
        _write_json(checks_dir / "dry_run.json", dry_run_result)

        simulator_names = list(simulators or [])
        simulator_status, simulator_reports = _run_simulators(protocol, simulator_names)
        for name, report in simulator_reports.items():
            _write_json(checks_dir / "simulators" / name / "report.json", report)

        _write_environment(bundle_root)

        _write_agent_files(
            bundle_root,
            tool_calls=agent_tool_calls,
            prompts=agent_prompts,
            model=agent_model,
        )
        _copy_results(bundle_root, results_paths)

        provenance_payload = _build_provenance(
            simulator_reports=simulator_reports,
            created_at=created_at,
        )
        _write_json(bundle_root / "provenance.json", provenance_payload)

        protocol_ir_hash = _sha256_bytes(protocol_path.read_bytes())
        file_hashes = _collect_file_hashes(bundle_root)

        manifest: dict[str, Any] = {
            "bundle_version": BUNDLE_VERSION,
            "created_at": created_at,
            "openatoms_version": _openatoms_version(),
            "openatoms_git_sha": _git_sha(),
            "schema_version": schema_version(),
            "protocol_ir_hash": protocol_ir_hash,
            "file_hashes": file_hashes,
            "seeds": _default_seeds(seeds),
            "simulator_status": simulator_status,
            "disclaimers": [
                (
                    "Heuristic and simulator checks are safety gates only; "
                    "they are not scientific certification."
                ),
                (
                    "Scientific validity depends on domain-specific "
                    "validation and calibrated instruments."
                ),
            ],
        }
        if metadata is not None:
            manifest["metadata"] = _redact_object(dict(metadata))

        _write_json(bundle_root / "manifest.json", manifest)

        if as_zip:
            _write_zip(bundle_root, output, deterministic=deterministic)
            return output

        return bundle_root


def _verify_required_files(root: Path) -> list[BundleIssue]:
    issues: list[BundleIssue] = []
    for rel in REQUIRED_FILES:
        relative_path = Path(rel)
        _ensure_relative_path(relative_path)
        if not (root / relative_path).exists():
            issues.append(BundleIssue(OEB001_MISSING_FILE, "Missing required file.", path=rel))
    return issues


def verify_signature(
    bundle_path: str | Path,
    *,
    key: str | bytes | None = None,
    key_env: str = "OPENATOMS_BUNDLE_SIGNING_KEY",
    raise_on_error: bool = False,
) -> BundleVerificationReport:
    """Verify bundle manifest signature when present."""
    issues: list[BundleIssue] = []

    with _bundle_root(bundle_path) as root:
        manifest = _load_manifest(root)
        signature = manifest.get("signature")
        if not isinstance(signature, dict):
            issues.append(
                BundleIssue(
                    OEB004_SIGNATURE_INVALID, "Manifest is not signed.", path="manifest.json"
                )
            )
            report = BundleVerificationReport(
                ok=False,
                bundle_path=str(bundle_path),
                bundle_version=str(manifest.get("bundle_version"))
                if manifest.get("bundle_version")
                else None,
                schema_version=str(manifest.get("schema_version"))
                if manifest.get("schema_version")
                else None,
                verified_files=0,
                errors=tuple(issues),
            )
            if raise_on_error:
                first = issues[0]
                raise BundleError(first.code, first.message, path=first.path)
            return report

        algorithm = signature.get("algorithm")
        if algorithm != "hmac-sha256":
            issues.append(
                BundleIssue(
                    OEB004_SIGNATURE_INVALID,
                    f"Unsupported signature algorithm: {algorithm}",
                    path="manifest.json",
                )
            )
        else:
            expected = signature.get("value")
            try:
                secret = _resolve_secret_key(key, key_env=key_env)
            except BundleError as exc:
                issues.append(BundleIssue(exc.code, str(exc), path="manifest.json"))
            else:
                computed = hmac.new(
                    secret, _manifest_signature_payload(manifest), hashlib.sha256
                ).hexdigest()
                if not isinstance(expected, str) or not hmac.compare_digest(computed, expected):
                    issues.append(
                        BundleIssue(
                            OEB004_SIGNATURE_INVALID,
                            "Manifest signature verification failed.",
                            path="manifest.json",
                        )
                    )
                else:
                    protocol_path = root / "protocol.ir.json"
                    if protocol_path.exists() and isinstance(manifest.get("protocol_ir_hash"), str):
                        protocol_hash = _sha256_file(protocol_path)
                        if protocol_hash != manifest.get("protocol_ir_hash"):
                            issues.append(
                                BundleIssue(
                                    OEB004_SIGNATURE_INVALID,
                                    "Signed manifest does not match protocol.ir.json content.",
                                    path="protocol.ir.json",
                                )
                            )

                    file_hashes = manifest.get("file_hashes")
                    if isinstance(file_hashes, dict):
                        for rel, expected_hash in sorted(
                            file_hashes.items(), key=lambda item: str(item[0])
                        ):
                            rel_text = str(rel)
                            candidate = root / rel_text
                            if not candidate.exists():
                                issues.append(
                                    BundleIssue(
                                        OEB004_SIGNATURE_INVALID,
                                        "Signed manifest references a missing file.",
                                        path=rel_text,
                                    )
                                )
                                continue
                            if not isinstance(expected_hash, str):
                                issues.append(
                                    BundleIssue(
                                        OEB004_SIGNATURE_INVALID,
                                        "Signed manifest includes a non-string file hash.",
                                        path=rel_text,
                                    )
                                )
                                continue
                            actual_hash = _sha256_file(candidate)
                            if actual_hash != expected_hash:
                                issues.append(
                                    BundleIssue(
                                        OEB004_SIGNATURE_INVALID,
                                        "Signed manifest does not match bundle file content.",
                                        path=rel_text,
                                    )
                                )

        report = BundleVerificationReport(
            ok=not issues,
            bundle_path=str(bundle_path),
            bundle_version=str(manifest.get("bundle_version"))
            if manifest.get("bundle_version")
            else None,
            schema_version=str(manifest.get("schema_version"))
            if manifest.get("schema_version")
            else None,
            verified_files=0,
            errors=tuple(issues),
        )
        if raise_on_error and issues:
            first = issues[0]
            raise BundleError(first.code, first.message, path=first.path)
        return report


def verify_bundle(
    bundle_path: str | Path,
    *,
    verify_manifest_signature: bool = True,
    key: str | bytes | None = None,
    key_env: str = "OPENATOMS_BUNDLE_SIGNING_KEY",
    raise_on_error: bool = False,
) -> BundleVerificationReport:
    """Verify OEB integrity, schema compatibility, hashes, and optional signature."""
    issues: list[BundleIssue] = []
    verified_files = 0

    with _bundle_root(bundle_path) as root:
        issues.extend(_verify_required_files(root))

        manifest: dict[str, Any] | None = None
        if not issues:
            try:
                manifest = _load_manifest(root)
            except BundleError as exc:
                issues.append(BundleIssue(exc.code, str(exc), path=exc.path))

        if manifest is not None:
            if manifest.get("bundle_version") != BUNDLE_VERSION:
                issues.append(
                    BundleIssue(
                        OEB003_SCHEMA_INCOMPAT,
                        f"Unsupported bundle_version: {manifest.get('bundle_version')}",
                        path="manifest.json",
                    )
                )
            if manifest.get("schema_version") != schema_version():
                issues.append(
                    BundleIssue(
                        OEB003_SCHEMA_INCOMPAT,
                        (
                            "IR schema version mismatch: "
                            f"bundle={manifest.get('schema_version')} runtime={schema_version()}"
                        ),
                        path="manifest.json",
                    )
                )

            protocol_path = root / "protocol.ir.json"
            if protocol_path.exists():
                protocol_hash = _sha256_file(protocol_path)
                if protocol_hash != manifest.get("protocol_ir_hash"):
                    issues.append(
                        BundleIssue(
                            OEB002_HASH_MISMATCH,
                            "protocol.ir.json hash mismatch.",
                            path="protocol.ir.json",
                        )
                    )

            file_hashes = manifest.get("file_hashes")
            if not isinstance(file_hashes, dict):
                issues.append(
                    BundleIssue(
                        OEB006_BUNDLE_INVALID,
                        "manifest.file_hashes must be an object.",
                        path="manifest.json",
                    )
                )
            else:
                for rel, expected_hash in sorted(
                    file_hashes.items(), key=lambda item: str(item[0])
                ):
                    rel_text = str(rel)
                    candidate = root / rel_text
                    if not candidate.exists():
                        issues.append(
                            BundleIssue(
                                OEB001_MISSING_FILE,
                                "File declared in manifest.file_hashes is missing.",
                                path=rel_text,
                            )
                        )
                        continue
                    if not isinstance(expected_hash, str):
                        issues.append(
                            BundleIssue(
                                OEB006_BUNDLE_INVALID,
                                "Hash value in manifest.file_hashes must be a string.",
                                path=rel_text,
                            )
                        )
                        continue
                    actual_hash = _sha256_file(candidate)
                    verified_files += 1
                    if actual_hash != expected_hash:
                        issues.append(
                            BundleIssue(
                                OEB002_HASH_MISMATCH,
                                "File hash mismatch.",
                                path=rel_text,
                            )
                        )

            if verify_manifest_signature and isinstance(manifest.get("signature"), dict):
                signature_report = verify_signature(
                    root,
                    key=key,
                    key_env=key_env,
                    raise_on_error=False,
                )
                issues.extend(signature_report.errors)

        report = BundleVerificationReport(
            ok=not issues,
            bundle_path=str(bundle_path),
            bundle_version=(
                str(manifest.get("bundle_version"))
                if manifest and manifest.get("bundle_version")
                else None
            ),
            schema_version=(
                str(manifest.get("schema_version"))
                if manifest and manifest.get("schema_version")
                else None
            ),
            verified_files=verified_files,
            errors=tuple(issues),
        )

        if raise_on_error and issues:
            first = issues[0]
            raise BundleError(first.code, first.message, path=first.path)

        return report


def _compare_reports(recorded: Any, replayed: Any) -> bool:
    return _json_dumps(recorded) == _json_dumps(replayed)


def _write_replay_checks(output_root: Path, checks: Mapping[str, Any]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "validate.json", checks["validate"])
    _write_json(output_root / "dry_run.json", checks["dry_run"])
    simulators = checks.get("simulators", {})
    if isinstance(simulators, Mapping):
        for name, report in simulators.items():
            _write_json(output_root / "simulators" / str(name) / "report.json", report)


def replay_bundle(
    bundle_path: str | Path,
    *,
    protocol: ProtocolGraph | None = None,
    simulators: Sequence[str] | None = None,
    strict: bool = False,
    output_path: str | Path | None = None,
    raise_on_error: bool = False,
) -> BundleReplayReport:
    """Replay deterministic checks from bundle inputs and compare with recorded reports."""
    errors: list[BundleIssue] = []

    verification = verify_bundle(bundle_path, verify_manifest_signature=False, raise_on_error=False)
    if not verification.ok:
        errors.extend(verification.errors)

    with _bundle_root(bundle_path) as root:
        payload = _read_json(root / "protocol.ir.json")

        replay_validate = _validate_report(payload)
        replay_dry_run = _dry_run_report(payload)

        recorded_validate = _read_json(root / "checks" / "validate.json")
        recorded_dry_run = _read_json(root / "checks" / "dry_run.json")

        replay_simulator_names: list[str]
        if simulators is not None:
            replay_simulator_names = [str(item) for item in simulators]
        else:
            manifest = _load_manifest(root)
            entries = manifest.get("simulator_status", [])
            replay_simulator_names = [
                str(item.get("name"))
                for item in entries
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            ]

        _, replay_sim_reports = _run_simulators(protocol, replay_simulator_names)

        if not _compare_reports(recorded_validate, replay_validate):
            errors.append(
                BundleIssue(
                    OEB005_REPLAY_MISMATCH,
                    "Replay mismatch for checks/validate.json.",
                    path="checks/validate.json",
                )
            )

        if not _compare_reports(recorded_dry_run, replay_dry_run):
            errors.append(
                BundleIssue(
                    OEB005_REPLAY_MISMATCH,
                    "Replay mismatch for checks/dry_run.json.",
                    path="checks/dry_run.json",
                )
            )

        for name, replay_report in replay_sim_reports.items():
            recorded_path = root / "checks" / "simulators" / name / "report.json"
            if not recorded_path.exists():
                errors.append(
                    BundleIssue(
                        OEB001_MISSING_FILE,
                        "Missing recorded simulator report.",
                        path=f"checks/simulators/{name}/report.json",
                    )
                )
                continue
            recorded_report = _read_json(recorded_path)
            if not _compare_reports(recorded_report, replay_report):
                errors.append(
                    BundleIssue(
                        OEB005_REPLAY_MISMATCH,
                        f"Replay mismatch for simulator {name} report.",
                        path=f"checks/simulators/{name}/report.json",
                    )
                )

        replay_checks = {
            "validate": replay_validate,
            "dry_run": replay_dry_run,
            "simulators": replay_sim_reports,
        }
        if output_path is not None:
            _write_replay_checks(Path(output_path), replay_checks)

        mismatch_errors = [issue for issue in errors if issue.code == OEB005_REPLAY_MISMATCH]
        ok = not errors
        if not strict and errors and all(issue.code != OEB005_REPLAY_MISMATCH for issue in errors):
            ok = False
        if not strict and mismatch_errors:
            ok = False

        report = BundleReplayReport(
            ok=ok,
            bundle_path=str(bundle_path),
            strict=strict,
            checks=replay_checks,
            errors=tuple(errors),
        )

        if raise_on_error and errors:
            first = errors[0]
            raise BundleError(first.code, first.message, path=first.path)

        return report


def sign_bundle(
    bundle_path: str | Path,
    *,
    key: str | bytes | None = None,
    key_env: str = "OPENATOMS_BUNDLE_SIGNING_KEY",
    key_id: str | None = None,
    deterministic: bool = False,
) -> dict[str, Any]:
    """Sign a bundle manifest using HMAC-SHA256."""
    path = Path(bundle_path)
    secret = _resolve_secret_key(key, key_env=key_env)
    resolved_key_id = key_id or os.getenv("OPENATOMS_BUNDLE_SIGNING_KEY_ID", "default")

    if path.is_file() and path.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="openatoms-oeb-sign-") as tmp:
            tmp_root = Path(tmp)
            with zipfile.ZipFile(path, mode="r") as archive:
                archive.extractall(tmp_root)

            entries = [item for item in tmp_root.iterdir() if item.name != "__MACOSX"]
            if (
                len(entries) == 1
                and entries[0].is_dir()
                and (entries[0] / "manifest.json").exists()
            ):
                extracted_root = entries[0]
            else:
                extracted_root = tmp_root

            signature = sign_bundle(
                extracted_root,
                key=secret,
                key_env=key_env,
                key_id=resolved_key_id,
                deterministic=deterministic,
            )

            if extracted_root == tmp_root:
                bundle_root = tmp_root
            else:
                bundle_root = extracted_root
            _write_zip(bundle_root, path, deterministic=deterministic)
            return signature

    with _bundle_root(path) as root:
        manifest = _load_manifest(root)
        signature_payload = _manifest_signature_payload(manifest)
        digest = hmac.new(secret, signature_payload, hashlib.sha256).hexdigest()
        signature = {
            "algorithm": "hmac-sha256",
            "key_id": resolved_key_id,
            "signed_at": _created_at(deterministic=deterministic),
            "value": digest,
        }
        manifest["signature"] = signature
        _write_json(root / "manifest.json", manifest)
        return signature


__all__ = [
    "BUNDLE_SPEC_NAME",
    "BUNDLE_VERSION",
    "BundleError",
    "BundleIssue",
    "BundleReplayReport",
    "BundleVerificationReport",
    "OEB001_MISSING_FILE",
    "OEB002_HASH_MISMATCH",
    "OEB003_SCHEMA_INCOMPAT",
    "OEB004_SIGNATURE_INVALID",
    "OEB005_REPLAY_MISMATCH",
    "OEB006_BUNDLE_INVALID",
    "create_bundle",
    "replay_bundle",
    "sign_bundle",
    "verify_bundle",
    "verify_signature",
]
