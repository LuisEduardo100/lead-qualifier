from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.database import get_db
from backend.models import Lead, Message
from backend.auth import get_current_user

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("")
async def list_leads(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Lead).options(selectinload(Lead.channel)).order_by(Lead.last_message_at.desc())
    if status:
        q = q.where(Lead.status == status)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "phone": r.phone,
            "name": r.name,
            "status": r.status,
            "city": r.city,
            "interest": r.interest,
            "project_type": r.project_type,
            "last_message_at": r.last_message_at.isoformat(),
            "channel": r.channel.name if r.channel else None,
        }
        for r in rows
    ]


@router.get("/{lead_id}")
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    lead = (await db.execute(
        select(Lead).where(Lead.id == lead_id).options(selectinload(Lead.messages), selectinload(Lead.channel))
    )).scalar_one_or_none()
    if not lead:
        raise HTTPException(404)
    return {
        "id": lead.id,
        "phone": lead.phone,
        "name": lead.name,
        "email": lead.email,
        "city": lead.city,
        "budget": lead.budget,
        "project_type": lead.project_type,
        "interest": lead.interest,
        "status": lead.status,
        "created_at": lead.created_at.isoformat(),
        "last_message_at": lead.last_message_at.isoformat(),
        "channel": lead.channel.name if lead.channel else None,
        "messages": [
            {"direction": m.direction, "content": m.content, "at": m.created_at.isoformat()}
            for m in lead.messages
        ],
    }


@router.patch("/{lead_id}/status")
async def update_status(lead_id: int, body: dict, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(404)
    lead.status = body.get("status", lead.status)
    await db.commit()
    return {"ok": True}
