import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models import Channel
from backend.auth import get_current_user
from backend.services import evolution
import os

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _webhook_url(instance_name: str) -> str:
    base = os.getenv("PUBLIC_URL", "http://api:8000")
    return f"{base}/webhook/{instance_name}"


class ChannelCreate(BaseModel):
    name: str


@router.get("")
async def list_channels(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    rows = (await db.execute(select(Channel))).scalars().all()
    return [{"id": c.id, "name": c.name, "instance": c.instance_name, "status": c.status} for c in rows]


@router.post("")
async def create_channel(body: ChannelCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    instance_name = body.name.lower().replace(" ", "-")
    existing = (await db.execute(select(Channel).where(Channel.instance_name == instance_name))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Canal já existe")

    await evolution.create_instance(instance_name, _webhook_url(instance_name))

    channel = Channel(name=body.name, instance_name=instance_name, status="disconnected")
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return {"id": channel.id, "instance": instance_name, "status": "disconnected"}


@router.get("/{channel_id}/qrcode")
async def get_qrcode(channel_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    channel = (await db.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Canal não encontrado")
    data = await evolution.get_qrcode(channel.instance_name)
    return data


@router.get("/{channel_id}/status")
async def check_status(channel_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    channel = (await db.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Canal não encontrado")
    state = await evolution.get_connection_state(channel.instance_name)
    channel.status = "connected" if state == "open" else "disconnected"
    await db.commit()
    return {"status": channel.status, "raw": state}


@router.delete("/{channel_id}")
async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    channel = (await db.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if not channel:
        raise HTTPException(404)
    await evolution.delete_instance(channel.instance_name)
    await db.delete(channel)
    await db.commit()
    return {"ok": True}
