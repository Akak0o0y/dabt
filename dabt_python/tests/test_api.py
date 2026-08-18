from fastapi.testclient import TestClient

from dabt_api import main
from dabt_api.main import app


client = TestClient(app)
TIMESTAMP = "2026-08-18T09:00:00Z"


def test_retrieval_evaluate_returns_full_decision() -> None:
    response = client.post(
        "/v1/retrieval/evaluate",
        json={
            "document": "National ID 1000000008",
            "cross_border": True,
            "timestamp": TIMESTAMP,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW_WITH_REDACTION"
    assert body["redacted_document"] != "National ID 1000000008"
    assert body["audit"]["legal_review_disclaimer_en"]
    assert body["policy_map_version"] == main.COMPLIANCE_MAP.version


def test_action_gate_is_implemented_and_validates_its_payload() -> None:
    # This test previously asserted a documented 501. The Agent Action Gate is
    # implemented now, so the same call must be rejected as malformed rather
    # than answered with a not-implemented notice.
    response = client.post("/v1/action/evaluate", json={"action": "send_payment"})
    assert response.status_code == 422
    assert response.json()["legal_review_disclaimer_en"]


def test_action_gate_evaluates_a_well_formed_call() -> None:
    response = client.post(
        "/v1/action/evaluate",
        json={
            "server_id": "cranl",
            "tool": "get_logs",
            "arguments": {"app_id": "app-1"},
            "timestamp": TIMESTAMP,
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] in {"ALLOW", "ALLOW_WITH_REDACTION", "DENY", "REVIEW"}


def test_map_endpoint_exposes_confidence_levels_without_authoritative_claim() -> None:
    response = client.get("/v1/compliance-map")
    assert response.status_code == 200
    body = response.json()
    assert body["rules"][0]["confidence_level"]
    assert all(item["requires_legal_review"] is True for item in body["rules"])
    assert "authoritative" not in str(body).lower()


def test_invalid_request_returns_422_not_500_with_caveat() -> None:
    response = client.post("/v1/retrieval/evaluate", json={"cross_border": True})
    assert response.status_code == 422
    assert response.json()["legal_review_disclaimer_en"]


def test_every_endpoint_response_carries_legal_caveat() -> None:
    responses = [
        client.post("/v1/retrieval/evaluate", json={"document": "Public report."}),
        client.post(
            "/v1/action/evaluate",
            json={"server_id": "cranl", "tool": "get_logs", "arguments": {}},
        ),
        client.get("/v1/compliance-map"),
    ]
    for response in responses:
        payload = response.json()
        assert payload["legal_review_disclaimer_en"]
        assert payload["legal_review_disclaimer_ar"]


def test_unexpected_error_still_carries_legal_caveat(monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(main.ENGINE, "evaluate", explode)
    non_raising_client = TestClient(app, raise_server_exceptions=False)
    response = non_raising_client.post(
        "/v1/retrieval/evaluate",
        json={"document": "Public report.", "timestamp": TIMESTAMP},
    )
    assert response.status_code == 500
    assert response.json()["legal_review_disclaimer_en"]
    assert response.json()["legal_review_disclaimer_ar"]


def test_retrieval_requires_an_explicit_timestamp() -> None:
    # The engine is a pure function that takes its clock from the caller. A
    # defaulted timestamp means a caller who forgets the field still gets a full
    # set of sealed audit records, every one of them attesting to the wrong
    # instant. Refusing is the only honest answer.
    response = client.post("/v1/retrieval/evaluate", json={"document": "Public report."})
    assert response.status_code == 422
    assert response.json()["legal_review_disclaimer_en"]


def test_retrieval_rejects_an_empty_timestamp() -> None:
    response = client.post(
        "/v1/retrieval/evaluate", json={"document": "Public report.", "timestamp": ""}
    )
    assert response.status_code == 422
