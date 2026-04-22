import pytest
from unittest.mock import AsyncMock
from sqlalchemy import select
from backend.models import Channel, Lead, Message, MessageDirection


def _text_payload(jid="5511999999999@s.whatsapp.net", text="Olá"):
    return {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": False, "remoteJid": jid},
            "pushName": "Usuário Teste",
            "message": {"conversation": text},
        },
    }


# --- Pure helper functions ---

def test_normalize_number_strips_symbols():
    from backend.routers.webhooks import _normalize_number

    assert _normalize_number("+55 11 999-99-9999") == "5511999999999"
    assert _normalize_number("551199999") == "551199999"


def test_normalize_number_preserves_jid():
    from backend.routers.webhooks import _normalize_number

    assert _normalize_number("5511@s.whatsapp.net") == "5511@s.whatsapp.net"


def test_cfg_returns_matching_value():
    from backend.routers.webhooks import _cfg
    from backend.models import AgentConfig

    configs = [
        AgentConfig(key="business_context", value="Empresa X"),
        AgentConfig(key="max_tokens", value="50"),
    ]
    assert _cfg(configs, "business_context") == "Empresa X"
    assert _cfg(configs, "max_tokens") == "50"


def test_cfg_returns_default_when_missing():
    from backend.routers.webhooks import _cfg
    from backend.models import AgentConfig

    configs = [AgentConfig(key="a", value="val")]
    assert _cfg(configs, "missing_key", "default") == "default"
    assert _cfg(configs, "missing_key") == ""


# --- Webhook endpoint tests ---

@pytest.mark.asyncio
async def test_webhook_non_upsert_event_returns_ok(client):
    r = await client.post(
        "/webhook/any-instance",
        json={"event": "connection.update", "data": {}},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_webhook_from_me_ignored(client):
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": True, "remoteJid": "5511@s.whatsapp.net"},
            "message": {"conversation": "self message"},
        },
    }
    r = await client.post("/webhook/any-instance", json=payload)
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_webhook_group_message_ignored(client):
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": False, "remoteJid": "12345@g.us"},
            "message": {"conversation": "group message"},
        },
    }
    r = await client.post("/webhook/any-instance", json=payload)
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_webhook_unknown_instance_returns_ok(client):
    r = await client.post("/webhook/nonexistent-inst", json=_text_payload())
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_webhook_sticker_message_skipped(client, db_session):
    channel = Channel(name="WH Sticker", instance_name="wh-sticker", status="connected")
    db_session.add(channel)
    await db_session.commit()

    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": False, "remoteJid": "5511111111111@s.whatsapp.net"},
            "message": {"stickerMessage": {}},
        },
    }
    r = await client.post("/webhook/wh-sticker", json=payload)
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_webhook_document_message_extracted(client, db_session, monkeypatch):
    import backend.agents.qualification as qa_mod
    import backend.agents.response as ra_mod
    import backend.routers.webhooks as wh_mod

    monkeypatch.setattr(qa_mod, "qualify", AsyncMock(return_value={
        "status": "warm", "next_question": "Qual é o seu interesse?", "collected": {},
    }))
    monkeypatch.setattr(ra_mod, "generate_response", AsyncMock(return_value="Recebi o documento!"))
    monkeypatch.setattr(wh_mod, "send_text_human", AsyncMock())
    monkeypatch.setattr(wh_mod, "get_active_document", AsyncMock(return_value=None))

    channel = Channel(name="WH Doc", instance_name="wh-doc", status="connected")
    db_session.add(channel)
    await db_session.commit()

    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": False, "remoteJid": "5511222222222@s.whatsapp.net"},
            "pushName": "Doc User",
            "message": {"documentMessage": {"fileName": "proposta.pdf", "caption": "Segue proposta"}},
        },
    }
    r = await client.post("/webhook/wh-doc", json=payload)
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_webhook_creates_new_lead_and_responds(client, db_session, monkeypatch):
    import backend.agents.qualification as qa_mod
    import backend.agents.response as ra_mod
    import backend.routers.webhooks as wh_mod

    monkeypatch.setattr(qa_mod, "qualify", AsyncMock(return_value={
        "status": "warm", "next_question": "Qual produto te interessa?", "collected": {},
    }))
    monkeypatch.setattr(ra_mod, "generate_response", AsyncMock(return_value="Qual produto te interessa?"))
    monkeypatch.setattr(wh_mod, "send_text_human", AsyncMock())
    monkeypatch.setattr(wh_mod, "get_active_document", AsyncMock(return_value=None))

    channel = Channel(name="WH New Lead", instance_name="wh-new-lead", status="connected")
    db_session.add(channel)
    await db_session.commit()

    r = await client.post("/webhook/wh-new-lead", json=_text_payload(jid="5511666666666@s.whatsapp.net"))
    assert r.status_code == 200
    assert r.json()["ok"] is True

    lead = (await db_session.execute(
        select(Lead).where(Lead.phone == "5511666666666")
    )).scalar_one_or_none()
    assert lead is not None

    msgs = (await db_session.execute(
        select(Message).where(Message.lead_id == lead.id)
    )).scalars().all()
    directions = {m.direction for m in msgs}
    assert MessageDirection.inbound in directions
    assert MessageDirection.outbound in directions


