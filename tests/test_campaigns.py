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
