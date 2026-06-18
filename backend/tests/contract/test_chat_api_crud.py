from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_chat_session_crud_workflow(client):
    create_response = client.post("/api/chat/sessions", json={"title": "Contract Chat"})
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["success"] is True
    session_id = created["data"]["id"]
    assert created["data"]["title"] == "Contract Chat"
    assert created["data"]["messages"] == []

    add_response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={
            "role": "user",
            "content": "验证 Chat CRUD 的契约路径",
            "meta_json": '{"source":"contract"}',
        },
    )
    assert add_response.status_code == 200
    assert add_response.json() == {"success": True, "data": None, "error": None}

    detail_response = client.get(f"/api/chat/sessions/{session_id}")
    detail = detail_response.json()
    assert detail_response.status_code == 200
    assert detail["success"] is True
    assert detail["data"]["messages"][0]["role"] == "user"
    assert detail["data"]["messages"][0]["content"] == "验证 Chat CRUD 的契约路径"
    assert detail["data"]["messages"][0]["meta_json"] == '{"source":"contract"}'

    update_response = client.patch(
        f"/api/chat/sessions/{session_id}",
        json={"title": "Contract Chat Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json() == {"success": True, "data": None, "error": None}

    list_response = client.get("/api/chat/sessions", params={"limit": 5})
    listed = list_response.json()
    assert list_response.status_code == 200
    assert listed["success"] is True
    assert listed["data"][0]["id"] == session_id
    assert listed["data"][0]["title"] == "Contract Chat Updated"
    assert listed["data"][0]["message_count"] == 1

    delete_response = client.delete(f"/api/chat/sessions/{session_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"success": True, "data": None, "error": None}

    deleted_detail = client.get(f"/api/chat/sessions/{session_id}").json()
    assert deleted_detail == {"success": False, "data": None, "error": "会话不存在"}


def test_chat_message_rejects_unknown_role(client):
    create_response = client.post("/api/chat/sessions", json={"title": "Role Boundary"})
    session_id = create_response.json()["data"]["id"]

    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"role": "system", "content": "invalid role"},
    )

    assert response.status_code == 422
