import pytest


@pytest.mark.asyncio
async def test_get_config_returns_defaults(client, auth_headers):
    r = await client.get("/api/config", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "agent_prompt" in data
    assert "business_context" in data
    assert data["max_tokens"] == "40"
    assert data["temperature"] == "0.7"


@pytest.mark.asyncio
async def test_update_config_persists(client, auth_headers):
    r = await client.put(
        "/api/config",
        json={"business_context": "Empresa de tecnologia"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r = await client.get("/api/config", headers=auth_headers)
    assert r.json()["business_context"] == "Empresa de tecnologia"


@pytest.mark.asyncio
async def test_update_config_overwrites_existing(client, auth_headers):
    await client.put("/api/config", json={"max_tokens": "60"}, headers=auth_headers)
    await client.put("/api/config", json={"max_tokens": "80"}, headers=auth_headers)

    r = await client.get("/api/config", headers=auth_headers)
    assert r.json()["max_tokens"] == "80"


@pytest.mark.asyncio
async def test_config_merges_db_with_defaults(client, auth_headers):
    await client.put("/api/config", json={"agent_name": "Carlos"}, headers=auth_headers)

    r = await client.get("/api/config", headers=auth_headers)
    data = r.json()
    assert data["agent_name"] == "Carlos"
    # Un-updated keys still have their defaults
    assert "qualification_criteria" in data
