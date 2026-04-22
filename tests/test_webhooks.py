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
async def test_webhook_pdf_document_downloaded_and_extracted(client, db_session, monkeypatch):
    """PDF sent by client is downloaded and text extracted into the message."""
    import backend.agents.qualification as qa_mod
    import backend.agents.response as ra_mod
    import backend.routers.webhooks as wh_mod
    from sqlalchemy import select as sa_select
    from backend.models import Message

    monkeypatch.setattr(qa_mod, "qualify", AsyncMock(return_value={
        "status": "warm", "next_question": "Qual produto?", "collected": {},
    }))
    monkeypatch.setattr(ra_mod, "generate_response", AsyncMock(return_value="Recebi a lista, vou analisar!"))
    monkeypatch.setattr(wh_mod, "send_text_human", AsyncMock())
    monkeypatch.setattr(wh_mod, "get_active_document", AsyncMock(return_value=None))

    download_mock = AsyncMock(return_value="FAKEPDFB64==")
    monkeypatch.setattr(wh_mod, "download_media_base64", download_mock)

    extract_mock = AsyncMock(return_value="Produto A: R$ 100\nProduto B: R$ 200")
    monkeypatch.setattr(wh_mod, "_extract_pdf_text", extract_mock)

    channel = Channel(name="WH PDF", instance_name="wh-pdf-test", status="connected")
    db_session.add(channel)
    await db_session.commit()

    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": False, "remoteJid": "5511777777771@s.whatsapp.net"},
            "pushName": "PDF User",
            "message": {"documentMessage": {
                "fileName": "lista_produtos.pdf",
                "mimetype": "application/pdf",
                "caption": "Minha lista de pedidos",
            }},
        },
    }
    r = await client.post("/webhook/wh-pdf-test", json=payload)
    assert r.json()["ok"] is True

    download_mock.assert_called_once()
    extract_mock.assert_called_once_with("FAKEPDFB64==")

    msgs = (await db_session.execute(
        sa_select(Message).where(Message.media_type == "document")
    )).scalars().all()
    assert len(msgs) == 1
    assert "Produto A" in msgs[0].content
    assert "lista_produtos.pdf" in msgs[0].content


@pytest.mark.asyncio
async def test_webhook_non_pdf_document_no_download(client, db_session, monkeypatch):
    """Non-PDF documents (Word, Excel) are acknowledged without download attempt."""
    import backend.agents.qualification as qa_mod
    import backend.agents.response as ra_mod
    import backend.routers.webhooks as wh_mod

    monkeypatch.setattr(qa_mod, "qualify", AsyncMock(return_value={
        "status": "warm", "next_question": None, "collected": {},
    }))
    monkeypatch.setattr(ra_mod, "generate_response", AsyncMock(return_value="Recebi o documento."))
    monkeypatch.setattr(wh_mod, "send_text_human", AsyncMock())
    monkeypatch.setattr(wh_mod, "get_active_document", AsyncMock(return_value=None))

    download_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(wh_mod, "download_media_base64", download_mock)

    channel = Channel(name="WH DOCX", instance_name="wh-docx-test", status="connected")
    db_session.add(channel)
    await db_session.commit()

    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": False, "remoteJid": "5511777777772@s.whatsapp.net"},
            "pushName": "Docx User",
            "message": {"documentMessage": {
                "fileName": "proposta.docx",
                "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }},
        },
    }
    r = await client.post("/webhook/wh-docx-test", json=payload)
    assert r.json()["ok"] is True
    download_mock.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_catalog_not_marked_until_sent(client, db_session, monkeypatch):
    """CATÁLOGO_ENVIADO marker is NOT written by the request handler — only by the background task."""
    import backend.agents.qualification as qa_mod
    import backend.agents.response as ra_mod
    import backend.routers.webhooks as wh_mod
    from sqlalchemy import select as sa_select

    monkeypatch.setattr(qa_mod, "qualify", AsyncMock(return_value={
        "status": "warm", "next_question": None, "collected": {},
    }))
    monkeypatch.setattr(ra_mod, "generate_response", AsyncMock(return_value="Estou enviando o catálogo!"))
    monkeypatch.setattr(wh_mod, "send_text_human", AsyncMock())

    from backend.models import AgentDocument
    fake_doc = AgentDocument(
        filename="catalogo.pdf", file_path="/fake/catalogo.pdf",
        original_size=1024, page_count=3, is_active=True,
    )
    monkeypatch.setattr(wh_mod, "get_active_document", AsyncMock(return_value=fake_doc))
    monkeypatch.setattr(wh_mod, "search_relevant_chunks", AsyncMock(return_value=[]))

    catalog_task_mock = AsyncMock()
    monkeypatch.setattr(wh_mod, "_send_catalog_task", catalog_task_mock)

    channel = Channel(name="WH Cat", instance_name="wh-cat-test", status="connected")
    db_session.add(channel)
    await db_session.commit()

    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": False, "remoteJid": "5511777777773@s.whatsapp.net"},
            "pushName": "Cat User",
            "message": {"conversation": "Pode me mandar o catálogo?"},
        },
    }
    r = await client.post("/webhook/wh-cat-test", json=payload)
    assert r.json()["ok"] is True

    msgs = (await db_session.execute(
        sa_select(Message).where(Message.content == "[CATÁLOGO_ENVIADO]")
    )).scalars().all()
    assert len(msgs) == 0, "CATÁLOGO_ENVIADO must not be committed by the request handler"


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
