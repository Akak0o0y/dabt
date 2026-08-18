# Agent Action Gate — Implementation Plan (Policy Brain)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second enforcement surface to the Dabt policy engine that evaluates MCP tool calls — both the request (may this act execute?) and the response (may this result be disclosed?) — returning the same four outcomes as the Data Retrieval Gate.

**Architecture:** A new `ActionEngine` reuses the existing detectors, classifier, redactor, and bilingual audit unchanged. Policy matching and decision semantics are lifted into a shared `rules.py` so both surfaces cannot drift. Tool semantics come from a validated per-server manifest rather than from name heuristics. Findings and obligations gain an element path so redaction rewrites individual argument and response values rather than spans in one document.

**Tech Stack:** Python 3.11, PyYAML, pytest, FastAPI, Uvicorn.

**Spec:** `docs/superpowers/specs/2026-08-18-agent-action-gate-design.md`

**Out of scope for this plan:** the reference MCP proxy (spec §8). It is a different runtime, it can only be integration-tested once these endpoints exist, and it is a demonstration harness rather than product code. It gets its own plan.

## Global Constraints

These apply to every task without restatement.

- Python 3.11. `dabt_core` performs **no network calls and no file I/O outside explicit map and manifest loading**.
- The engine is a **pure function**: identical input yields byte-identical output. Timestamps are injected, never read from the clock inside the engine.
- **Every** compliance map entry carries `confidence_level` (one of `verified` / `inferred` / `needs_verification`) and `requires_legal_review: true`. Validation runs at **load time** and fails hard.
- **Every** manifest entry carries `confidence_level` and `requires_legal_review: true`, validated at load time on the same terms.
- **Every** rule carries both `rationale_en` and `rationale_ar`. Arabic and English are both mandatory.
- `citation.quote` contains **verbatim source text only**. Paraphrase is a defect.
- A rule whose `confidence_level` is `needs_verification` **cannot** produce a terminal `DENY`; it degrades to `REVIEW`.
- **No leaf-level NCA ECC control ID may be asserted as verified.** Map to subdomain granularity and mark `needs_verification`.
- **No manifest entry may claim `confidence_level: verified`** until someone has read the target server's published tool schema and transcribed it. The CranL manifest in this plan ships `needs_verification` throughout.
- **No mapping is presented as authoritative** in any API response. The legal-review disclaimer appears in every audit record, in both languages.
- TDD throughout: write the failing test, watch it fail, write minimal code, watch it pass, commit.
- Baseline before starting: 103 pytest passing. `pnpm test` passes 21/22 with one pre-existing `python3`-spawn failure on Windows that is unrelated to this work and must not be "fixed".

## File Structure

| File | Responsibility |
|---|---|
| `dabt_python/dabt_core/rules.py` | NEW. Rule matching and decision semantics shared by both surfaces. |
| `dabt_python/dabt_core/manifest.py` | NEW. Manifest types and load-time validation. |
| `dabt_python/dabt_core/action.py` | NEW. `ActionEngine`, its request/result types, element scanning and redaction. |
| `dabt_python/dabt_core/engine.py` | MODIFY. Import from `rules.py`; inject `surface` into context. |
| `dabt_python/dabt_core/schema.py` | MODIFY. Parse the residency table. |
| `dabt_python/dabt_core/data/compliance_map.yaml` | MODIFY. `surface` key, residency table, three new rules. |
| `dabt_python/dabt_core/data/manifests/cranl.yaml` | NEW. CranL tool manifest. |
| `dabt_python/dabt_api/main.py` | MODIFY. Two action endpoints, fail-closed. |

---

### Task 1: Lift policy evaluation into a shared module

Both surfaces must match conditions and degrade `needs_verification` denials identically. Sharing one implementation makes that structural rather than conventional.

**Files:**
- Create: `dabt_python/dabt_core/rules.py`
- Modify: `dabt_python/dabt_core/engine.py`
- Test: `dabt_python/tests/test_rules_shared.py`

**Interfaces:**
- Produces: `rules.rule_matches(rule, context) -> bool`, `rules.evaluate_policy(compliance_map, context) -> PolicyDecision`, `rules.PolicyDecision(decision, rule, fired_rules)`.
- `engine.py` re-exports all three by importing them, so `from dabt_core.engine import rule_matches` and `from dabt_core.engine import PolicyDecision` keep working. `tests/test_rule_boundaries.py` and `tests/test_obligations.py` rely on those imports and must not be edited in this task.

- [ ] **Step 1: Write the failing test**

Create `dabt_python/tests/test_rules_shared.py`:

```python
from pathlib import Path

from dabt_core import rules
from dabt_core.loader import load_compliance_map
from dabt_core.schema import Decision

MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


def test_rules_module_exposes_shared_matcher_and_evaluator() -> None:
    assert callable(rules.rule_matches)
    assert callable(rules.evaluate_policy)


def test_engine_and_rules_expose_the_same_matcher() -> None:
    from dabt_core import engine

    assert engine.rule_matches is rules.rule_matches
    assert engine.PolicyDecision is rules.PolicyDecision


def test_evaluate_policy_returns_review_when_no_rule_matches() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    decision = rules.evaluate_policy(compliance_map, {"classification": "__nothing_matches__"})
    assert decision.decision == Decision.REVIEW
    assert decision.rule is None
    assert decision.fired_rules == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dabt_python && python -m pytest tests/test_rules_shared.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dabt_core.rules'`

- [ ] **Step 3: Create `rules.py` by moving the code verbatim**

Create `dabt_python/dabt_core/rules.py`:

```python
"""Policy matching and decision semantics shared by every enforcement surface.

Both the retrieval gate and the action gate evaluate the same compliance map.
They must agree on what a condition means and on how an unverified rule
degrades, so that logic lives here once rather than in each engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .schema import ComplianceMap, ConfidenceLevel, Decision, Rule


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    rule: Rule | None
    fired_rules: tuple[Rule, ...]


def rule_matches(rule: Rule, context: Mapping[str, object]) -> bool:
    """Match declared map conditions exactly; special category matching is set-aware."""
    for key, expected in rule.condition.items():
        if key == "contains_sensitive_category":
            categories = context.get("sensitive_categories", context.get("contains_sensitive_category", frozenset()))
            if isinstance(categories, str):
                categories = frozenset({categories})
            if expected not in categories:
                return False
            continue
        if context.get(key) != expected:
            return False
    return True


def evaluate_policy(compliance_map: ComplianceMap, context: Mapping[str, object]) -> PolicyDecision:
    """First matching rule by priority wins; an unverified rule may not terminally deny."""
    fired_rules = tuple(rule for rule in compliance_map.rules if rule_matches(rule, context))
    if not fired_rules:
        return PolicyDecision(Decision.REVIEW, None, ())
    winner = fired_rules[0]
    decision = winner.decision
    # Defence in depth: a directly constructed invalid in-memory map still cannot deny on unverified content.
    if decision == Decision.DENY and winner.confidence_level == ConfidenceLevel.NEEDS_VERIFICATION:
        decision = Decision.REVIEW
    return PolicyDecision(decision, winner, fired_rules)
```

- [ ] **Step 4: Delete the moved code from `engine.py` and import it instead**

In `dabt_python/dabt_core/engine.py`, delete the `PolicyDecision` dataclass, the `rule_matches` function, and the `_evaluate_policy` function. Change the import block so it reads:

```python
from .audit import AuditRecord, build_audit_record
from .classifier import ClassificationContext, ClassificationResult, classify_findings
from .detectors import DEFAULT_DETECTORS
from .detectors.base import Detector, Finding
from .obligations import RedactionObligation, resolve_obligations
from .redactor import apply_redactions
from .rules import PolicyDecision, evaluate_policy, rule_matches
from .schema import ComplianceMap, Decision, Rule
```

Note `ConfidenceLevel` is no longer needed in `engine.py`. Then change the single call site inside `PolicyEngine.evaluate` from:

```python
        policy = _evaluate_policy(self._map, context)
```

to:

```python
        policy = evaluate_policy(self._map, context)
```

`rule_matches` is imported but unused inside `engine.py` — that is deliberate, so existing tests importing it from `dabt_core.engine` keep working.

- [ ] **Step 5: Run the full suite to verify nothing shifted**

Run: `cd dabt_python && python -m pytest -q`
Expected: PASS, 106 tests (103 baseline + 3 new)

- [ ] **Step 6: Commit**

```bash
git add dabt_python/dabt_core/rules.py dabt_python/dabt_core/engine.py dabt_python/tests/test_rules_shared.py
git commit -m "Lift policy matching and decision semantics into a shared rules module

Both enforcement surfaces evaluate the same compliance map and must agree on
what a condition means and how an unverified rule degrades. Sharing one
implementation makes that structural rather than conventional. Pure move;
engine.py re-exports so existing imports are unaffected."
```

---

### Task 2: Manifest types and validation

A manifest is a claim about someone else's software. It gets the same load-time strictness as a claim about a regulation.

**Files:**
- Create: `dabt_python/dabt_core/manifest.py`
- Test: `dabt_python/tests/test_manifest.py`

**Interfaces:**
- Produces: `ManifestError`, `ParameterSpec(name, role, maskable)`, `ReturnFieldSpec(name, role, maskable, declared_sensitive, inspect_content, collection)`, `ToolSpec(name, operation, resource_type, persists_data, confidence_level, requires_legal_review, parameters, returns)`, `ToolManifest(version, server_id, tools)` with methods `tool(name) -> ToolSpec | None` and `parameter(tool_name, param_name) -> ParameterSpec | None`, and `validate_manifest_payload(raw) -> ToolManifest`.
- Consumes: `ConfidenceLevel` from `schema.py`.

- [ ] **Step 1: Write the failing test**

Create `dabt_python/tests/test_manifest.py`:

