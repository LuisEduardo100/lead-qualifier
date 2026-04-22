import pytest
from unittest.mock import AsyncMock
from backend.models import Campaign, CampaignStatus, CampaignRecipient, CampaignRecipientStatus, Lead, Channel


@pytest.mark.asyncio
async def test_campaign_model_defaults(db_session):
    channel = Channel(
        name="WA Business", instance_name="wa-biz",
        channel_type="whatsapp-business", status="connected",
    )
    db_session.add(channel)
    await db_session.flush()

    campaign = Campaign(
        name="Campanha Hot",
        message="Ola! Temos uma oferta especial.",
        channel_id=channel.id,
        filter_status="hot",
    )
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)

    assert campaign.status == CampaignStatus.draft
    assert campaign.total == 0
    assert campaign.sent_count == 0
    assert campaign.failed_count == 0


@pytest.mark.asyncio
async def test_create_business_instance_payload(monkeypatch):
    from backend.services import evolution

    captured = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"instance": {"instanceName": "wabiz"}}

    async def fake_post(self, url, headers, json):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(evolution.httpx.AsyncClient, "post", fake_post)

    await evolution.create_business_instance(
        instance_name="wabiz",
        webhook_url="http://api:8000/webhook/wabiz",
        token="TOKEN123",
        number="551199999999",
        business_id="BIZ456",
    )

    assert captured["json"]["integration"] == "WHATSAPP-BUSINESS"
    assert captured["json"]["token"] == "TOKEN123"
    assert captured["json"]["number"] == "551199999999"
    assert captured["json"]["businessId"] == "BIZ456"
    assert captured["json"]["qrcode"] is False


