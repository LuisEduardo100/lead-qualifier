import io
import base64 as b64mod
import logging
from fastapi import APIRouter, Request, Depends, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, UTC
from backend.database import get_db
from backend.models import Channel, Lead, Message, AgentConfig, LeadStatus, MessageDirection
from backend.agents import qualification as qa, response as ra
from backend.services.evolution import send_text_human, download_media_base64
from backend import qr_store
from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])
settings = get_settings()

MAX_HISTORY = 20


def _cfg(configs, key, default=""):
    for c in configs:
        if c.key == key:
            return c.value
    return default


def _normalize_number(phone: str) -> str:
    if "@" in phone:
        return phone
    return phone.replace("+", "").replace(" ", "").replace("-", "")


async def _transcribe_audio(audio_b64: str) -> str:
    from groq import AsyncGroq
    client = AsyncGroq(api_key=settings.groq_api_key)
    audio_bytes = b64mod.b64decode(audio_b64)
    transcription = await client.audio.transcriptions.create(
        file=("audio.ogg", io.BytesIO(audio_bytes)),
        model="whisper-large-v3",
        language="pt",
    )
    text = transcription.text.strip()
    logger.info(f"[whisper] transcript={text!r}")
    return text


async def _describe_image(image_b64: str, caption: str = "") -> str:
    from groq import AsyncGroq
    client = AsyncGroq(api_key=settings.groq_api_key)
    content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        {"type": "text", "text": "Descreva em 1 frase o que está nesta imagem, em português."},
    ]
    r = await client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": content}],
        max_tokens=80,
    )
    desc = r.choices[0].message.content.strip()
    return f"[Imagem: {desc}]" + (f" {caption}" if caption else "")


async def _extract_message(message_obj: dict, instance_name: str, key: dict) -> tuple[str, str | None, str | None]:
    """Returns (text_for_history, media_type, thumbnail_base64_or_none)."""

    # Plain text
    text = (
        message_obj.get("conversation")
        or message_obj.get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()
    if text:
        return text, None, None

    # Audio / PTT
    if message_obj.get("audioMessage") or message_obj.get("pttMessage"):
        audio_b64 = await download_media_base64(instance_name, key, message_obj)
        if audio_b64:
            try:
                transcript = await _transcribe_audio(audio_b64)
                return transcript, "audio", None
            except Exception as e:
                logger.error(f"Whisper transcription failed: {e}")
        # Download or transcription failed — return empty so the webhook sends a friendly fallback
        return "", "audio", None

    # Image
    if message_obj.get("imageMessage"):
        img = message_obj["imageMessage"]
        caption = img.get("caption", "")
        thumbnail = img.get("jpegThumbnail", "")
        full_b64 = await download_media_base64(instance_name, key, message_obj)
        if full_b64:
            try:
                desc = await _describe_image(full_b64, caption)
                return desc, "image", thumbnail or None
            except Exception as e:
                logger.error(f"Image vision failed: {e}")
        return caption or "[Imagem]", "image", thumbnail or None

    # Document (PDF, Word, etc.)
    if message_obj.get("documentMessage") or message_obj.get("documentWithCaptionMessage"):
        doc = (
            message_obj.get("documentMessage")
            or message_obj.get("documentWithCaptionMessage", {}).get("message", {}).get("documentMessage", {})
        )
        filename = doc.get("fileName") or doc.get("title") or "documento"
        caption = doc.get("caption", "")
        content_text = f"[Documento: {filename}]" + (f" {caption}" if caption else "")
        return content_text, "document", None

    # Sticker / reaction / other — skip
    return "", None, None


@router.post("/{instance_name}")
async def receive_webhook(
    instance_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()
    event = payload.get("event", "")

    if event == "qrcode.updated":
        data = payload.get("data", {})
        qr_data = data.get("qrcode", {})
        code = qr_data.get("base64") or qr_data.get("code") or data.get("base64")
        if code and not code.startswith("data:"):
            import qrcode as qrlib
            buf = io.BytesIO()
            qrlib.make(code).save(buf, format="PNG")
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
    if remote_jid.endswith("@g.us"):
        return {"ok": True}

    push_name = data.get("pushName")
    remote_jid_alt = key.get("remoteJidAlt", "")
    if remote_jid.endswith("@lid") and remote_jid_alt:
        reply_jid = remote_jid_alt
        phone = remote_jid_alt.split("@")[0]
    else:
        reply_jid = remote_jid
        phone = remote_jid.split("@")[0]

    message_obj = data.get("message", {})
    text, media_type, media_url = await _extract_message(message_obj, instance_name, key)

    if not text and media_type != "audio":
        return {"ok": True}

    # Audio received but could not be transcribed — ask user to type
    if not text and media_type == "audio":
        background_tasks.add_task(
            send_text_human, instance_name, reply_jid,
            "Não consegui ouvir o áudio. Pode digitar sua mensagem?"
        )
        return {"ok": True}

    channel = (await db.execute(
        select(Channel).where(Channel.instance_name == instance_name)
    )).scalar_one_or_none()

    if not channel:
        logger.warning(f"Webhook de instância desconhecida: {instance_name}")
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

    db.add(Message(
        lead_id=lead.id,
        direction=MessageDirection.inbound,
        content=text,
        media_type=media_type,
        media_url=media_url,
    ))
    await db.commit()

    if lead.agent_paused:
        return {"ok": True}

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
    max_tokens = int(_cfg(configs, "max_tokens", "30"))
    temperature = float(_cfg(configs, "temperature", "0.7"))
    brevity_rule = _cfg(configs, "brevity_rule", "")

    try:
        qual = await qa.qualify(history, business_context, criteria)
    except Exception as e:
        logger.error(f"Erro na qualificação: {e}")
        await db.commit()
        return {"ok": True}

    status_map = {"hot": LeadStatus.hot, "warm": LeadStatus.warm, "cold": LeadStatus.cold}
    lead.status = status_map.get(qual.get("status", "warm"), LeadStatus.warm)

    collected = qual.get("collected", {})
    for field in ("name", "email", "city", "budget", "project_type", "interest"):
        if collected.get(field) and not getattr(lead, field):
            setattr(lead, field, collected[field])

    try:
        reply = await ra.generate_response(
            history=history,
            next_question=qual.get("next_question"),
            lead_status=qual.get("status", "warm"),
            agent_prompt=agent_prompt,
            business_context=business_context,
            max_tokens=max_tokens,
            temperature=temperature,
            brevity_rule=brevity_rule,
        )
        if not reply:
            logger.warning("[webhook] LLM returned empty reply — skipping send")
            await db.commit()
            return {"ok": True}
        db.add(Message(lead_id=lead.id, direction=MessageDirection.outbound, content=reply))
        await db.commit()
        background_tasks.add_task(send_text_human, instance_name, reply_jid, reply)
    except Exception as e:
        logger.error(f"Erro ao gerar/enviar resposta: {e}")
        await db.commit()

    return {"ok": True}