```python
import pytest

from dabt_core.manifest import ManifestError, validate_manifest_payload


def base_tool() -> dict:
    return {
        "operation": "create",
        "resource_type": "database",
        "persists_data": True,
        "confidence_level": "needs_verification",
        "requires_legal_review": True,
        "parameters": {
            "region": {"role": "deployment_region", "maskable": False},
        },
        "returns": {
            "connection_string": {
                "role": "credential",
                "declared_sensitive": True,
                "maskable": True,
            }
        },
    }


def payload_with(tool: dict) -> dict:
    return {"version": "0.1", "server": {"id": "cranl"}, "tools": {"create_database": tool}}


def test_valid_manifest_is_accepted() -> None:
    manifest = validate_manifest_payload(payload_with(base_tool()))
    assert manifest.server_id == "cranl"
    spec = manifest.tool("create_database")
    assert spec is not None
    assert spec.operation == "create"
    assert spec.persists_data is True
    assert manifest.parameter("create_database", "region").role == "deployment_region"


def test_unknown_tool_returns_none() -> None:
    manifest = validate_manifest_payload(payload_with(base_tool()))
    assert manifest.tool("no_such_tool") is None


def test_tool_requires_confidence_level() -> None:
    tool = base_tool()
    tool.pop("confidence_level")
    with pytest.raises(ManifestError, match="create_database.*confidence_level"):
        validate_manifest_payload(payload_with(tool))


def test_tool_requires_legal_review_true() -> None:
    tool = base_tool()
    tool["requires_legal_review"] = False
    with pytest.raises(ManifestError, match="create_database.*requires_legal_review"):
        validate_manifest_payload(payload_with(tool))


def test_unknown_request_role_is_rejected() -> None:
    tool = base_tool()
    tool["parameters"]["region"]["role"] = "not_a_real_role"
    with pytest.raises(ManifestError, match="region.*role"):
        validate_manifest_payload(payload_with(tool))


def test_unknown_response_role_is_rejected() -> None:
    tool = base_tool()
    tool["returns"]["connection_string"]["role"] = "deployment_region"
    with pytest.raises(ManifestError, match="connection_string.*role"):
        validate_manifest_payload(payload_with(tool))


def test_unknown_operation_is_rejected() -> None:
    tool = base_tool()
    tool["operation"] = "teleport"
    with pytest.raises(ManifestError, match="create_database.*operation"):
        validate_manifest_payload(payload_with(tool))


def test_declared_sensitive_defaults_to_false() -> None:
    tool = base_tool()
    tool["returns"]["connection_string"].pop("declared_sensitive")
    manifest = validate_manifest_payload(payload_with(tool))
    field = manifest.tool("create_database").returns[0]
    assert field.declared_sensitive is False
    assert field.inspect_content is False
    assert field.collection is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dabt_python && python -m pytest tests/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dabt_core.manifest'`

- [ ] **Step 3: Write the implementation**

Create `dabt_python/dabt_core/manifest.py`:

```python
"""Strict, immutable types for a tool manifest.

A manifest states what a third party's tool does: which operation it performs,
which parameter carries a deployment region, which response field carries a
credential. That is a claim about software Dabt does not control, so it is
validated at load time on the same terms as a claim about a regulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .schema import ConfidenceLevel


class ManifestError(ValueError):
    """Raised when a tool manifest cannot meet Dabt's integrity contract."""


OPERATIONS = frozenset({"create", "read", "update", "delete", "execute"})
REQUEST_ROLES = frozenset(
    {
        "deployment_region",
        "opaque_payload",
        "resource_name",
        "resource_reference",
        "credential_reference",
    }
)
RESPONSE_ROLES = frozenset({"credential", "opaque_payload", "resource_metadata"})


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    role: str
    maskable: bool


@dataclass(frozen=True)
class ReturnFieldSpec:
    name: str
    role: str
    maskable: bool
    declared_sensitive: bool = False
    inspect_content: bool = False
    collection: bool = False


@dataclass(frozen=True)
class ToolSpec:
    name: str
    operation: str
    resource_type: str
    persists_data: bool
    confidence_level: ConfidenceLevel
    requires_legal_review: bool
    parameters: tuple[ParameterSpec, ...] = ()
    returns: tuple[ReturnFieldSpec, ...] = ()

    def parameter(self, name: str) -> ParameterSpec | None:
        for item in self.parameters:
            if item.name == name:
                return item
        return None

    def return_field(self, name: str) -> ReturnFieldSpec | None:
        for item in self.returns:
            if item.name == name:
                return item
        return None

    @property
    def declares_sensitive_response(self) -> bool:
        return any(item.declared_sensitive for item in self.returns)


@dataclass(frozen=True)
class ToolManifest:
    version: str
    server_id: str
    tools: tuple[ToolSpec, ...]

    def tool(self, name: str) -> ToolSpec | None:
        for item in self.tools:
            if item.name == name:
                return item
        return None

    def parameter(self, tool_name: str, parameter_name: str) -> ParameterSpec | None:
        spec = self.tool(tool_name)
        return spec.parameter(parameter_name) if spec else None


def _require(mapping: Mapping[str, Any], key: str, label: str) -> Any:
    if key not in mapping:
        raise ManifestError(f"{label}: missing required field '{key}'")
    return mapping[key]


def _non_empty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label}: must be a non-empty string")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ManifestError(f"{label}: must be a boolean")
    return value


def _legal_review(value: Any, label: str) -> bool:
    if value is not True:
        raise ManifestError(f"{label}: must be true")
    return True


def _confidence(value: Any, label: str) -> ConfidenceLevel:
    try:
        return ConfidenceLevel(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ConfidenceLevel)
        raise ManifestError(f"{label}: must be one of {allowed}") from exc


def _parse_parameter(name: str, raw: Any, label: str) -> ParameterSpec:
    if not isinstance(raw, Mapping):
        raise ManifestError(f"{label}: must be an object")
    role = _non_empty(_require(raw, "role", label), f"{label}.role")
    if role not in REQUEST_ROLES:
        allowed = ", ".join(sorted(REQUEST_ROLES))
        raise ManifestError(f"{label}.role: must be one of {allowed}")
    return ParameterSpec(
        name=name,
        role=role,
        maskable=_boolean(_require(raw, "maskable", label), f"{label}.maskable"),
    )


def _parse_return_field(name: str, raw: Any, label: str) -> ReturnFieldSpec:
    if not isinstance(raw, Mapping):
        raise ManifestError(f"{label}: must be an object")
    role = _non_empty(_require(raw, "role", label), f"{label}.role")
    if role not in RESPONSE_ROLES:
        allowed = ", ".join(sorted(RESPONSE_ROLES))
        raise ManifestError(f"{label}.role: must be one of {allowed}")
    return ReturnFieldSpec(
        name=name,
        role=role,
        maskable=_boolean(_require(raw, "maskable", label), f"{label}.maskable"),
        declared_sensitive=_boolean(raw.get("declared_sensitive", False), f"{label}.declared_sensitive"),
        inspect_content=_boolean(raw.get("inspect_content", False), f"{label}.inspect_content"),
        collection=_boolean(raw.get("collection", False), f"{label}.collection"),
    )


def _parse_tool(name: str, raw: Any) -> ToolSpec:
    label = name
    if not isinstance(raw, Mapping):
        raise ManifestError(f"{label}: must be an object")

    operation = _non_empty(_require(raw, "operation", label), f"{label}.operation")
    if operation not in OPERATIONS:
        allowed = ", ".join(sorted(OPERATIONS))
        raise ManifestError(f"{label}.operation: must be one of {allowed}")

    parameters = tuple(
        _parse_parameter(param_name, param_raw, f"{label}.parameters.{param_name}")
        for param_name, param_raw in (raw.get("parameters") or {}).items()
    )
    returns = tuple(
        _parse_return_field(field_name, field_raw, f"{label}.returns.{field_name}")
        for field_name, field_raw in (raw.get("returns") or {}).items()
    )

    return ToolSpec(
        name=name,
        operation=operation,
        resource_type=_non_empty(_require(raw, "resource_type", label), f"{label}.resource_type"),
        persists_data=_boolean(_require(raw, "persists_data", label), f"{label}.persists_data"),
        confidence_level=_confidence(_require(raw, "confidence_level", label), f"{label}.confidence_level"),
        requires_legal_review=_legal_review(
            _require(raw, "requires_legal_review", label), f"{label}.requires_legal_review"
        ),
        parameters=parameters,
        returns=returns,
    )


def validate_manifest_payload(raw: Mapping[str, Any]) -> ToolManifest:
    """Validate an untrusted manifest payload and return an immutable ToolManifest."""
    if not isinstance(raw, Mapping):
        raise ManifestError("tool manifest: expected an object")
    version = _non_empty(_require(raw, "version", "tool manifest"), "tool manifest.version")
    server = _require(raw, "server", "tool manifest")
    if not isinstance(server, Mapping):
        raise ManifestError("tool manifest.server: must be an object")
    server_id = _non_empty(_require(server, "id", "tool manifest.server"), "tool manifest.server.id")

    raw_tools = _require(raw, "tools", "tool manifest")
    if not isinstance(raw_tools, Mapping) or not raw_tools:
        raise ManifestError("tool manifest.tools: must be a non-empty object")

    return ToolManifest(
        version=version,
        server_id=server_id,
        tools=tuple(_parse_tool(name, spec) for name, spec in raw_tools.items()),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dabt_python && python -m pytest tests/test_manifest.py -v`
Expected: PASS, 8 tests

- [ ] **Step 5: Commit**

```bash
git add dabt_python/dabt_core/manifest.py dabt_python/tests/test_manifest.py
git commit -m "Add tool manifest types with load-time validation

A manifest is a claim about a third party's software, so it carries
confidence_level and requires_legal_review and is validated as strictly as a
claim about a regulation. Unknown roles and operations are rejected at load
rather than silently ignored at evaluation."
```

---

### Task 3: Manifest loader and the CranL manifest

**Files:**
- Modify: `dabt_python/dabt_core/manifest.py`
- Create: `dabt_python/dabt_core/data/manifests/cranl.yaml`
- Test: `dabt_python/tests/test_manifest_content.py`

**Interfaces:**
- Consumes: `validate_manifest_payload` from Task 2.
- Produces: `manifest.load_manifest(path) -> ToolManifest`.

- [ ] **Step 1: Write the failing test**

Create `dabt_python/tests/test_manifest_content.py`:

```python
from pathlib import Path

from dabt_core.manifest import load_manifest
from dabt_core.schema import ConfidenceLevel

MANIFEST_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "manifests" / "cranl.yaml"


def test_cranl_manifest_loads() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    assert manifest.server_id == "cranl"
    assert len(manifest.tools) >= 4


def test_no_cranl_tool_claims_verified_confidence() -> None:
    # Nobody has transcribed CranL's published tool schema yet. Until that
    # happens the manifest is a reconstruction, and saying otherwise would be
    # the exact overreach this project exists to avoid.
    manifest = load_manifest(MANIFEST_PATH)
    for tool in manifest.tools:
        assert tool.confidence_level != ConfidenceLevel.VERIFIED, tool.name


def test_every_cranl_tool_requires_legal_review() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    for tool in manifest.tools:
        assert tool.requires_legal_review is True, tool.name


def test_create_database_declares_a_sensitive_response() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    tool = manifest.tool("create_database")
    assert tool is not None
    assert tool.declares_sensitive_response is True


def test_list_env_vars_is_an_inspected_collection() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    field = manifest.tool("list_env_vars").return_field("variables")
    assert field.inspect_content is True
    assert field.collection is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dabt_python && python -m pytest tests/test_manifest_content.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_manifest'`

- [ ] **Step 3: Add the loader**

Append to `dabt_python/dabt_core/manifest.py`:

```python
def load_manifest(path: "str | Path") -> ToolManifest:
    """Read and validate a manifest once, before any evaluation can occur."""
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload: Any = yaml.safe_load(handle)
    except OSError as exc:
        raise ManifestError(f"tool manifest: unable to read {path}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"tool manifest: invalid YAML in {path}") from exc
    return validate_manifest_payload(payload)
```

