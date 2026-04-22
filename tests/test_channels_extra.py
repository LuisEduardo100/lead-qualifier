import pytest
from unittest.mock import AsyncMock
from backend.models import Channel, Lead


@pytest.mark.asyncio
async def test_list_channels_empty(client, auth_headers, monkeypatch):
    from backend.services import evolution

    monkeypatch.setattr(evolution, "fetch_instance_info", AsyncMock(return_value={}))

    r = await client.get("/api/channels", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_channels_returns_data(client, auth_headers, db_session, monkeypatch):
    from backend.services import evolution

    monkeypatch.setattr(evolution, "fetch_instance_info", AsyncMock(return_value={}))

    channel = Channel(name="Lista Chan", instance_name="lista-chan", status="disconnected")
    db_session.add(channel)
    await db_session.commit()

    r = await client.get("/api/channels", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Lista Chan"


@pytest.mark.asyncio
async def test_create_baileys_channel_success(client, auth_headers, monkeypatch):
    from backend.services import evolution

    monkeypatch.setattr(evolution, "create_instance", AsyncMock(return_value={}))

    r = await client.post("/api/channels", json={"name": "Baileys WA"}, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["channel_type"] == "baileys"
    assert data["status"] == "disconnected"


@pytest.mark.asyncio
async def test_create_channel_duplicate_raises_400(client, auth_headers, monkeypatch):
    from backend.services import evolution

    monkeypatch.setattr(evolution, "create_instance", AsyncMock(return_value={}))

    await client.post("/api/channels", json={"name": "Meu Canal"}, headers=auth_headers)
    r = await client.post("/api/channels", json={"name": "Meu Canal"}, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_channel_not_found(client, auth_headers):
    r = await client.delete("/api/channels/99999", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_channel_success(client, auth_headers, db_session, monkeypatch):
    from backend.services import evolution

    monkeypatch.setattr(evolution, "delete_instance", AsyncMock())

    channel = Channel(name="Del Chan", instance_name="del-chan-test", status="connected")
    db_session.add(channel)
    await db_session.commit()

    r = await client.delete(f"/api/channels/{channel.id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_check_status_open_becomes_connected(client, auth_headers, db_session, monkeypatch):
    from backend.services import evolution

    monkeypatch.setattr(evolution, "get_connection_state", AsyncMock(return_value="open"))

    channel = Channel(name="Status Chan", instance_name="status-chan-test", status="disconnected")
    db_session.add(channel)
    await db_session.commit()

    r = await client.get(f"/api/channels/{channel.id}/status", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "connected"
    assert data["raw"] == "open"


@pytest.mark.asyncio
async def test_check_status_not_connected(client, auth_headers, db_session, monkeypatch):
    from backend.services import evolution

    monkeypatch.setattr(evolution, "get_connection_state", AsyncMock(return_value="close"))

    channel = Channel(name="Status Chan2", instance_name="status-chan2-test", status="connected")
    db_session.add(channel)
    await db_session.commit()

    r = await client.get(f"/api/channels/{channel.id}/status", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "disconnected"


@pytest.mark.asyncio
async def test_qrcode_wa_business_raises_400(client, auth_headers, db_session):
    channel = Channel(
        name="WA Biz QR",
        instance_name="wa-biz-qr-test",
        channel_type="whatsapp-business",
        status="connected",
    )
    db_session.add(channel)
    await db_session.commit()

    r = await client.get(f"/api/channels/{channel.id}/qrcode", headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_channel_cascades_leads(client, auth_headers, db_session, monkeypatch):
    from backend.services import evolution
    from sqlalchemy import select

    monkeypatch.setattr(evolution, "delete_instance", AsyncMock())

    channel = Channel(name="Cascade Chan", instance_name="cascade-chan-test", status="connected")
    db_session.add(channel)
    await db_session.flush()
    db_session.add(Lead(channel_id=channel.id, phone="5511900099001", status="warm"))
    await db_session.commit()
    channel_id = channel.id

    r = await client.delete(f"/api/channels/{channel_id}", headers=auth_headers)
    assert r.status_code == 200

    remaining = (await db_session.execute(
        select(Lead).where(Lead.channel_id == channel_id)
    )).scalars().all()
    assert remaining == []
