"""FastAPI service boundary for Dabt's deterministic policy engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dabt_core.action import ActionEngine, ActionRequest, ActionResultRequest
from dabt_core.audit import LEGAL_REVIEW_DISCLAIMER_AR, LEGAL_REVIEW_DISCLAIMER_EN
from dabt_core.engine import EngineRequest, PolicyEngine
from dabt_core.loader import load_compliance_map
from dabt_core.manifest import load_manifest


MAP_PATH = Path(__file__).parents[1] / "dabt_core" / "data" / "compliance_map.yaml"
COMPLIANCE_MAP = load_compliance_map(MAP_PATH)
ENGINE = PolicyEngine(COMPLIANCE_MAP)

MANIFEST_DIR = Path(__file__).parents[1] / "dabt_core" / "data" / "manifests"
MANIFESTS = {
    manifest.server_id: manifest
    for manifest in (load_manifest(path) for path in sorted(MANIFEST_DIR.glob("*.yaml")))
}
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Any, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail_en": "Request validation failed; no compliance decision was produced.",
            "detail_ar": "فشل التحقق من صحة الطلب؛ لم يُنتج أي قرار امتثال.",
            "validation_errors": exc.errors(),
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


class RetrievalEvaluatePayload(BaseModel):
    document: str = Field(min_length=1, max_length=100_000)
    agent_id: str = Field(default="demo-agent", max_length=128)
    purpose: str = Field(default="retrieval", max_length=256)
    lawful_basis: str = Field(default="consent", max_length=128)
    cross_border: bool = False
    sector: str = Field(default="development", max_length=128)
    event_type: str = Field(default="disclosure", max_length=128)
    agent_authorised: bool = True
    requires_minimisation: bool = True
    # Required, never defaulted. The engine takes its clock from the caller,
    # so a default would let a caller who omits the field seal a full set of
    # audit records that all attest to the wrong instant.
    timestamp: str = Field(min_length=1, max_length=64)


class ActionContextPayload(BaseModel):
    server_id: str = Field(min_length=1, max_length=128)
    tool: str = Field(min_length=1, max_length=256)
    agent_id: str = Field(default="demo-agent", max_length=128)
    purpose: str = Field(default="action", max_length=256)
    lawful_basis: str = Field(default="consent", max_length=128)
    sector: str = Field(default="development", max_length=128)
    agent_authorised: bool = True
    requires_minimisation: bool = True
    # Required, never defaulted. The engine takes its clock from the caller,
    # so a default would let a caller who omits the field seal a full set of
    # audit records that all attest to the wrong instant.
    timestamp: str = Field(min_length=1, max_length=64)


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