And add to the import block at the top of the same file:

```python
from pathlib import Path

import yaml
```

- [ ] **Step 4: Create the CranL manifest**

Create `dabt_python/dabt_core/data/manifests/cranl.yaml`:

```yaml
# CranL hosted PaaS MCP server.
#
# RECONSTRUCTED, NOT TRANSCRIBED. Landscape research establishes that CranL
# exposes 16 MCP tools covering app deployment, database creation, environment
# variables, and logs. It does not enumerate their names or signatures. The
# entries below are plausible reconstructions that fix the manifest's shape.
# Every entry is therefore needs_verification, which means every action against
# this server resolves to REVIEW until someone reads CranL's published tool
# schema and transcribes it. An inaccurate reconstruction fails safe.
version: "0.1.0-cranl-reconstructed"
server:
  id: cranl
  description: "CranL hosted PaaS MCP server"

tools:
  create_database:
    operation: create
    resource_type: database
    persists_data: true
    confidence_level: needs_verification
    requires_legal_review: true
    parameters:
      region: { role: deployment_region, maskable: false }
      name: { role: resource_name, maskable: false }
    returns:
      connection_string:
        role: credential
        declared_sensitive: true
        maskable: true

  set_env_var:
    operation: update
    resource_type: configuration
    persists_data: true
    confidence_level: needs_verification
    requires_legal_review: true
    parameters:
      key: { role: resource_name, maskable: false }
      value: { role: opaque_payload, maskable: true }

  get_logs:
    operation: read
    resource_type: log
    persists_data: false
    confidence_level: needs_verification
    requires_legal_review: true
    parameters:
      app_id: { role: resource_reference, maskable: false }
    returns:
      entries:
        role: opaque_payload
        inspect_content: true
        collection: true
        maskable: true

  list_env_vars:
    operation: read
    resource_type: configuration
    persists_data: false
    confidence_level: needs_verification
    requires_legal_review: true
    parameters:
      app_id: { role: resource_reference, maskable: false }
    returns:
      variables:
        role: opaque_payload
        inspect_content: true
        collection: true
        maskable: true

  delete_database:
    operation: delete
    resource_type: database
    persists_data: false
    confidence_level: needs_verification
    requires_legal_review: true
    parameters:
      name: { role: resource_name, maskable: false }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd dabt_python && python -m pytest tests/test_manifest_content.py -v`
Expected: PASS, 5 tests

- [ ] **Step 6: Commit**

```bash
git add dabt_python/dabt_core/manifest.py dabt_python/dabt_core/data/manifests/cranl.yaml dabt_python/tests/test_manifest_content.py
git commit -m "Add the manifest loader and a reconstructed CranL manifest

Every CranL entry is needs_verification because nobody has read CranL's
published tool schema yet. A test enforces that no entry may claim verified
until it is transcribed, so an inaccurate reconstruction fails safe rather than
silently authorising actions."
```

---

### Task 4: Inject `surface` into retrieval context and close the boundary-coverage gap

Adding a condition to an existing rule requires its own before/after proof. `rule_matches()` returns False for an absent key, so without the injection every genuinely Public document would fall through to `REVIEW`.

**Files:**
- Modify: `dabt_python/dabt_core/engine.py`
- Modify: `dabt_python/dabt_core/data/compliance_map.yaml`
- Modify: `dabt_python/tests/test_rule_boundaries.py`

**Interfaces:**
- Consumes: `evaluate_policy` from Task 1.
- Produces: the context key `surface`, whose value is `"retrieval"` from `PolicyEngine` and `"action"` from `ActionEngine` in Task 7.

- [ ] **Step 1: Add the boundary-coverage test that is currently missing**

Both existing boundary tests parametrize over the hand-maintained `_MATCHING_CONTEXTS` dictionary rather than over the compliance map, so a rule added to the map with no dictionary entry is silently untested while the suite stays green. Add to the end of `dabt_python/tests/test_rule_boundaries.py`:

```python
def test_every_map_rule_has_boundary_coverage() -> None:
    mapped = {rule.id for rule in load_compliance_map(MAP_PATH).rules}
    missing = sorted(mapped - set(_MATCHING_CONTEXTS))
    assert not missing, f"rules with no boundary context: {missing}"
```

- [ ] **Step 2: Run it to confirm it passes today**

Run: `cd dabt_python && python -m pytest tests/test_rule_boundaries.py -v`
Expected: PASS. All ten current rules have entries, so this establishes the gate before new rules arrive.

- [ ] **Step 3: Add `surface` to the retrieval allow rule**

In `dabt_python/dabt_core/data/compliance_map.yaml`, find the `NDMO-PUBLIC-ALLOW` rule and change its condition from:

```yaml
    condition:
      classification: Public
```

to:

```yaml
    condition:
      classification: Public
      surface: retrieval
```

- [ ] **Step 4: Run the suite and watch two tests fail for the right reasons**

Run: `cd dabt_python && python -m pytest -q`
Expected: FAIL. `test_public_document_allows` fails because the engine does not yet set `surface`, and `test_every_rule_has_a_firing_condition[NDMO-PUBLIC-ALLOW]` fails because its hand-built context lacks the key. Both failures are the point of this task.

- [ ] **Step 5: Inject the key in `engine.py`**

In `dabt_python/dabt_core/engine.py`, inside `PolicyEngine.evaluate`, find the context dictionary and add `surface` as its first entry:

```python
        context: dict[str, object] = {
            "surface": "retrieval",
            "classification": classification.level.value,
            "lawful_basis": request.lawful_basis,
            "event_type": request.event_type,
            "cross_border": request.cross_border,
            "agent_authorised": request.agent_authorised,
            "requires_minimisation": request.requires_minimisation,
            "contains_personal_data": any(finding.is_personal_data for finding in findings),
            "contains_sensitive_data": bool(sensitive_categories),
            "sensitive_categories": sensitive_categories,
        }
```

- [ ] **Step 6: Update the hand-built boundary context**

In `dabt_python/tests/test_rule_boundaries.py`, change:

```python
    "NDMO-PUBLIC-ALLOW": {"classification": "Public"},
```

to:

```python
    "NDMO-PUBLIC-ALLOW": {"classification": "Public", "surface": "retrieval"},
```

- [ ] **Step 7: Run the full suite**

Run: `cd dabt_python && python -m pytest -q`
Expected: PASS, 112 tests. `test_public_document_allows` passing unchanged is the before/after proof that retrieval behaviour did not shift.

- [ ] **Step 8: Commit**

```bash
git add dabt_python/dabt_core/engine.py dabt_python/dabt_core/data/compliance_map.yaml dabt_python/tests/test_rule_boundaries.py
git commit -m "Scope the retrieval allow rule to its surface and enforce boundary coverage

NDMO-PUBLIC-ALLOW fires on classification Public, and an action whose arguments
contain no Saudi identifiers also classifies Public, so without scoping it would
permit an action because there was no PII in the argument. The guard lives in
the map rather than in engine code so a reviewer reading compliance_map.yaml can
see it.

Also closes a gap in the boundary harness: both parametrized tests iterate a
hand-maintained dictionary rather than the map, so a new rule with no entry was
silently untested while the suite stayed green."
```

---

### Task 5: Residency table

**Files:**
- Modify: `dabt_python/dabt_core/schema.py`
- Modify: `dabt_python/dabt_core/data/compliance_map.yaml`
- Test: `dabt_python/tests/test_residency.py`

**Interfaces:**
- Produces: `schema.RegionSpec(id, provider, confidence_level, requires_legal_review)` and `ComplianceMap.residency: tuple[RegionSpec, ...]`, plus `ComplianceMap.region_in_kingdom(region_id) -> bool`.

- [ ] **Step 1: Write the failing test**

Create `dabt_python/tests/test_residency.py`:

```python
from pathlib import Path

from dabt_core.loader import load_compliance_map

MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


def test_map_exposes_in_kingdom_regions() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    assert compliance_map.residency, "residency table must not be empty"


def test_known_in_kingdom_region_is_recognised() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    assert compliance_map.region_in_kingdom("me-central-1") is True


def test_unrecognised_region_is_treated_as_outside_the_kingdom() -> None:
    # Conservative direction: an unknown region triggers the residency rule and
    # lands on REVIEW rather than passing unexamined.
    compliance_map = load_compliance_map(MAP_PATH)
    assert compliance_map.region_in_kingdom("eu-west-1") is False
    assert compliance_map.region_in_kingdom("__never_heard_of_it__") is False


def test_every_region_entry_requires_legal_review() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    for region in compliance_map.residency:
        assert region.requires_legal_review is True, region.id
        assert region.confidence_level != "verified", region.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dabt_python && python -m pytest tests/test_residency.py -v`
Expected: FAIL with `AttributeError: 'ComplianceMap' object has no attribute 'residency'`

- [ ] **Step 3: Extend the schema**

In `dabt_python/dabt_core/schema.py`, add this dataclass immediately after the existing `RedactionDirective` dataclass:

```python
@dataclass(frozen=True)
class RegionSpec:
    id: str
    provider: str
    confidence_level: ConfidenceLevel
    requires_legal_review: bool
```

Change the `ComplianceMap` dataclass to:

```python
@dataclass(frozen=True)
class ComplianceMap:
    version: str
    rules: tuple[Rule, ...]
    classification: ClassificationPolicy = ClassificationPolicy()
    residency: tuple[RegionSpec, ...] = ()

    def region_in_kingdom(self, region_id: str) -> bool:
        """Unrecognised regions are treated as outside the Kingdom, deliberately."""
        return any(region.id == region_id for region in self.residency)
```

Add this parser immediately before `validate_map_payload`:

```python
def _parse_residency(raw: Any) -> tuple[RegionSpec, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Mapping):
        raise SchemaError("residency: must be an object")
    entries = raw.get("in_kingdom_regions") or []
    if not isinstance(entries, list):
        raise SchemaError("residency.in_kingdom_regions: must be a list")
    parsed: list[RegionSpec] = []
    for index, item in enumerate(entries, start=1):
        label = f"residency.in_kingdom_regions[{index}]"
        if not isinstance(item, Mapping):
            raise SchemaError(f"{label}: must be an object")
        parsed.append(
            RegionSpec(
                id=_non_empty(_require(item, "id", label), f"{label}.id"),
                provider=_non_empty(_require(item, "provider", label), f"{label}.provider"),
                confidence_level=_confidence(
                    _require(item, "confidence_level", label), f"{label}.confidence_level"
                ),
                requires_legal_review=_legal_review(
                    _require(item, "requires_legal_review", label), f"{label}.requires_legal_review"
                ),
            )
        )
    return tuple(parsed)
```

Finally, in `validate_map_payload`, change the returned `ComplianceMap` to include the new field:

