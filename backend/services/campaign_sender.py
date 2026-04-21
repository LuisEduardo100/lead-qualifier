import asyncio
import logging
from datetime import datetime, UTC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import SessionLocal
from backend.models import Campaign, CampaignRecipient, CampaignRecipientStatus, CampaignStatus, Channel
from backend.services import evolution

logger = logging.getLogger(__name__)
SEND_DELAY_SECONDS = 1.5


async def run_campaign_with_session(campaign_id: int, db: AsyncSession) -> None:
    """Core sending loop — accepts an existing DB session (facilitates testing)."""
    campaign = (await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )).scalar_one_or_none()

    if not campaign or campaign.status != CampaignStatus.running:
        return

    channel = (await db.execute(
        select(Channel).where(Channel.id == campaign.channel_id)
    )).scalar_one_or_none()

    if not channel:
        campaign.status = CampaignStatus.failed
        await db.commit()
        return

    recipients = (await db.execute(
        select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.delivery_status == CampaignRecipientStatus.pending,
        )
    )).scalars().all()

    for recipient in recipients:
        try:
            await evolution.send_text(channel.instance_name, recipient.phone, campaign.message)
            recipient.delivery_status = CampaignRecipientStatus.sent
            recipient.sent_at = datetime.now(UTC)
            campaign.sent_count += 1
        except Exception as e:
            logger.error(f"Campaign {campaign_id}: failed to send to {recipient.phone}: {e}")
            recipient.delivery_status = CampaignRecipientStatus.failed
            recipient.error = str(e)[:500]
            campaign.failed_count += 1
        await db.commit()
        await asyncio.sleep(SEND_DELAY_SECONDS)

    campaign.status = CampaignStatus.done
    await db.commit()


async def run_campaign(campaign_id: int) -> None:
    """BackgroundTasks entry point — opens its own DB session."""
    async with SessionLocal() as db:
        await run_campaign_with_session(campaign_id, db)