@pytest.mark.asyncio
async def test_create_business_channel_missing_credentials(client, auth_headers):
    r = await client.post("/api/channels", json={
        "name": "WA Business",
        "channel_type": "whatsapp-business",
    }, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_business_channel_succeeds(client, auth_headers, monkeypatch):
    from backend.services import evolution

    async def fake_create_business(*args, **kwargs):
        return {"instance": {"instanceName": "wabiz-test"}}

    monkeypatch.setattr(evolution, "create_business_instance", fake_create_business)

    r = await client.post("/api/channels", json={
        "name": "WA Business Test",
        "channel_type": "whatsapp-business",
        "wa_token": "TOKEN",
        "wa_phone_number_id": "123",
        "wa_business_id": "456",
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["channel_type"] == "whatsapp-business"
    assert data["status"] == "connected"


@pytest.mark.asyncio
async def test_campaign_sender_marks_sent(db_session, monkeypatch):
    from backend.services import evolution, campaign_sender
    from backend.models import CampaignRecipientStatus, CampaignStatus

    async def fake_send(instance_name, phone, text):
        return {"key": {"id": "msg1"}}

    monkeypatch.setattr(evolution, "send_text", fake_send)
    monkeypatch.setattr(campaign_sender.asyncio, "sleep", AsyncMock())

    channel = Channel(name="WB", instance_name="wb", channel_type="whatsapp-business", status="connected")
    db_session.add(channel)
    await db_session.flush()
    lead = Lead(channel_id=channel.id, phone="5511900000001", status="hot")
    db_session.add(lead)
    await db_session.flush()
    campaign = Campaign(
        name="Test", message="Ola!", channel_id=channel.id,
        filter_status="hot", status="running", total=1,
    )
    db_session.add(campaign)
    await db_session.flush()
    recipient = CampaignRecipient(campaign_id=campaign.id, lead_id=lead.id, phone=lead.phone)
    db_session.add(recipient)
    await db_session.commit()

    await campaign_sender.run_campaign_with_session(campaign.id, db_session)

    await db_session.refresh(recipient)
    await db_session.refresh(campaign)
    assert recipient.delivery_status == CampaignRecipientStatus.sent
    assert campaign.sent_count == 1
    assert campaign.status == CampaignStatus.done


@pytest.mark.asyncio
async def test_campaign_sender_marks_failed_on_error(db_session, monkeypatch):
    from backend.services import evolution, campaign_sender
    from backend.models import CampaignRecipientStatus, CampaignStatus

    async def fake_send_error(instance_name, phone, text):
        raise Exception("Evolution API 429")

    monkeypatch.setattr(evolution, "send_text", fake_send_error)
    monkeypatch.setattr(campaign_sender.asyncio, "sleep", AsyncMock())

    channel = Channel(name="WB2", instance_name="wb2", channel_type="whatsapp-business", status="connected")
    db_session.add(channel)
    await db_session.flush()
    lead = Lead(channel_id=channel.id, phone="5511900000002", status="hot")
    db_session.add(lead)
    await db_session.flush()
    campaign = Campaign(
        name="Fail", message="Msg", channel_id=channel.id,
        filter_status="hot", status="running", total=1,
    )
    db_session.add(campaign)
    await db_session.flush()
    recipient = CampaignRecipient(campaign_id=campaign.id, lead_id=lead.id, phone=lead.phone)
    db_session.add(recipient)
    await db_session.commit()

    await campaign_sender.run_campaign_with_session(campaign.id, db_session)

    await db_session.refresh(recipient)
    await db_session.refresh(campaign)
    assert recipient.delivery_status == CampaignRecipientStatus.failed
    assert campaign.failed_count == 1
    assert campaign.status == CampaignStatus.done


@pytest.mark.asyncio
async def test_preview_empty_returns_zero(client, auth_headers):
    r = await client.post("/api/campaigns/preview", json={"filter_status": "hot"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["count"] == 0


@pytest.mark.asyncio
async def test_preview_deduplicates_phones_across_channels(client, auth_headers, db_session):
    c1 = Channel(name="Ch1", instance_name="ch1", status="connected")
    c2 = Channel(name="Ch2", instance_name="ch2", status="connected")
    db_session.add(c1)
    db_session.add(c2)
    await db_session.flush()
    # Same phone in two channels — should count as 1
    db_session.add(Lead(channel_id=c1.id, phone="5511900000001", status="hot"))
    db_session.add(Lead(channel_id=c2.id, phone="5511900000001", status="hot"))
    db_session.add(Lead(channel_id=c1.id, phone="5511900000002", status="warm"))
    await db_session.commit()

    r = await client.post("/api/campaigns/preview", json={"filter_status": "hot"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["count"] == 1


@pytest.mark.asyncio
async def test_create_campaign_draft(client, auth_headers, db_session):
    channel = Channel(name="WB3", instance_name="wb3", channel_type="whatsapp-business", status="connected")
    db_session.add(channel)
    await db_session.flush()
    db_session.add(Lead(channel_id=channel.id, phone="5511900000010", status="hot"))
    await db_session.commit()

    r = await client.post("/api/campaigns", json={
        "name": "Campanha Hot",
        "message": "Ola! Oferta especial.",
        "channel_id": channel.id,
        "filter_status": "hot",
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_create_campaign_no_leads_raises_400(client, auth_headers, db_session):
    channel = Channel(name="WB4", instance_name="wb4", status="connected")
    db_session.add(channel)
    await db_session.commit()

    r = await client.post("/api/campaigns", json={
        "name": "Vazia", "message": "msg", "channel_id": channel.id, "filter_status": "hot",
    }, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_launch_transitions_to_running(client, auth_headers, db_session, monkeypatch):
    from backend.services import campaign_sender

    monkeypatch.setattr(campaign_sender, "run_campaign", AsyncMock())

    channel = Channel(name="WB5", instance_name="wb5", channel_type="whatsapp-business", status="connected")
    db_session.add(channel)
    await db_session.flush()
    db_session.add(Lead(channel_id=channel.id, phone="5511900000020", status="warm"))
    await db_session.commit()

    r = await client.post("/api/campaigns", json={
        "name": "Follow-up Mornos", "message": "Lembrete!", "channel_id": channel.id, "filter_status": "warm",
    }, headers=auth_headers)
    cid = r.json()["id"]

    r = await client.post(f"/api/campaigns/{cid}/launch", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "running"


@pytest.mark.asyncio
async def test_launch_already_running_raises_400(client, auth_headers, db_session, monkeypatch):
    from backend.services import campaign_sender

    monkeypatch.setattr(campaign_sender, "run_campaign", AsyncMock())

    channel = Channel(name="WB6", instance_name="wb6", channel_type="whatsapp-business", status="connected")
    db_session.add(channel)
    await db_session.flush()
    db_session.add(Lead(channel_id=channel.id, phone="5511900000030", status="hot"))
    await db_session.commit()

    r = await client.post("/api/campaigns", json={
        "name": "Duplo", "message": "msg", "channel_id": channel.id, "filter_status": "hot",
    }, headers=auth_headers)
    cid = r.json()["id"]

    await client.post(f"/api/campaigns/{cid}/launch", headers=auth_headers)
    r = await client.post(f"/api/campaigns/{cid}/launch", headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_draft_campaign(client, auth_headers, db_session):
    channel = Channel(name="WB7", instance_name="wb7", channel_type="whatsapp-business", status="connected")
    db_session.add(channel)
    await db_session.flush()
    db_session.add(Lead(channel_id=channel.id, phone="5511900000040", status="hot"))
    await db_session.commit()

    r = await client.post("/api/campaigns", json={
        "name": "Para deletar", "message": "x", "channel_id": channel.id, "filter_status": "hot",
    }, headers=auth_headers)
    cid = r.json()["id"]

    r = await client.delete(f"/api/campaigns/{cid}", headers=auth_headers)
    assert r.status_code == 200

    r = await client.get(f"/api/campaigns/{cid}", headers=auth_headers)
    assert r.status_code == 404