```python
    return ComplianceMap(
        version=version,
        rules=tuple(sorted(rules, key=lambda rule: rule.priority)),
        classification=_parse_classification(raw.get("classification")),
        residency=_parse_residency(raw.get("residency")),
    )
```

- [ ] **Step 4: Add the residency table to the map**

In `dabt_python/dabt_core/data/compliance_map.yaml`, insert this block immediately after the `sources:` block and before `classification:`:

```yaml
# Whether a provider's region identifier denotes infrastructure inside the
# Kingdom is a jurisdictional claim, not a fact about any vendor's API, so it
# lives here rather than in a tool manifest. Every entry is inferred at best:
# providers have changed region semantics before. A region absent from this
# table is treated as outside the Kingdom.
residency:
  in_kingdom_regions:
    - id: "me-central-1"
      provider: aws
      confidence_level: inferred
      requires_legal_review: true
    - id: "saudiarabia"
      provider: azure
      confidence_level: inferred
      requires_legal_review: true
    - id: "me-central2"
      provider: gcp
      confidence_level: inferred
      requires_legal_review: true
```

- [ ] **Step 5: Run the full suite**

Run: `cd dabt_python && python -m pytest -q`
Expected: PASS, 116 tests

- [ ] **Step 6: Commit**

```bash
git add dabt_python/dabt_core/schema.py dabt_python/dabt_core/data/compliance_map.yaml dabt_python/tests/test_residency.py
git commit -m "Add an inferred region residency table to the compliance map

Whether a region identifier denotes infrastructure inside the Kingdom is a
jurisdictional claim rather than a fact about a vendor's API, so it lives in the
map beside the other regulatory content. Every entry is inferred, and an
unrecognised region is treated as outside the Kingdom so the unknown case lands
on REVIEW rather than passing unexamined."
```

---

### Task 6: The three new rules

**Files:**
- Modify: `dabt_python/dabt_core/data/compliance_map.yaml`
- Modify: `dabt_python/tests/test_rule_boundaries.py`
- Test: `dabt_python/tests/test_action_rules.py`

**Interfaces:**
- Produces the condition keys consumed by Task 8: `surface`, `tool_manifested`, `tool_confidence`, `persists_data`, `deployment_region_in_kingdom`, `response_declared_credential`.

- [ ] **Step 1: Write the failing test**

Create `dabt_python/tests/test_action_rules.py`:

```python
from pathlib import Path

from dabt_core.loader import load_compliance_map
from dabt_core.rules import evaluate_policy
from dabt_core.schema import ConfidenceLevel, Decision

MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"


def clean_action_context() -> dict:
    return {
        "surface": "action",
        "tool_manifested": True,
        "tool_confidence": "verified",
        "contains_personal_data": False,
        "contains_sensitive_data": False,
        "response_declared_credential": False,
        "undeclared_response_fields": False,
        "leg": "request",
        "persists_data": False,
        "deployment_region_in_kingdom": True,
        "classification": "Public",
        "sensitive_categories": frozenset(),
    }


def test_manifested_action_with_no_findings_allows() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    decision = evaluate_policy(compliance_map, clean_action_context())
    assert decision.decision == Decision.ALLOW
    assert decision.rule.id == "ACTION-DEFAULT-ALLOW-NO-FINDING"


def test_public_retrieval_allow_does_not_fire_on_actions() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    decision = evaluate_policy(compliance_map, clean_action_context())
    assert "NDMO-PUBLIC-ALLOW" not in {rule.id for rule in decision.fired_rules}


def test_unverified_tool_does_not_reach_allow() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["tool_confidence"] = "needs_verification"
    decision = evaluate_policy(compliance_map, context)
    assert decision.decision == Decision.REVIEW


def test_unmanifested_tool_does_not_reach_allow() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["tool_manifested"] = False
    decision = evaluate_policy(compliance_map, context)
    assert decision.decision == Decision.REVIEW


def test_provisioning_outside_the_kingdom_reviews() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["persists_data"] = True
    context["deployment_region_in_kingdom"] = False
    decision = evaluate_policy(compliance_map, context)
    assert decision.decision == Decision.REVIEW
    assert decision.rule.id == "PDPL-ART29-2C-INFERRED-RESIDENCY"


def test_residency_rule_cannot_terminally_deny() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    rule = next(r for r in compliance_map.rules if r.id == "PDPL-ART29-2C-INFERRED-RESIDENCY")
    assert rule.confidence_level == ConfidenceLevel.NEEDS_VERIFICATION
    assert rule.decision != Decision.DENY


def test_declared_credential_does_not_block_the_request_leg() -> None:
    # The write must be able to proceed; only its disclosure is gated.
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["response_declared_credential"] = True
    assert evaluate_policy(compliance_map, context).decision == Decision.ALLOW


def test_declared_credential_response_reviews_on_the_response_leg() -> None:
    compliance_map = load_compliance_map(MAP_PATH)
    context = clean_action_context()
    context["leg"] = "response"
    context["response_declared_credential"] = True
    decision = evaluate_policy(compliance_map, context)
    assert decision.decision == Decision.REVIEW
    assert decision.rule.id == "NCA-ECC-CREDENTIAL-DISCLOSURE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dabt_python && python -m pytest tests/test_action_rules.py -v`
Expected: FAIL. Every test fails because none of the three rules exist yet, so `evaluate_policy` returns `REVIEW` with `rule is None`.

- [ ] **Step 3: Add the three rules to the map**

Append these three rules to the end of the `rules:` list in `dabt_python/dabt_core/data/compliance_map.yaml`. Priorities place both review rules ahead of the allow rule so a residency or credential concern wins over a clean-content finding.

```yaml
  - id: PDPL-ART29-2C-INFERRED-RESIDENCY
    priority: 300
    decision: REVIEW
    framework: PDPL
    citation:
      article: "Article 29(2)(c)"
      quote: "The Transfer or Disclosure shall be limited to the minimum amount of Personal Data needed."
      source_url: "https://sdaia.gov.sa/en/SDAIA/about/Documents/Personal%20Data%20English%20V2-23April2023-%20Reviewed-.pdf"
    condition:
      surface: action
      persists_data: true
      deployment_region_in_kingdom: false
    rationale_en: "This action would place a data store outside the Kingdom. Article 29 governs the transfer of Personal Data outside the Kingdom; provisioning transfers nothing yet, and Dabt cannot know whether Personal Data will later come to rest there. Extending Article 29 from transfer to provisioning is an explicit inference and is escalated to a qualified reviewer rather than decided automatically."
    rationale_ar: "سيؤدي هذا الإجراء إلى إنشاء مخزن بيانات خارج المملكة. تحكم المادة 29 نقل البيانات الشخصية خارج المملكة؛ ولا يترتب على مجرد التجهيز أي نقل حتى الآن، ولا يمكن لضبط أن يعرف ما إذا كانت بيانات شخصية ستُخزَّن هناك لاحقاً. ويُعد توسيع المادة 29 من النقل إلى التجهيز استنتاجاً صريحاً، ولذلك يُحال إلى مراجع مؤهل بدلاً من البت فيه آلياً."
    mapped_controls:
      - framework: NCA_ECC_2_2024
        control_id: "4-2"
        granularity: subdomain
        confidence_level: needs_verification
        requires_legal_review: true
    sama_maturity_contribution: 3
    confidence_level: needs_verification
    requires_legal_review: true

  - id: NCA-ECC-CREDENTIAL-DISCLOSURE
    priority: 310
    decision: REVIEW
    framework: NCA_ECC_2_2024
    citation:
      article: "Subdomain 2-2 — Identity and Access Management"
      quote: "To ensure protecting cybersecurity of logical access to information and technology assets, in order to prevent unauthorized access and restrict access to the extent necessary for accomplishment of the assigned tasks of the entity."
      source_url: "https://nca.gov.sa/en/regulatory-documents/controls-list/ecc/"
    condition:
      surface: action
      leg: response
      response_declared_credential: true
    rationale_en: "The tool manifest declares that this call returns a credential, which would place a live secret in an AI agent's context. The subdomain objective quoted here is drawn from a secondary listing rather than transcribed from the official NCA publication, so this mapping cannot claim verified status and the decision is escalated to a qualified reviewer."
    rationale_ar: "يُعلن بيان الأدوات أن هذا الاستدعاء يعيد بيانات اعتماد، مما يضع سراً فعّالاً في سياق وكيل ذكاء اصطناعي. والهدف المقتبس لهذا النطاق الفرعي مأخوذ من مصدر ثانوي وليس منقولاً من منشور الهيئة الوطنية للأمن السيبراني الرسمي، ولذلك لا يمكن اعتماد هذا التعيين موثقاً، ويُحال القرار إلى مراجع مؤهل."
    mapped_controls:
      - framework: NCA_ECC_2_2024
        control_id: "2-2"
        granularity: subdomain
        confidence_level: needs_verification
        requires_legal_review: true
    sama_maturity_contribution: 3
    confidence_level: needs_verification
    requires_legal_review: true

  - id: ACTION-DEFAULT-ALLOW-NO-FINDING
    priority: 950
    decision: ALLOW
    framework: NDMO
    citation:
      article: "Section 4.3 — Data Classification Levels"
      quote: "Data shall be classified as ‘Public’, if unauthorized access to or disclosure of such data or its content has no impact on: National Interest, or Organizations, or Individuals, or Environment."
      source_url: "https://sdaia.gov.sa/ndmo/Files/PoliciesEn.pdf"
    condition:
      surface: action
      tool_manifested: true
      tool_confidence: verified
      contains_personal_data: false
      contains_sensitive_data: false
      undeclared_response_fields: false
    rationale_en: "No mapped rule objected. The tool is declared in a validated manifest at verified confidence, no personal or sensitive data was detected in its arguments or declared response, and every field of the response was declared. This records the absence of a mapped objection. It is not a determination that the action is lawful, safe, or authorised, and it makes no claim about operational consequences such as data loss."
    rationale_ar: "لم تعترض أي قاعدة معيَّنة. فالأداة معلنة في بيان أدوات مُتحقَّق منه بمستوى ثقة موثق، ولم تُكتشف بيانات شخصية أو حساسة في وسائطها أو في استجابتها المعلنة، ولا تتضمن أي بيانات اعتماد. ويسجل هذا غياب الاعتراض المعيَّن، وهو ليس تقريراً بأن الإجراء مشروع أو آمن أو مصرح به، ولا يتضمن أي ادعاء بشأن العواقب التشغيلية مثل فقدان البيانات."
    mapped_controls:
      - framework: NCA_ECC_2_2024
        control_id: "2-12"
        granularity: subdomain
        confidence_level: needs_verification
        requires_legal_review: true
    sama_maturity_contribution: 5
    confidence_level: verified
    requires_legal_review: true
```

- [ ] **Step 4: Add boundary contexts for the three new rules**

