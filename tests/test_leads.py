import pytest
from unittest.mock import AsyncMock
from backend.models import Channel, Lead


@pytest.mark.asyncio
async def test_list_leads_empty(client, auth_headers):
    r = await client.get("/api/leads", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_leads_with_status_filter(client, auth_headers, db_session):
    channel = Channel(name="Ch Filter", instance_name="ch-filter", status="connected")
    db_session.add(channel)
    await db_session.flush()
    db_session.add(Lead(channel_id=channel.id, phone="551100000001", status="hot"))
    db_session.add(Lead(channel_id=channel.id, phone="551100000002", status="warm"))
    await db_session.commit()

    r = await client.get("/api/leads?status=hot", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["status"] == "hot"


@pytest.mark.asyncio
async def test_get_lead_not_found(client, auth_headers):
    r = await client.get("/api/leads/99999", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_lead_found(client, auth_headers, db_session):
    channel = Channel(name="Ch Found", instance_name="ch-found", status="connected")
    db_session.add(channel)
    await db_session.flush()
    lead = Lead(channel_id=channel.id, phone="551100000010", name="João", status="warm")
    db_session.add(lead)
    await db_session.commit()

    r = await client.get(f"/api/leads/{lead.id}", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["phone"] == "551100000010"
    assert data["name"] == "João"
    assert "messages" in data


@pytest.mark.asyncio
async def test_update_lead_status(client, auth_headers, db_session):
    channel = Channel(name="Ch Status", instance_name="ch-status", status="connected")
    db_session.add(channel)
    await db_session.flush()
    lead = Lead(channel_id=channel.id, phone="551100000020", status="warm")
    db_session.add(lead)
    await db_session.commit()

    r = await client.patch(f"/api/leads/{lead.id}/status", json={"status": "hot"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_update_lead_status_not_found(client, auth_headers):
    r = await client.patch("/api/leads/99999/status", json={"status": "hot"}, headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_toggle_pause_on_and_off(client, auth_headers, db_session):
    channel = Channel(name="Ch Pause", instance_name="ch-pause", status="connected")
    db_session.add(channel)
    await db_session.flush()
    lead = Lead(channel_id=channel.id, phone="551100000030", status="warm", agent_paused=False)
    db_session.add(lead)
    await db_session.commit()

    r = await client.patch(f"/api/leads/{lead.id}/pause", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["agent_paused"] is True

    r = await client.patch(f"/api/leads/{lead.id}/pause", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["agent_paused"] is False


@pytest.mark.asyncio
async def test_send_message_empty_text_raises_400(client, auth_headers, db_session):
    channel = Channel(name="Ch Send Empty", instance_name="ch-send-empty", status="connected")
    db_session.add(channel)
    await db_session.flush()
    lead = Lead(channel_id=channel.id, phone="551100000040", status="warm")
    db_session.add(lead)
    await db_session.commit()

    r = await client.post(f"/api/leads/{lead.id}/send", json={"text": ""}, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_send_message_success(client, auth_headers, db_session, monkeypatch):
    import backend.routers.leads as leads_mod

    monkeypatch.setattr(leads_mod, "send_text_human", AsyncMock())

    channel = Channel(name="Ch Send OK", instance_name="ch-send-ok", status="connected")
    db_session.add(channel)
    await db_session.flush()
    lead = Lead(channel_id=channel.id, phone="551100000050", status="warm")
    db_session.add(lead)
    await db_session.commit()

    r = await client.post(f"/api/leads/{lead.id}/send", json={"text": "Olá lead!"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True
