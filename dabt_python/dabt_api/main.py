"""FastAPI service boundary for Dabt's deterministic policy engine."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from dabt_core.action import ActionEngine, ActionRequest, ActionResultRequest
from dabt_core.audit import LEGAL_REVIEW_DISCLAIMER_AR, LEGAL_REVIEW_DISCLAIMER_EN
from dabt_core.engine import EngineRequest, PolicyEngine
from dabt_core.loader import load_compliance_map
from dabt_core.manifest import load_manifest


MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"
COMPLIANCE_MAP = load_compliance_map(MAP_PATH)
ENGINE = PolicyEngine(COMPLIANCE_MAP)

MANIFEST_DIR = Path(__file__).parents[1] / "dabt_core" / "data" / "manifests"


def manifest_directories() -> list[Path]:
    """Packaged manifests first, then any directory named by DABT_MANIFEST_DIRS.

    A manifest is a claim about someone else's software, so an organisation
    gating its own MCP server needs to supply one without forking this package.
    Later directories win on a server_id collision, which is what lets a
    transcribed manifest supersede a reconstructed one.
    """
    extra = os.environ.get("DABT_MANIFEST_DIRS", "")
    return [MANIFEST_DIR, *(Path(item) for item in extra.split(os.pathsep) if item)]


def load_manifests() -> dict[str, Any]:
    manifests: dict[str, Any] = {}
    for directory in manifest_directories():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.yaml")):
            manifest = load_manifest(path)
            manifests[manifest.server_id] = manifest
    return manifests


MANIFESTS = load_manifests()
ACTION_ENGINE = ActionEngine(COMPLIANCE_MAP, MANIFESTS)

app = FastAPI(
    title="Dabt Core API",
    version="0.1.0",
    description="Research-grounded Saudi data retrieval policy enforcement. Not legal advice.",
)


def caveat_payload() -> dict[str, str]:
    return {
        "legal_review_disclaimer_en": LEGAL_REVIEW_DISCLAIMER_EN,
        "legal_review_disclaimer_ar": LEGAL_REVIEW_DISCLAIMER_AR,
    }


def serialisable_errors(errors: Any) -> list[dict[str, Any]]:
    """Render validation errors as JSON.

    Pydantic puts the exception object a custom validator raised into `ctx`, and
    an exception cannot be serialised. Emitting it unchanged turns a 422 into a
    500, which would report a service failure for what is really a malformed
    request - and would drop the bilingual caveat along the way.
    """
    cleaned: list[dict[str, Any]] = []
    for error in errors:
        item = {key: value for key, value in error.items() if key != "ctx"}
        context = error.get("ctx")
        if context:
            item["ctx"] = {key: str(value) for key, value in context.items()}
        cleaned.append(item)
    return cleaned


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Any, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail_en": "Request validation failed; no compliance decision was produced.",
            "detail_ar": "فشل التحقق من صحة الطلب؛ لم يُنتج أي قرار امتثال.",
            "validation_errors": serialisable_errors(exc.errors()),
            **caveat_payload(),
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(_: Any, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail_en": "An unexpected service error occurred; no compliance decision should be relied upon.",
            "detail_ar": "حدث خطأ غير متوقع في الخدمة؛ ولا ينبغي الاعتماد على أي قرار امتثال.",
            **caveat_payload(),
        },
    )


class TimestampedPayload(BaseModel):
    """Every evaluation must name the instant it was made.

    The engine is a pure function that takes its clock from the caller, which is
    what makes its output reproducible. That only holds if the caller supplies a
    real instant: a missing, malformed, or timezone-naive value would still seal
    an audit record, and a record that cannot say when the decision was made is
    worse than no record at all.
    """

    timestamp: str = Field(min_length=1, max_length=64)

    @field_validator("timestamp")
    @classmethod
    def _require_iso_8601_instant(cls, value: str) -> str:
        # datetime.fromisoformat only accepts a trailing Z from Python 3.11.
        # Normalising here keeps the check identical across supported versions.
        candidate = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError(
                "must be an ISO 8601 instant, for example 2026-08-18T09:00:00Z"
            ) from exc
        if parsed.tzinfo is None:
            raise ValueError(
                "must carry an explicit UTC offset; a wall-clock reading does not "
                "identify an instant"
            )
        # The caller's own representation is preserved rather than normalised, so
        # the audit record states exactly what was asserted to it.
        return value


class RetrievalEvaluatePayload(TimestampedPayload):
    document: str = Field(min_length=1, max_length=100_000)
    agent_id: str = Field(default="demo-agent", max_length=128)
    purpose: str = Field(default="retrieval", max_length=256)
    lawful_basis: str = Field(default="consent", max_length=128)
    cross_border: bool = False
    sector: str = Field(default="development", max_length=128)
    event_type: str = Field(default="disclosure", max_length=128)
    agent_authorised: bool = True
    requires_minimisation: bool = True


class ActionContextPayload(TimestampedPayload):
    server_id: str = Field(min_length=1, max_length=128)
    tool: str = Field(min_length=1, max_length=256)
    agent_id: str = Field(default="demo-agent", max_length=128)
    purpose: str = Field(default="action", max_length=256)
    lawful_basis: str = Field(default="consent", max_length=128)
    sector: str = Field(default="development", max_length=128)
    agent_authorised: bool = True
    requires_minimisation: bool = True


class ActionEvaluatePayload(ActionContextPayload):
    arguments: dict[str, Any] = Field(default_factory=dict)


class ActionResultPayload(ActionContextPayload):
    result: dict[str, Any] = Field(default_factory=dict)


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


@app.post("/v1/retrieval/evaluate")
def evaluate_retrieval(payload: RetrievalEvaluatePayload) -> dict[str, Any]:
    result = ENGINE.evaluate(
        EngineRequest(
            document=payload.document,
            agent_id=payload.agent_id,
            purpose=payload.purpose,
            lawful_basis=payload.lawful_basis,
            cross_border=payload.cross_border,
            sector=payload.sector,
            event_type=payload.event_type,
            agent_authorised=payload.agent_authorised,
            requires_minimisation=payload.requires_minimisation,
        ),
        payload.timestamp,
    ).to_dict()
    return {**result, "policy_map_version": COMPLIANCE_MAP.version, **caveat_payload()}


@app.post("/v1/action/evaluate")
def evaluate_action(payload: ActionEvaluatePayload) -> dict[str, Any]:
    """Request leg: gate the act itself, before any side effect occurs."""
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
    """Response leg: gate the disclosure of what the act returned."""
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


@app.get("/v1/compliance-map")
def compliance_map() -> dict[str, Any]:
    return {
        "version": COMPLIANCE_MAP.version,
        "rules": [
            {
                "id": rule.id,
                "priority": rule.priority,
                "decision": str(rule.decision),
                "framework": rule.framework,
                "article": rule.citation.article,
                "confidence_level": str(rule.confidence_level),
                "requires_legal_review": rule.requires_legal_review,
                "sama_maturity_contribution": rule.sama_maturity_contribution,
                "mapped_controls": [
                    {
                        "framework": str(mapped.framework),
                        "control_id": mapped.control_id,
                        "granularity": mapped.granularity,
                        "confidence_level": str(mapped.confidence_level),
                        "requires_legal_review": mapped.requires_legal_review,
                    }
                    for mapped in rule.mapped_controls
                ],
            }
            for rule in COMPLIANCE_MAP.rules
        ],
        **caveat_payload(),
    }