The coverage test from Task 4 now fails until these exist. In `dabt_python/tests/test_rule_boundaries.py`, add these entries to `_MATCHING_CONTEXTS`:

```python
    "PDPL-ART29-2C-INFERRED-RESIDENCY": {
        "surface": "action",
        "persists_data": True,
        "deployment_region_in_kingdom": False,
    },
    "NCA-ECC-CREDENTIAL-DISCLOSURE": {
        "surface": "action",
        "leg": "response",
        "response_declared_credential": True,
    },
    "ACTION-DEFAULT-ALLOW-NO-FINDING": {
        "surface": "action",
        "tool_manifested": True,
        "tool_confidence": "verified",
        "contains_personal_data": False,
        "contains_sensitive_data": False,
        "undeclared_response_fields": False,
    },
```

- [ ] **Step 5: Run the full suite**

Run: `cd dabt_python && python -m pytest -q`
Expected: PASS, 126 tests

- [ ] **Step 6: Commit**

```bash
git add dabt_python/dabt_core/data/compliance_map.yaml dabt_python/tests/test_rule_boundaries.py dabt_python/tests/test_action_rules.py
git commit -m "Add the three action rules, including the explicit ALLOW path

Closing off the accidental NDMO-PUBLIC-ALLOW route without restoring a
legitimate one would have sent every action to REVIEW by omission, which would
hold a regulatorily clean destructive operation for human review on
blast-radius grounds. That is the overreach the scope boundary disclaims, so
the allow path is explicit, cites the classification it rests on, and states in
its rationale that it records the absence of an objection rather than a finding
of lawfulness.

Both review rules ship needs_verification: the residency rule extends Article 29
from transfer to provisioning, and the credential rule quotes an ECC subdomain
objective from a secondary listing. Neither can terminally deny."
```

---

### Task 7: Action request types and element scanning

**Files:**
- Create: `dabt_python/dabt_core/action.py`
- Test: `dabt_python/tests/test_action_scanning.py`

**Interfaces:**
- Consumes: `DEFAULT_DETECTORS` and `Finding` from `detectors`, `ToolManifest`/`ToolSpec` from Task 2.
- Produces: `ElementFinding(element, finding)`, `ActionRequest(server_id, tool, arguments, …)`, `ActionResultRequest(server_id, tool, result, …)`, and `scan_elements(values, detectors) -> tuple[ElementFinding, ...]` where `values` is a `Mapping[str, str]` of element path to text.

- [ ] **Step 1: Write the failing test**

Create `dabt_python/tests/test_action_scanning.py`:

```python
from dabt_core.action import ElementFinding, flatten_arguments, flatten_result, scan_elements
from dabt_core.detectors import DEFAULT_DETECTORS
from dabt_core.manifest import validate_manifest_payload


def manifest():
    return validate_manifest_payload(
        {
            "version": "0.1",
            "server": {"id": "cranl"},
            "tools": {
                "set_env_var": {
                    "operation": "update",
                    "resource_type": "configuration",
                    "persists_data": True,
                    "confidence_level": "verified",
                    "requires_legal_review": True,
                    "parameters": {
                        "key": {"role": "resource_name", "maskable": False},
                        "value": {"role": "opaque_payload", "maskable": True},
                    },
                },
                "list_env_vars": {
                    "operation": "read",
                    "resource_type": "configuration",
                    "persists_data": False,
                    "confidence_level": "verified",
                    "requires_legal_review": True,
                    "returns": {
                        "variables": {
                            "role": "opaque_payload",
                            "inspect_content": True,
                            "collection": True,
                            "maskable": True,
                        }
                    },
                },
            },
        }
    )


def test_flatten_arguments_produces_element_paths() -> None:
    spec = manifest().tool("set_env_var")
    values = flatten_arguments(spec, {"key": "DB_URL", "value": "id 1000000008"})
    assert values == {"arguments.key": "DB_URL", "arguments.value": "id 1000000008"}


def test_flatten_result_indexes_collection_elements() -> None:
    spec = manifest().tool("list_env_vars")
    values = flatten_result(spec, {"variables": ["clean", "id 1000000008", "also clean"]})
    assert values == {
        "result.variables[0]": "clean",
        "result.variables[1]": "id 1000000008",
        "result.variables[2]": "also clean",
    }


def test_flatten_result_skips_fields_not_marked_for_inspection() -> None:
    spec = manifest().tool("set_env_var")
    assert flatten_result(spec, {"anything": "id 1000000008"}) == {}


def test_scan_attaches_the_element_path_to_each_finding() -> None:
    found = scan_elements({"arguments.value": "id 1000000008"}, DEFAULT_DETECTORS)
    assert len(found) == 1
    assert isinstance(found[0], ElementFinding)
    assert found[0].element == "arguments.value"
    assert found[0].finding.type == "saudi_national_id"


def test_scan_offsets_are_relative_to_their_own_element() -> None:
    found = scan_elements({"result.variables[1]": "id 1000000008"}, DEFAULT_DETECTORS)
    finding = found[0].finding
    assert "id 1000000008"[finding.start : finding.end] == "1000000008"


def test_clean_elements_yield_no_findings() -> None:
    assert scan_elements({"arguments.key": "DB_URL"}, DEFAULT_DETECTORS) == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dabt_python && python -m pytest tests/test_action_scanning.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dabt_core.action'`

- [ ] **Step 3: Write the implementation**

Create `dabt_python/dabt_core/action.py`:

```python
"""The Agent Action Gate: policy evaluation for MCP tool calls.

The retrieval gate evaluates one document. An action gate evaluates a set of
named values — a tool call's arguments on the request leg, its declared response
fields on the response leg. Detection, classification, redaction and audit are
the retrieval gate's, unchanged; only the shape of the payload differs, so a
finding carries the element it came from and offsets relative to that element.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .detectors.base import Detector, Finding
from .manifest import ToolSpec


@dataclass(frozen=True)
class ElementFinding:
    """One detection result, tagged with the element of the call it came from."""

    element: str
    finding: Finding


@dataclass(frozen=True)
class ActionRequest:
    server_id: str
    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    agent_id: str = "demo-agent"
    purpose: str = "action"
    lawful_basis: str = "consent"
    sector: str = "development"
    agent_authorised: bool = True
    requires_minimisation: bool = True


@dataclass(frozen=True)
class ActionResultRequest:
    server_id: str
    tool: str
    result: Mapping[str, Any] = field(default_factory=dict)
    agent_id: str = "demo-agent"
    purpose: str = "action"
    lawful_basis: str = "consent"
    sector: str = "development"
    agent_authorised: bool = True
    requires_minimisation: bool = True


def flatten_arguments(spec: ToolSpec | None, arguments: Mapping[str, Any]) -> dict[str, str]:
    """Every argument value is inspectable; the manifest governs masking, not scanning."""
    flattened: dict[str, str] = {}
    for name, value in arguments.items():
        if value is None:
            continue
        flattened[f"arguments.{name}"] = value if isinstance(value, str) else str(value)
    return flattened


def flatten_result(spec: ToolSpec | None, result: Mapping[str, Any]) -> dict[str, str]:
    """Only manifest-declared response fields marked for inspection are scanned."""
    if spec is None:
        return {}
    flattened: dict[str, str] = {}
    for name, value in result.items():
        declared = spec.return_field(name)
        if declared is None or not declared.inspect_content or value is None:
            continue
        if declared.collection and isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                if item is None:
                    continue
                flattened[f"result.{name}[{index}]"] = item if isinstance(item, str) else str(item)
            continue
        flattened[f"result.{name}"] = value if isinstance(value, str) else str(value)
    return flattened


def has_undeclared_fields(spec: ToolSpec | None, result: Mapping[str, Any]) -> bool:
    """A response field the manifest never described cannot be reasoned about.

    Spec limitation 2: such a field is not inspected, so it must not be able to
    reach ALLOW. Without this the gate would permit a response purely because it
    failed to look at it.
    """
    if spec is None:
        return bool(result)
    return any(spec.return_field(name) is None for name in result)


def scan_elements(
    values: Mapping[str, str], detectors: Iterable[Detector]
) -> tuple[ElementFinding, ...]:
    """Run every detector over each element independently, preserving local offsets."""
    detectors = tuple(detectors)
    found: list[ElementFinding] = []
    for element in sorted(values):
        text = values[element]
        for detector in detectors:
            for finding in detector.detect(text):
                found.append(ElementFinding(element, finding))
    return tuple(
        sorted(found, key=lambda item: (item.element, item.finding.start, item.finding.end, item.finding.type))
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dabt_python && python -m pytest tests/test_action_scanning.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add dabt_python/dabt_core/action.py dabt_python/tests/test_action_scanning.py
git commit -m "Add action request types and per-element detection

A tool call is a set of named values rather than one document, so a finding
carries the element it came from and offsets relative to that element. Arguments
are always scanned; response fields are scanned only where the manifest declares
inspect_content, so undeclared response content is never silently examined nor
silently trusted."
```

---

### Task 8: Action context and policy evaluation

**Files:**
- Modify: `dabt_python/dabt_core/action.py`
- Test: `dabt_python/tests/test_action_engine.py`

**Interfaces:**
- Consumes: `evaluate_policy` and `PolicyDecision` from Task 1, `classify_findings` and `ClassificationContext` from `classifier`, `load_manifest`/`ToolManifest` from Tasks 2–3, and the condition keys from Task 6.
- Produces: `ActionEngine(compliance_map, manifests, detectors=DEFAULT_DETECTORS)` where `manifests` is a `Mapping[str, ToolManifest]` keyed by `server_id`, plus `ActionEngine.build_context(spec, request, findings, classification, leg, undeclared_response_fields) -> dict[str, object]`.

- [ ] **Step 1: Write the failing test**

Create `dabt_python/tests/test_action_engine.py`:

