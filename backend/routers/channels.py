import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from backend.database import get_db
from backend.models import Channel, Lead, Message, FollowUpLog
from backend.auth import get_current_user
from backend.services import evolution
from backend import qr_store
import os

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _webhook_url(instance_name: str) -> str:
    base = os.getenv("PUBLIC_URL", "http://api:8000")
    return f"{base}/webhook/{instance_name}"


class ChannelCreate(BaseModel):
    name: str
    channel_type: str = "baileys"
    wa_token: Optional[str] = None
    wa_phone_number_id: Optional[str] = None
    wa_business_id: Optional[str] = None


@router.get("")
async def list_channels(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    rows = (await db.execute(select(Channel))).scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "instance": c.instance_name,
            "status": c.status,
            "channel_type": c.channel_type,
        }
        for c in rows
    ]


@router.post("")
async def create_channel(
    body: ChannelCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    instance_name = body.name.lower().replace(" ", "-")
    existing = (await db.execute(
        select(Channel).where(Channel.instance_name == instance_name)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Canal ja existe")

    if body.channel_type == "whatsapp-business":
        if not all([body.wa_token, body.wa_phone_number_id, body.wa_business_id]):
            raise HTTPException(
                400,
                "WA Business requer wa_token, wa_phone_number_id e wa_business_id",
            )
        await evolution.create_business_instance(
            instance_name=instance_name,
            webhook_url=_webhook_url(instance_name),
            token=body.wa_token,
            number=body.wa_phone_number_id,
            business_id=body.wa_business_id,
        )
        channel = Channel(
            name=body.name,
            instance_name=instance_name,
            channel_type="whatsapp-business",
            wa_token=body.wa_token,
            wa_phone_number_id=body.wa_phone_number_id,
            wa_business_id=body.wa_business_id,
            status="connected",
        )
    else:
        await evolution.create_instance(instance_name, _webhook_url(instance_name))
        channel = Channel(
            name=body.name,
            instance_name=instance_name,
            channel_type="baileys",
            status="disconnected",
        )

    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return {
        "id": channel.id,
        "instance": instance_name,
        "status": channel.status,
        "channel_type": channel.channel_type,
    }


@router.get("/{channel_id}/qrcode")
async def get_qrcode(channel_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    channel = (await db.execute(
        select(Channel).where(Channel.id == channel_id)
    )).scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Canal nao encontrado")
    if channel.channel_type == "whatsapp-business":
        raise HTTPException(400, "Canais WA Business nao usam QR Code")
    qr_store.clear_qr(channel.instance_name)
    await evolution.trigger_connect(channel.instance_name)
    b64 = await qr_store.wait_for_qr(channel.instance_name, timeout=20)
    if not b64:
        raise HTTPException(408, "QR Code nao disponivel")
    return {"base64": b64}


@router.get("/{channel_id}/status")
async def check_status(channel_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    channel = (await db.execute(
        select(Channel).where(Channel.id == channel_id)
    )).scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Canal nao encontrado")
    state = await evolution.get_connection_state(channel.instance_name)
    channel.status = "connected" if state == "open" else "disconnected"
    await db.commit()
    return {"status": channel.status, "raw": state}


@router.delete("/{channel_id}")
async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    channel = (await db.execute(
        select(Channel).where(Channel.id == channel_id)
    )).scalar_one_or_none()
    if not channel:
        raise HTTPException(404)
    lead_ids = (await db.execute(
        select(Lead.id).where(Lead.channel_id == channel_id)
    )).scalars().all()
    if lead_ids:
        await db.execute(delete(FollowUpLog).where(FollowUpLog.lead_id.in_(lead_ids)))
        await db.execute(delete(Message).where(Message.lead_id.in_(lead_ids)))
        await db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
    await evolution.delete_instance(channel.instance_name)
    await db.delete(channel)
    await db.commit()
    return {"ok": True}