@pytest.mark.asyncio
async def test_webhook_agent_paused_skips_ai(client, db_session, monkeypatch):
    import backend.agents.qualification as qa_mod

    qualify_mock = AsyncMock()
    monkeypatch.setattr(qa_mod, "qualify", qualify_mock)

    channel = Channel(name="WH Paused", instance_name="wh-paused", status="connected")
    db_session.add(channel)
    await db_session.flush()
    lead = Lead(channel_id=channel.id, phone="5511555555555", status="warm", agent_paused=True)
    db_session.add(lead)
    await db_session.commit()

    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": False, "remoteJid": "5511555555555@s.whatsapp.net"},
            "pushName": "Paused User",
            "message": {"conversation": "Oi, quero comprar!"},
        },
    }
    r = await client.post("/webhook/wh-paused", json=payload)
    assert r.json()["ok"] is True
    qualify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_updates_lead_status_to_hot(client, db_session, monkeypatch):
    import backend.agents.qualification as qa_mod
    import backend.agents.response as ra_mod
    import backend.routers.webhooks as wh_mod

    monkeypatch.setattr(qa_mod, "qualify", AsyncMock(return_value={
        "status": "hot",
        "next_question": None,
        "collected": {"email": "hot@lead.com"},
    }))
    monkeypatch.setattr(ra_mod, "generate_response", AsyncMock(return_value="Ótimo! Vou te passar mais detalhes."))
    monkeypatch.setattr(wh_mod, "send_text_human", AsyncMock())
    monkeypatch.setattr(wh_mod, "get_active_document", AsyncMock(return_value=None))

    channel = Channel(name="WH Hot", instance_name="wh-hot", status="connected")
    db_session.add(channel)
    await db_session.flush()
    lead = Lead(channel_id=channel.id, phone="5511444444444", status="warm")
    db_session.add(lead)
    await db_session.commit()
    lead_id = lead.id

    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": False, "remoteJid": "5511444444444@s.whatsapp.net"},
            "pushName": "Hot User",
            "message": {"conversation": "Quero comprar o produto X agora!"},
        },
    }
    r = await client.post("/webhook/wh-hot", json=payload)
    assert r.json()["ok"] is True

    updated = (await db_session.execute(
        select(Lead).where(Lead.id == lead_id)
    )).scalar_one()
    await db_session.refresh(updated)
    assert updated.status == "hot"


@pytest.mark.asyncio
async def test_webhook_qualify_error_returns_ok(client, db_session, monkeypatch):
    import backend.agents.qualification as qa_mod
    import backend.routers.webhooks as wh_mod

    monkeypatch.setattr(qa_mod, "qualify", AsyncMock(side_effect=Exception("Groq timeout")))
    monkeypatch.setattr(wh_mod, "get_active_document", AsyncMock(return_value=None))

    channel = Channel(name="WH Err", instance_name="wh-err", status="connected")
    db_session.add(channel)
    await db_session.commit()

    r = await client.post("/webhook/wh-err", json=_text_payload(jid="5511333333333@s.whatsapp.net"))
    assert r.status_code == 200
    assert r.json()["ok"] is True