```python
from pathlib import Path

from dabt_core.action import ActionEngine, ActionRequest
from dabt_core.loader import load_compliance_map
from dabt_core.manifest import load_manifest
from dabt_core.schema import Decision

ROOT = Path(__file__).parents[1] / "dabt_core" / "data"
TIMESTAMP = "2026-08-18T09:00:00Z"


def engine() -> ActionEngine:
    manifest = load_manifest(ROOT / "manifests" / "cranl.yaml")
    return ActionEngine(load_compliance_map(ROOT / "compliance_map.yaml"), {manifest.server_id: manifest})


def test_unmanifested_tool_reviews() -> None:
    result = engine().evaluate(
        ActionRequest(server_id="cranl", tool="no_such_tool", arguments={"x": "y"}), TIMESTAMP
    )
    assert result.decision == Decision.REVIEW


def test_unknown_server_reviews() -> None:
    result = engine().evaluate(
        ActionRequest(server_id="not_a_server", tool="create_database", arguments={}), TIMESTAMP
    )
    assert result.decision == Decision.REVIEW


def test_reconstructed_cranl_manifest_cannot_reach_allow() -> None:
    # Every CranL entry is needs_verification, so nothing there may be permitted
    # until the real tool schema is transcribed.
    result = engine().evaluate(
        ActionRequest(server_id="cranl", tool="delete_database", arguments={"name": "production"}),
        TIMESTAMP,
    )
    assert result.decision == Decision.REVIEW


def test_personal_data_in_an_argument_fires_an_existing_pdpl_rule() -> None:
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl",
            tool="set_env_var",
            arguments={"key": "OWNER_ID", "value": "national id 1000000008"},
        ),
        TIMESTAMP,
    )
    assert result.classification == "Confidential"
    assert "PDPL-ART11-3-MINIMISATION" in {rule.id for rule in result.fired_rules}


def test_provisioning_outside_the_kingdom_reviews() -> None:
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl", tool="create_database", arguments={"region": "eu-west-1", "name": "customers"}
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.REVIEW
    assert result.decision_rule_id in {
        "PDPL-ART29-2C-INFERRED-RESIDENCY",
        "NCA-ECC-CREDENTIAL-DISCLOSURE",
    }


def test_action_evaluation_is_deterministic() -> None:
    request = ActionRequest(
        server_id="cranl", tool="set_env_var", arguments={"key": "K", "value": "id 1000000008"}
    )
    first = engine().evaluate(request, TIMESTAMP).to_dict()
    second = engine().evaluate(request, TIMESTAMP).to_dict()
    assert first == second


def test_audit_record_carries_both_languages() -> None:
    result = engine().evaluate(ActionRequest(server_id="cranl", tool="get_logs", arguments={}), TIMESTAMP)
    assert result.audit.legal_review_disclaimer_en
    assert "مراجعة" in result.audit.legal_review_disclaimer_ar
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dabt_python && python -m pytest tests/test_action_engine.py -v`
Expected: FAIL with `ImportError: cannot import name 'ActionEngine'`

- [ ] **Step 3: Write the implementation**

Append to `dabt_python/dabt_core/action.py`. Add these imports to the existing import block first:

```python
from .audit import AuditRecord, build_audit_record
from .classifier import ClassificationContext, ClassificationResult, classify_findings
from .detectors import DEFAULT_DETECTORS
from .rules import PolicyDecision, evaluate_policy
from .manifest import ToolManifest, ToolSpec
from .schema import ComplianceMap, Decision, Rule
```

Then append:

```python
@dataclass(frozen=True)
class ActionResult:
    decision: Decision
    decision_rule_id: str | None
    classification: str
    classification_evidence: dict[str, object]
    findings: tuple[ElementFinding, ...]
    fired_rules: tuple[Rule, ...]
    audit: AuditRecord
    manifest_version: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": str(self.decision),
            "decision_rule_id": self.decision_rule_id,
            "classification": self.classification,
            "classification_evidence": self.classification_evidence,
            "findings": [
                {
                    "element": item.element,
                    "type": item.finding.type,
                    "start": item.finding.start,
                    "end": item.finding.end,
                    "confidence_tier": item.finding.confidence_tier,
                    "confidence_level": item.finding.confidence_level,
                    "checksum_result": item.finding.checksum_result,
                    "sensitive_category": item.finding.sensitive_category,
                }
                for item in self.findings
            ],
            "fired_rules": [rule.id for rule in self.fired_rules],
            "audit": self.audit.to_dict(),
            "manifest_version": self.manifest_version,
        }


class ActionEngine:
    """Pure action evaluator: map, manifests and detectors are injected; no I/O here."""

    def __init__(
        self,
        compliance_map: ComplianceMap,
        manifests: Mapping[str, ToolManifest],
        detectors: Iterable[Detector] = DEFAULT_DETECTORS,
    ) -> None:
        self._map = compliance_map
        self._manifests = dict(manifests)
        self._detectors = tuple(detectors)

    def _spec(self, server_id: str, tool: str) -> tuple[ToolManifest | None, ToolSpec | None]:
        manifest = self._manifests.get(server_id)
        return manifest, (manifest.tool(tool) if manifest else None)

    def build_context(
        self,
        spec: ToolSpec | None,
        request: Any,
        findings: tuple[ElementFinding, ...],
        classification: str,
        leg: str,
        undeclared_response_fields: bool,
    ) -> dict[str, object]:
        sensitive_categories = frozenset(
            item.finding.sensitive_category for item in findings if item.finding.sensitive_category
        )
        region_in_kingdom = True
        if spec is not None:
            for parameter in spec.parameters:
                if parameter.role != "deployment_region":
                    continue
                value = getattr(request, "arguments", {}).get(parameter.name)
                if value is not None:
                    region_in_kingdom = self._map.region_in_kingdom(str(value))
        return {
            "surface": "action",
            "leg": leg,
            "undeclared_response_fields": undeclared_response_fields,
            "classification": classification,
            "lawful_basis": request.lawful_basis,
            "event_type": "action",
            "agent_authorised": request.agent_authorised,
            "requires_minimisation": request.requires_minimisation,
            "contains_personal_data": any(item.finding.is_personal_data for item in findings),
            "contains_sensitive_data": bool(sensitive_categories),
            "sensitive_categories": sensitive_categories,
            "tool_manifested": spec is not None,
            "tool_confidence": str(spec.confidence_level) if spec else "needs_verification",
            "operation": spec.operation if spec else None,
            "resource_type": spec.resource_type if spec else None,
            "persists_data": spec.persists_data if spec else False,
            "deployment_region_in_kingdom": region_in_kingdom,
            "response_declared_credential": spec.declares_sensitive_response if spec else False,
        }

    def _finish(
        self,
        request: Any,
        spec: ToolSpec | None,
        manifest: ToolManifest | None,
        findings: tuple[ElementFinding, ...],
        timestamp: str,
        leg: str,
        undeclared_response_fields: bool = False,
    ) -> tuple[ActionResult, PolicyDecision]:
        classification: ClassificationResult = classify_findings(
            [item.finding for item in findings],
            ClassificationContext(sector=request.sector),
            self._map.classification,
        )
        context = self.build_context(
            spec, request, findings, classification.level.value, leg, undeclared_response_fields
        )
        policy = evaluate_policy(self._map, context)
        audit = build_audit_record(request, classification.level.value, policy, (), timestamp)
        selected = classification.selected_mapping
        evidence: dict[str, object] = {
            "mapping_key": selected.key if selected else None,
            "confidence_level": str(classification.confidence_level),
            "requires_legal_review": selected.requires_legal_review if selected else True,
            "rationale_en": selected.rationale_en if selected else classification.rationale_en,
            "rationale_ar": selected.rationale_ar if selected else classification.rationale_ar,
            "citation": (
                {
                    "article": selected.citation.article,
                    "quote": selected.citation.quote,
                    "source_url": selected.citation.source_url,
                }
                if selected and selected.citation
                else None
            ),
        }
        result = ActionResult(
            decision=policy.decision,
            decision_rule_id=policy.rule.id if policy.rule else None,
            classification=classification.level.value,
            classification_evidence=evidence,
            findings=findings,
            fired_rules=policy.fired_rules,
            audit=audit,
            manifest_version=manifest.version if manifest else None,
        )
        return result, policy

    def evaluate(self, request: ActionRequest, timestamp: str) -> ActionResult:
        """Request leg: gate the act itself."""
        manifest, spec = self._spec(request.server_id, request.tool)
        findings = scan_elements(flatten_arguments(spec, request.arguments), self._detectors)
        result, _ = self._finish(request, spec, manifest, findings, timestamp, "request")
        return result

    def evaluate_result(self, request: ActionResultRequest, timestamp: str) -> ActionResult:
        """Response leg: gate the disclosure of what the act returned."""
        manifest, spec = self._spec(request.server_id, request.tool)
        findings = scan_elements(flatten_result(spec, request.result), self._detectors)
        result, _ = self._finish(
            request, spec, manifest, findings, timestamp, "response", has_undeclared_fields(spec, request.result)
        )
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dabt_python && python -m pytest tests/test_action_engine.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Run the full suite**

Run: `cd dabt_python && python -m pytest -q`
Expected: PASS, 139 tests

- [ ] **Step 6: Commit**

```bash
git add dabt_python/dabt_core/action.py dabt_python/tests/test_action_engine.py
git commit -m "Add the action engine, sharing classification, rules and audit with retrieval

An IBAN in an environment variable fires Article 11(3) minimisation with no new
rule code, which is the payoff of one engine across two surfaces. An
unmanifested tool, an unknown server, and a manifest entry below verified
confidence all resolve to REVIEW rather than ALLOW."
```

---

### Task 9: Per-element obligations and rewriting

**Files:**
- Modify: `dabt_python/dabt_core/action.py`
- Test: `dabt_python/tests/test_action_redaction.py`

**Interfaces:**
- Consumes: `apply_redactions` and `RedactionObligation` from `redactor`/`obligations`.
- Produces: `ElementObligation(element, start, end, strategy)`, `resolve_element_obligations(policy, spec, findings) -> tuple[ElementObligation, ...]`, `apply_element_redactions(values, obligations) -> dict[str, str]`, and `ActionResult.released_arguments` / `released_result` / `rewritten` / `obligations`.

- [ ] **Step 1: Write the failing test**

Create `dabt_python/tests/test_action_redaction.py`:

```python
from pathlib import Path

from dabt_core.action import ActionEngine, ActionRequest, ActionResultRequest
from dabt_core.loader import load_compliance_map
from dabt_core.manifest import validate_manifest_payload
from dabt_core.schema import Decision

ROOT = Path(__file__).parents[1] / "dabt_core" / "data"
TIMESTAMP = "2026-08-18T09:00:00Z"


def verified_manifest():
    """A transcribed-quality manifest, so ALLOW paths are reachable in tests."""
    payload = {
        "version": "test-verified",
        "server": {"id": "cranl"},
        "tools": {
            "set_env_var": {
                "operation": "update",
                "resource_type": "configuration",
                "persists_data": False,
                "confidence_level": "verified",
                "requires_legal_review": True,
                "parameters": {
                    "key": {"role": "resource_name", "maskable": False},
                    "value": {"role": "opaque_payload", "maskable": True},
                },
            },
            "list_env_vars": {
                "operation": "read",
                "resource_type": "configuration",
                "persists_data": False,
                "confidence_level": "verified",
                "requires_legal_review": True,
                "returns": {
                    "variables": {
                        "role": "opaque_payload",
                        "inspect_content": True,
                        "collection": True,
                        "maskable": True,
                    }
                },
            },
            "delete_database": {
                "operation": "delete",
                "resource_type": "database",
                "persists_data": False,
                "confidence_level": "verified",
                "requires_legal_review": True,
                "parameters": {"name": {"role": "resource_name", "maskable": False}},
            },
        },
    }
    return validate_manifest_payload(payload)


