"""Session creation/persistence + API contract/validation tests (real DB, no mocks)."""
import uuid


def test_create_session_returns_valid_session(client):
    resp = client.post("/sessions", json={"user_id": "test-user"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == "test-user"
    assert body["title"] is None
    uuid.UUID(body["id"])  # raises if not a valid UUID


def test_get_session_round_trips(client):
    created = client.post("/sessions", json={"user_id": "alice"}).json()
    fetched = client.get(f"/sessions/{created['id']}").json()
    assert fetched["id"] == created["id"]
    assert fetched["user_id"] == "alice"


def test_get_nonexistent_session_returns_structured_404(client):
    bogus_id = "00000000-0000-0000-0000-000000000000"
    resp = client.get(f"/sessions/{bogus_id}")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "NOT_FOUND"
    assert "error" in body and "detail" in body


def test_post_message_persists_and_list_returns_both_turns(client):
    session = client.post("/sessions", json={}).json()
    resp = client.post(f"/sessions/{session['id']}/messages", json={"content": "What is a PRD?"})
    assert resp.status_code == 201
    assistant_msg = resp.json()
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["session_id"] == session["id"]

    history = client.get(f"/sessions/{session['id']}/messages").json()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "What is a PRD?"
    assert history[1]["role"] == "assistant"
    assert history[1]["id"] == assistant_msg["id"]


def test_post_message_to_nonexistent_session_returns_404(client):
    bogus_id = "00000000-0000-0000-0000-000000000000"
    resp = client.post(f"/sessions/{bogus_id}/messages", json={"content": "hello"})
    assert resp.status_code == 404


# --- Contract / validation tests ---


def test_empty_message_content_rejected_with_structured_422(client):
    session = client.post("/sessions", json={}).json()
    resp = client.post(f"/sessions/{session['id']}/messages", json={"content": ""})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"


def test_missing_required_field_rejected(client):
    session = client.post("/sessions", json={}).json()
    resp = client.post(f"/sessions/{session['id']}/messages", json={})
    assert resp.status_code == 422


def test_malformed_session_id_rejected(client):
    resp = client.get("/sessions/not-a-valid-uuid/messages")
    assert resp.status_code == 422


def test_health_endpoint_reports_real_db_status(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "ok"
    assert "model_provider" in body


def test_config_endpoint_reflects_settings(client):
    resp = client.get("/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_provider"] in ("anthropic", "ollama")
    assert isinstance(body["anthropic_configured"], bool)
