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
