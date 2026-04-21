import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, UTC
from backend.database import get_db
from backend.models import Channel, Lead, Message, AgentConfig, LeadStatus, MessageDirection
from backend.agents import qualification as qa, response as ra
from backend.services.evolution import send_text
from backend import qr_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

MAX_HISTORY = 20


def _cfg(configs, key, default=""):
    for c in configs:
        if c.key == key:
            return c.value
    return default


@router.post("/{instance_name}")
async def receive_webhook(instance_name: str, request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.json()
    event = payload.get("event", "")

    if event == "qrcode.updated":
        data = payload.get("data", {})
        qr_data = data.get("qrcode", {})
        code = qr_data.get("base64") or qr_data.get("code") or data.get("base64")
        if code and not code.startswith("data:"):
            import qrcode, io, base64 as b64mod
            img = qrcode.make(code)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            code = "data:image/png;base64," + b64mod.b64encode(buf.getvalue()).decode()
        if code:
            qr_store.set_qr(instance_name, code)
        return {"ok": True}

    if event != "messages.upsert":
        return {"ok": True}

    data = payload.get("data", {})
    key = data.get("key", {})

    if key.get("fromMe"):
        return {"ok": True}

    remote_jid = key.get("remoteJid", "")
    phone = remote_jid.replace("@s.whatsapp.net", "").replace("@g.us", "")

    message_obj = data.get("message", {})
    text = (
        message_obj.get("conversation")
        or message_obj.get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()

    if not text:
        return {"ok": True}

    push_name = data.get("pushName")

    channel = (await db.execute(
        select(Channel).where(Channel.instance_name == instance_name)
    )).scalar_one_or_none()

    if not channel:
        logger.warning(f"Webhook recebido de instância desconhecida: {instance_name}")
        return {"ok": True}

    lead = (await db.execute(
        select(Lead).where(Lead.phone == phone, Lead.channel_id == channel.id)
    )).scalar_one_or_none()

    if not lead:
        lead = Lead(channel_id=channel.id, phone=phone, name=push_name)
        db.add(lead)
        await db.flush()

    lead.last_message_at = datetime.now(UTC)
    if push_name and not lead.name:
        lead.name = push_name

    db.add(Message(lead_id=lead.id, direction=MessageDirection.inbound, content=text))
    await db.flush()

    messages_rows = (await db.execute(
        select(Message).where(Message.lead_id == lead.id).order_by(Message.created_at).limit(MAX_HISTORY)
    )).scalars().all()

    history = [
        {"role": "user" if m.direction == MessageDirection.inbound else "assistant", "content": m.content}
        for m in messages_rows
    ]

    configs = (await db.execute(select(AgentConfig))).scalars().all()
    business_context = _cfg(configs, "business_context", "Empresa do setor comercial")
    criteria = _cfg(configs, "qualification_criteria", "")
    agent_prompt = _cfg(configs, "agent_prompt", "")

    try:
        qual = await qa.qualify(history, business_context, criteria)
    except Exception as e:
        logger.error(f"Erro na qualificação: {e}")
        await db.commit()
        return {"ok": True}

    status_map = {"hot": LeadStatus.hot, "warm": LeadStatus.warm, "cold": LeadStatus.cold}
    lead.status = status_map.get(qual.get("status", "warm"), LeadStatus.warm)

    collected = qual.get("collected", {})
    if collected.get("name") and not lead.name:
        lead.name = collected["name"]
    if collected.get("email") and not lead.email:
        lead.email = collected["email"]
    if collected.get("city") and not lead.city:
        lead.city = collected["city"]
    if collected.get("budget") and not lead.budget:
        lead.budget = collected["budget"]
    if collected.get("project_type") and not lead.project_type:
        lead.project_type = collected["project_type"]
    if collected.get("interest") and not lead.interest:
        lead.interest = collected["interest"]

    try:
        reply = await ra.generate_response(
            history=history,
            next_question=qual.get("next_question"),
            lead_status=qual.get("status", "warm"),
            agent_prompt=agent_prompt,
            business_context=business_context,
        )
        db.add(Message(lead_id=lead.id, direction=MessageDirection.outbound, content=reply))
        try:
            await send_text(instance_name, phone, reply)
        except Exception as e:
            logger.error(f"Erro ao enviar WhatsApp (mensagem salva): {e}")
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {e}")

    await db.commit()

    return {"ok": True}
