from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, UTC
from typing import Optional
from backend.database import get_db
from backend.models import (
    Campaign, CampaignRecipient, CampaignRecipientStatus,
    CampaignStatus, Lead, Channel,
)
from backend.auth import get_current_user
from backend.services import campaign_sender

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    name: str
    message: str
    channel_id: int
    filter_status: Optional[str] = None


def _recipient_leads_query(filter_status: str | None):
    """Selects one Lead per distinct phone (most recently created), filtered by status."""
    subq = select(Lead.phone, func.max(Lead.id).label("lead_id")).group_by(Lead.phone)
    if filter_status:
        subq = subq.where(Lead.status == filter_status)
    subq = subq.subquery()
    return select(Lead).join(subq, Lead.id == subq.c.lead_id)


@router.get("")
async def list_campaigns(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    rows = (await db.execute(
        select(Campaign).options(selectinload(Campaign.channel)).order_by(Campaign.created_at.desc())
    )).scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "status": c.status,
            "channel": c.channel.name if c.channel else None,
            "filter_status": c.filter_status,
            "total": c.total,
            "sent_count": c.sent_count,
            "failed_count": c.failed_count,
            "created_at": c.created_at.isoformat(),
            "launched_at": c.launched_at.isoformat() if c.launched_at else None,
        }
        for c in rows
    ]


@router.post("/preview")
async def preview_recipients(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = _recipient_leads_query(body.get("filter_status"))
    count = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    return {"count": count}


@router.post("")
async def create_campaign(
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    channel = (await db.execute(
        select(Channel).where(Channel.id == body.channel_id)
    )).scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Canal nao encontrado")

    leads = (await db.execute(_recipient_leads_query(body.filter_status))).scalars().all()
    if not leads:
        raise HTTPException(400, "Nenhum lead encontrado com os filtros selecionados")

    campaign = Campaign(
        name=body.name,
        message=body.message,
        channel_id=body.channel_id,
        filter_status=body.filter_status,
        total=len(leads),
    )
    db.add(campaign)
    await db.flush()

    for lead in leads:
        db.add(CampaignRecipient(
            campaign_id=campaign.id,
            lead_id=lead.id,
            phone=lead.phone,
        ))

    await db.commit()
    await db.refresh(campaign)
    return {"id": campaign.id, "total": campaign.total, "status": campaign.status}


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    campaign = (await db.execute(
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .options(selectinload(Campaign.channel), selectinload(Campaign.recipients))
    )).scalar_one_or_none()
    if not campaign:
        raise HTTPException(404)
    return {
        "id": campaign.id,
        "name": campaign.name,
        "message": campaign.message,
        "status": campaign.status,
        "channel": campaign.channel.name if campaign.channel else None,
        "channel_type": campaign.channel.channel_type if campaign.channel else None,
        "filter_status": campaign.filter_status,
        "total": campaign.total,
        "sent_count": campaign.sent_count,
        "failed_count": campaign.failed_count,
        "created_at": campaign.created_at.isoformat(),
        "launched_at": campaign.launched_at.isoformat() if campaign.launched_at else None,
        "recipients": [
            {
                "phone": r.phone,
                "delivery_status": r.delivery_status,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "error": r.error,
            }
            for r in campaign.recipients
        ],
    }


@router.post("/{campaign_id}/launch")
async def launch_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    campaign = (await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )).scalar_one_or_none()
    if not campaign:
        raise HTTPException(404)
    if campaign.status != CampaignStatus.draft:
        raise HTTPException(400, f"Campanha nao pode ser lancada (status atual: {campaign.status})")

    campaign.status = CampaignStatus.running
    campaign.launched_at = datetime.now(UTC)
    await db.commit()

    background_tasks.add_task(campaign_sender.run_campaign, campaign_id)
    return {"ok": True, "status": "running"}


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    campaign = (await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )).scalar_one_or_none()
    if not campaign:
        raise HTTPException(404)
    if campaign.status == CampaignStatus.running:
        raise HTTPException(400, "Nao e possivel deletar campanha em execucao")
    await db.execute(delete(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign_id))
    await db.delete(campaign)
    await db.commit()
    return {"ok": True}
