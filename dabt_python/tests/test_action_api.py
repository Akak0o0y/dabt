from fastapi.testclient import TestClient

from dabt_api import main
from dabt_api.main import app

client = TestClient(app)
TIMESTAMP = "2026-08-18T09:00:00Z"


def test_action_evaluate_returns_a_decision() -> None:
    response = client.post(
        "/v1/action/evaluate",
        json={
            "server_id": "cranl",
            "tool": "create_database",
            "arguments": {"region": "eu-west-1", "name": "customers"},
            "timestamp": TIMESTAMP,
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
            "timestamp": TIMESTAMP,
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] in {"ALLOW_WITH_REDACTION", "DENY", "REVIEW"}


def test_action_gate_no_longer_returns_not_implemented() -> None:
    response = client.post(
        "/v1/action/evaluate",
        json={"server_id": "cranl", "tool": "get_logs", "arguments": {}, "timestamp": TIMESTAMP},
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
        "/v1/action/evaluate",
        json={"server_id": "cranl", "tool": "get_logs", "arguments": {}, "timestamp": TIMESTAMP},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "DENY"
    assert body["service_error"] is True
    assert body["legal_review_disclaimer_en"]
    assert body["released_arguments"] is None


def test_result_leg_fails_closed_on_evaluation_error(monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(main.ACTION_ENGINE, "evaluate_result", explode)
    response = client.post(
        "/v1/action/result",
        json={"server_id": "cranl", "tool": "get_logs", "result": {}, "timestamp": TIMESTAMP},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "DENY"
    assert body["service_error"] is True
    assert body["released_result"] is None


def test_action_evaluate_requires_an_explicit_timestamp() -> None:
    response = client.post(
        "/v1/action/evaluate",
        json={"server_id": "cranl", "tool": "get_logs", "arguments": {}},
    )
    assert response.status_code == 422
    assert response.json()["legal_review_disclaimer_en"]


def test_action_result_requires_an_explicit_timestamp() -> None:
    response = client.post(
        "/v1/action/result",
        json={"server_id": "cranl", "tool": "get_logs", "result": {}},
    )
    assert response.status_code == 422


def test_action_rejects_a_timestamp_that_is_not_an_instant() -> None:
    response = client.post(
        "/v1/action/evaluate",
        json={"server_id": "cranl", "tool": "get_logs", "arguments": {}, "timestamp": "banana"},
    )
    assert response.status_code == 422
    assert response.json()["legal_review_disclaimer_en"]


def test_action_result_rejects_a_naive_timestamp() -> None:
    response = client.post(
        "/v1/action/result",
        json={
            "server_id": "cranl",
            "tool": "get_logs",
            "result": {},
            "timestamp": "2026-08-18T09:00:00",
        },
    )
    assert response.status_code == 422