def engine() -> ActionEngine:
    manifest = verified_manifest()
    return ActionEngine(load_compliance_map(ROOT / "compliance_map.yaml"), {manifest.server_id: manifest})


def test_manifested_action_with_no_findings_allows() -> None:
    result = engine().evaluate(
        ActionRequest(server_id="cranl", tool="delete_database", arguments={"name": "production"}),
        TIMESTAMP,
    )
    assert result.decision == Decision.ALLOW
    assert result.decision_rule_id == "ACTION-DEFAULT-ALLOW-NO-FINDING"
    assert result.rewritten is False
    assert result.released_arguments == {"name": "production"}


def test_rewritten_flag_set_when_arguments_altered() -> None:
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl", tool="set_env_var", arguments={"key": "K", "value": "id 1000000008"}
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.ALLOW_WITH_REDACTION
    assert result.rewritten is True
    assert "1000000008" not in result.released_arguments["value"]
    assert result.released_arguments["key"] == "K"


def test_denied_action_releases_no_arguments() -> None:
    result = engine().evaluate(
        ActionRequest(
            server_id="cranl",
            tool="set_env_var",
            arguments={"key": "K", "value": "medical diagnosis on file"},
            lawful_basis="legitimate_interest",
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.DENY
    assert result.released_arguments is None


def test_collection_redacts_only_flagged_elements() -> None:
    result = engine().evaluate_result(
        ActionResultRequest(
            server_id="cranl",
            tool="list_env_vars",
            result={"variables": ["clean one", "iban SA0380000000608010167519", "clean two"]},
        ),
        TIMESTAMP,
    )
    released = result.released_result["variables"]
    assert released[0] == "clean one"
    assert released[2] == "clean two"
    assert "SA0380000000608010167519" not in released[1]


def test_collection_classification_aggregates_to_maximum() -> None:
    result = engine().evaluate_result(
        ActionResultRequest(
            server_id="cranl",
            tool="list_env_vars",
            result={"variables": ["clean", "medical diagnosis attached"]},
        ),
        TIMESTAMP,
    )
    assert result.classification == "Secret"


def test_undeclared_response_field_reviews() -> None:
    # Nothing inspected it, so it must not be permitted merely by not being looked at.
    result = engine().evaluate_result(
        ActionResultRequest(
            server_id="cranl", tool="list_env_vars", result={"surprise_field": "anything at all"}
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.REVIEW
    assert result.released_result is None


def test_write_tool_response_disclosure_is_gated() -> None:
    # The write proceeds; the credential it returns does not reach the model.
    manifest = validate_manifest_payload(
        {
            "version": "test-verified",
            "server": {"id": "cranl"},
            "tools": {
                "create_database": {
                    "operation": "create",
                    "resource_type": "database",
                    "persists_data": False,
                    "confidence_level": "verified",
                    "requires_legal_review": True,
                    "parameters": {"name": {"role": "resource_name", "maskable": False}},
                    "returns": {
                        "connection_string": {
                            "role": "credential",
                            "declared_sensitive": True,
                            "maskable": True,
                        }
                    },
                }
            },
        }
    )
    gate = ActionEngine(load_compliance_map(ROOT / "compliance_map.yaml"), {"cranl": manifest})

    permitted = gate.evaluate(
        ActionRequest(server_id="cranl", tool="create_database", arguments={"name": "customers"}), TIMESTAMP
    )
    assert permitted.decision == Decision.ALLOW

    withheld = gate.evaluate_result(
        ActionResultRequest(
            server_id="cranl",
            tool="create_database",
            result={"connection_string": "postgres://u:secret@host/db"},
        ),
        TIMESTAMP,
    )
    assert withheld.decision == Decision.REVIEW
    assert withheld.released_result is None


def test_collection_deny_withholds_every_element() -> None:
    result = engine().evaluate_result(
        ActionResultRequest(
            server_id="cranl",
            tool="list_env_vars",
            result={"variables": ["clean", "medical diagnosis attached"]},
            lawful_basis="legitimate_interest",
        ),
        TIMESTAMP,
    )
    assert result.decision == Decision.DENY
    assert result.released_result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dabt_python && python -m pytest tests/test_action_redaction.py -v`
Expected: FAIL with `AttributeError: 'ActionResult' object has no attribute 'rewritten'`

- [ ] **Step 3: Write the implementation**

In `dabt_python/dabt_core/action.py`, add this import to the existing import block:

```python
from .obligations import RedactionObligation
from .redactor import apply_redactions
```

Add this dataclass immediately after `ElementFinding`:

```python
@dataclass(frozen=True)
class ElementObligation:
    element: str
    start: int
    end: int
    strategy: str
```

Add these two functions immediately after `scan_elements`:

```python
def resolve_element_obligations(
    policy: PolicyDecision, spec: ToolSpec | None, findings: tuple[ElementFinding, ...]
) -> tuple[ElementObligation, ...]:
    """Mask only where a fired rule requires it and the manifest permits it."""
    if policy.decision != Decision.ALLOW_WITH_REDACTION:
        return ()
    obligations: list[ElementObligation] = []
    for rule in policy.fired_rules:
        directive = rule.obligation
        if directive is None:
            continue
        for item in findings:
            applies = directive.scope == "personal_data" and item.finding.is_personal_data
            applies = applies or (directive.scope == "sensitive_data" and item.finding.type == "sensitive_data")
            if not applies or not _maskable(spec, item.element):
                continue
            start, end = item.finding.redaction_span
            strategy = "full" if item.finding.type == "sensitive_data" else directive.strategy
            obligations.append(ElementObligation(item.element, start, end, strategy))
    return tuple(obligations)


def apply_element_redactions(
    values: Mapping[str, str], obligations: Iterable[ElementObligation]
) -> dict[str, str]:
    """Apply the retrieval gate's redactor to each element independently."""
    grouped: dict[str, list[RedactionObligation]] = {}
    for item in obligations:
        grouped.setdefault(item.element, []).append(
            RedactionObligation(item.start, item.end, "action_element", item.strategy)
        )
    return {
        element: apply_redactions(text, tuple(grouped[element])) if element in grouped else text
        for element, text in values.items()
    }
```

Add this helper immediately before `resolve_element_obligations`:

```python
def _maskable(spec: ToolSpec | None, element: str) -> bool:
    """Masking a region produces nonsense; the manifest says where masking is safe."""
    if spec is None:
        return False
    name = element.split(".", 1)[1] if "." in element else element
    name = name.split("[", 1)[0]
    declared = spec.parameter(name) if element.startswith("arguments.") else spec.return_field(name)
    return bool(declared and declared.maskable)
```

Now extend `ActionResult` with four fields, placed after `manifest_version`:

```python
    obligations: tuple[ElementObligation, ...] = ()
    released_arguments: dict[str, Any] | None = None
    released_result: dict[str, Any] | None = None
    rewritten: bool = False
```

Add these entries to `ActionResult.to_dict`, immediately before `"audit"`:

```python
            "obligations": [
                {"element": item.element, "start": item.start, "end": item.end, "strategy": item.strategy}
                for item in self.obligations
            ],
            "released_arguments": self.released_arguments,
            "released_result": self.released_result,
            "rewritten": self.rewritten,
```

Finally, rewrite `evaluate` and `evaluate_result` to resolve and apply obligations:

```python
    def evaluate(self, request: ActionRequest, timestamp: str) -> ActionResult:
        """Request leg: gate the act itself."""
        manifest, spec = self._spec(request.server_id, request.tool)
        values = flatten_arguments(spec, request.arguments)
        findings = scan_elements(values, self._detectors)
        result, policy = self._finish(request, spec, manifest, findings, timestamp, "request")
        obligations = resolve_element_obligations(policy, spec, findings)
        released: dict[str, Any] | None = None
        rewritten = False
        if result.decision in {Decision.ALLOW, Decision.ALLOW_WITH_REDACTION}:
            redacted = apply_element_redactions(values, obligations)
            released = {key.split(".", 1)[1]: value for key, value in redacted.items()}
            rewritten = redacted != values
        return replace(
            result, obligations=obligations, released_arguments=released, rewritten=rewritten
        )

    def evaluate_result(self, request: ActionResultRequest, timestamp: str) -> ActionResult:
        """Response leg: gate the disclosure of what the act returned."""
        manifest, spec = self._spec(request.server_id, request.tool)
        values = flatten_result(spec, request.result)
        findings = scan_elements(values, self._detectors)
        result, policy = self._finish(
            request, spec, manifest, findings, timestamp, "response", has_undeclared_fields(spec, request.result)
        )
        obligations = resolve_element_obligations(policy, spec, findings)
        released: dict[str, Any] | None = None
        rewritten = False
        if result.decision in {Decision.ALLOW, Decision.ALLOW_WITH_REDACTION}:
            redacted = apply_element_redactions(values, obligations)
            released = _rebuild_result(request.result, redacted)
            rewritten = redacted != values
        return replace(result, obligations=obligations, released_result=released, rewritten=rewritten)
```

Add this helper at module level, immediately after `apply_element_redactions`:

```python
def _rebuild_result(original: Mapping[str, Any], redacted: Mapping[str, str]) -> dict[str, Any]:
    """Reassemble the response, substituting masked elements back into place."""
    rebuilt: dict[str, Any] = {key: value for key, value in original.items()}
    for element, text in redacted.items():
        name = element.split(".", 1)[1]
        if "[" in name:
            field_name, index_part = name.split("[", 1)
            index = int(index_part.rstrip("]"))
            current = list(rebuilt.get(field_name) or [])
            if index < len(current):
                current[index] = text
                rebuilt[field_name] = current
            continue
        rebuilt[name] = text
    return rebuilt
```

And add `replace` to the dataclasses import at the top of the file:

```python
from dataclasses import dataclass, field, replace
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dabt_python && python -m pytest tests/test_action_redaction.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Run the full suite**

Run: `cd dabt_python && python -m pytest -q`
Expected: PASS, 145 tests

- [ ] **Step 6: Commit**

```bash
git add dabt_python/dabt_core/action.py dabt_python/tests/test_action_redaction.py
git commit -m "Rewrite tool calls per element, and never release a denied payload

Redaction applies per element while classification aggregates across all of
them: nine clean environment variables return intact, the tenth returns masked,
and one health value still raises the whole response to Secret under NDMO
Principle 4. Masking only happens where the manifest says it preserves meaning.

released_arguments and released_result are absent rather than empty on DENY and
REVIEW, mirroring how the retrieval gate never carries source text through a
denial, and rewritten is explicit so a proxy can tell an agent its call changed."
```

---

### Task 10: API endpoints, fail-closed

**Files:**
- Modify: `dabt_python/dabt_api/main.py`
- Test: `dabt_python/tests/test_action_api.py`

**Interfaces:**
- Consumes: `ActionEngine`, `ActionRequest`, `ActionResultRequest` from Tasks 7–9; `load_manifest` from Task 3.
- Produces: `POST /v1/action/evaluate` and `POST /v1/action/result`, both returning the action result plus `policy_map_version`, `manifest_version`, and the bilingual caveat.

- [ ] **Step 1: Write the failing test**

Create `dabt_python/tests/test_action_api.py`:

```python
from fastapi.testclient import TestClient

from dabt_api import main
from dabt_api.main import app

client = TestClient(app)


def test_action_evaluate_returns_a_decision() -> None:
    response = client.post(
        "/v1/action/evaluate",
        json={
            "server_id": "cranl",
            "tool": "create_database",
            "arguments": {"region": "eu-west-1", "name": "customers"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] in {"ALLOW", "ALLOW_WITH_REDACTION", "DENY", "REVIEW"}
    assert body["policy_map_version"] == main.COMPLIANCE_MAP.version
    assert body["manifest_version"]
    assert body["legal_review_disclaimer_ar"]


def test_action_result_endpoint_evaluates_the_response_leg() -> None:
    response = client.post(
        "/v1/action/result",
        json={
            "server_id": "cranl",
            "tool": "list_env_vars",
            "result": {"variables": ["clean", "iban SA0380000000608010167519"]},
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] in {"ALLOW_WITH_REDACTION", "DENY", "REVIEW"}


def test_action_gate_no_longer_returns_not_implemented() -> None:
    response = client.post(
        "/v1/action/evaluate", json={"server_id": "cranl", "tool": "get_logs", "arguments": {}}
    )
    assert response.status_code != 501


def test_invalid_action_request_returns_422_with_caveat() -> None:
    response = client.post("/v1/action/evaluate", json={"tool": "create_database"})
    assert response.status_code == 422
    assert response.json()["legal_review_disclaimer_en"]


def test_engine_fails_closed_on_evaluation_error(monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(main.ACTION_ENGINE, "evaluate", explode)
    response = client.post(
        "/v1/action/evaluate", json={"server_id": "cranl", "tool": "get_logs", "arguments": {}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "DENY"
    assert body["service_error"] is True
    assert body["legal_review_disclaimer_en"]
    assert "released_arguments" not in body or body["released_arguments"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dabt_python && python -m pytest tests/test_action_api.py -v`
Expected: FAIL. The endpoint still returns 501 and `main.ACTION_ENGINE` does not exist.

- [ ] **Step 3: Wire the endpoints**

In `dabt_python/dabt_api/main.py`, add to the import block:

```python
from dabt_core.action import ActionEngine, ActionRequest, ActionResultRequest
from dabt_core.manifest import load_manifest
```

Immediately after the existing `ENGINE = PolicyEngine(COMPLIANCE_MAP)` line, add:

```python
MANIFEST_DIR = Path(__file__).parents[1] / "dabt_core" / "data" / "manifests"
MANIFESTS = {
    manifest.server_id: manifest
    for manifest in (load_manifest(path) for path in sorted(MANIFEST_DIR.glob("*.yaml")))
}
ACTION_ENGINE = ActionEngine(COMPLIANCE_MAP, MANIFESTS)
```

Add these two payload models after the existing `RetrievalEvaluatePayload`:

```python
class ActionContextPayload(BaseModel):
    server_id: str = Field(min_length=1, max_length=128)
    tool: str = Field(min_length=1, max_length=256)
    agent_id: str = Field(default="demo-agent", max_length=128)
    purpose: str = Field(default="action", max_length=256)
    lawful_basis: str = Field(default="consent", max_length=128)
    sector: str = Field(default="development", max_length=128)
    agent_authorised: bool = True
    requires_minimisation: bool = True
    timestamp: str = "1970-01-01T00:00:00Z"


class ActionEvaluatePayload(ActionContextPayload):
    arguments: dict[str, Any] = Field(default_factory=dict)


class ActionResultPayload(ActionContextPayload):
    result: dict[str, Any] = Field(default_factory=dict)
```

Add this helper immediately before the endpoints:

```python
def failed_closed(detail_en: str, detail_ar: str) -> dict[str, Any]:
    """A gate that cannot decide denies. Failing open would defeat the gate."""
    return {
        "decision": "DENY",
        "decision_rule_id": None,
        "service_error": True,
        "detail_en": detail_en,
        "detail_ar": detail_ar,
        "released_arguments": None,
        "released_result": None,
        "rewritten": False,
        "policy_map_version": COMPLIANCE_MAP.version,
        **caveat_payload(),
    }
```

Replace the entire existing `evaluate_action` function with:

```python
@app.post("/v1/action/evaluate")
def evaluate_action(payload: ActionEvaluatePayload) -> dict[str, Any]:
    try:
        result = ACTION_ENGINE.evaluate(
            ActionRequest(
                server_id=payload.server_id,
                tool=payload.tool,
                arguments=payload.arguments,
                agent_id=payload.agent_id,
                purpose=payload.purpose,
                lawful_basis=payload.lawful_basis,
                sector=payload.sector,
                agent_authorised=payload.agent_authorised,
                requires_minimisation=payload.requires_minimisation,
            ),
            payload.timestamp,
        ).to_dict()
    except Exception:  # noqa: BLE001 - the gate denies on any failure it cannot describe
        return failed_closed(
            "The Action Gate could not evaluate this call and therefore denied it.",
            "تعذر على بوابة الإجراءات تقييم هذا الاستدعاء، ولذلك رفضته.",
        )
    return {**result, "policy_map_version": COMPLIANCE_MAP.version, **caveat_payload()}


@app.post("/v1/action/result")
def evaluate_action_result(payload: ActionResultPayload) -> dict[str, Any]:
    try:
        result = ACTION_ENGINE.evaluate_result(
            ActionResultRequest(
                server_id=payload.server_id,
                tool=payload.tool,
                result=payload.result,
                agent_id=payload.agent_id,
                purpose=payload.purpose,
                lawful_basis=payload.lawful_basis,
                sector=payload.sector,
                agent_authorised=payload.agent_authorised,
                requires_minimisation=payload.requires_minimisation,
            ),
            payload.timestamp,
        ).to_dict()
    except Exception:  # noqa: BLE001
        return failed_closed(
            "The Action Gate could not evaluate this result and therefore denied its disclosure.",
            "تعذر على بوابة الإجراءات تقييم هذه النتيجة، ولذلك رفضت الإفصاح عنها.",
        )
    return {**result, "policy_map_version": COMPLIANCE_MAP.version, **caveat_payload()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dabt_python && python -m pytest tests/test_action_api.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Run every suite**

Run: `cd dabt_python && python -m pytest -q`
Expected: PASS, 150 tests

Run: `cd .. && pnpm check`
Expected: exit 0

Run: `pnpm test`
Expected: 21 of 22 passing, with only the pre-existing `python3`-spawn failure in `server/dabt.test.ts`. Do not fix that test.

- [ ] **Step 6: Commit**

```bash
git add dabt_python/dabt_api/main.py dabt_python/tests/test_action_api.py
git commit -m "Replace the Action Gate 501 stub with two evaluating endpoints

The request leg gates the act, which is the only place a side effect can be
prevented. The response leg gates the disclosure, which matters regardless of
whether the operation was a read or a write.

Both fail closed: if the gate cannot describe why it is allowing something, it
denies. A gate that fails open is defeated by making it unavailable, which
reduces the guarantee to holding only while the gate happens to be up."
```

---

### Task 11: Update the reference documentation

**Files:**
- Modify: `README.md`
- Modify: `todo.md`

- [ ] **Step 1: Update the README capability table**

In `README.md`, in the "What the current reference build does" table, add this row immediately after the **Retrieval gate** row:

```markdown
| **Agent action gate** | Evaluates an MCP tool call before execution and its result before disclosure, returning the same four outcomes. Tool semantics come from a validated per-server manifest. Ships with a reconstructed CranL manifest whose entries are all `needs_verification`, so every action against it resolves to `REVIEW` until the published tool schema is transcribed. |
```

In the "What Dabt explicitly does **not** do" table, add:

```markdown
| **Operational safety** | Dabt gates regulatory violations, not operational blast radius. A destructive call carrying no regulated data passes the gate. Platforms should keep their own confirmation step for destructive operations. |
```

- [ ] **Step 2: Tick the completed todo items**

In `todo.md`, add a new section at the end:

```markdown
## Agent Action Gate — policy brain

- [x] Shared `rules.py` so both surfaces cannot drift on condition matching
- [x] Tool manifest types with load-time validation
- [x] Reconstructed CranL manifest, every entry `needs_verification`
- [x] `surface` scoping so the retrieval allow rule cannot permit an action
- [x] Boundary-coverage test proving every map rule has a firing context
- [x] Inferred region residency table in the compliance map
- [x] Three action rules, including an explicit ALLOW path
- [x] Per-element detection, obligations, and rewriting
- [x] Two endpoints replacing the 501 stub, failing closed
- [ ] Transcribe CranL's published tool schema and raise the manifest to `verified`
- [ ] Reference MCP proxy (separate plan)
- [ ] Harden the subprocess lifecycle before pitching fail-closed as a guarantee
```

- [ ] **Step 3: Commit**

```bash
git add README.md todo.md
git commit -m "Document the Agent Action Gate and its stated scope boundary

Records that Dabt gates regulatory violations rather than operational blast
radius, so a destructive call carrying no regulated data passes, and that the
shipped CranL manifest is a reconstruction resolving to REVIEW until the real
tool schema is transcribed."
```

---

## Deviations from the spec, and why

Two conditions in spec §6.3 are implemented differently. Both are corrections
that make the spec's own §3.1 narrative work, and §6.3 should be amended to
match before this ships.

1. **`NCA-ECC-CREDENTIAL-DISCLOSURE` gains `leg: response`.**
   `response_declared_credential` is a property of the *tool*, so it is equally
   true on the request leg. Without leg-scoping the rule fires at priority 310
   during the request and `create_database` could never execute at all — whereas
   §3.1 requires the write to proceed and only the disclosure to be gated.

2. **`ACTION-DEFAULT-ALLOW-NO-FINDING` drops `response_declared_credential:
   false` and gains `undeclared_response_fields: false`.** With the credential
   rule leg-scoped, priority ordering already handles credentials (310 beats
   950), and keeping the condition would block a credential-returning tool's
   request leg from ever being permitted. The replacement condition makes spec
   limitation 2 real: without it, a response containing only fields the manifest
   never described would reach `ALLOW` purely because nothing inspected it.

## Verification Checklist

Run after Task 11.

- [ ] `cd dabt_python && python -m pytest -q` — 153 passing
- [ ] `pnpm check` — exit 0
- [ ] `pnpm test` — 21/22, only the known `python3`-spawn failure
- [ ] `pnpm build` — succeeds
- [ ] `git log --oneline` — eleven commits, one per task
- [ ] Every spec section §3–§10 maps to a task above
- [ ] No manifest entry claims `confidence_level: verified`
- [ ] `test_public_document_allows` passes unchanged — the retrieval regression proof
