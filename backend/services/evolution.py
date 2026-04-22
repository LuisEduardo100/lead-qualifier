import asyncio
import httpx
from backend.config import get_settings

settings = get_settings()

HEADERS = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}
BASE = settings.evolution_api_url


async def create_instance(instance_name: str, webhook_url: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/instance/create", headers=HEADERS, json={
            "instanceName": instance_name,
            "integration": "WHATSAPP-BAILEYS",
            "webhook": {"url": webhook_url, "enabled": True,
                        "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE", "QRCODE_UPDATED"]},
        })
        r.raise_for_status()
        return r.json()


async def create_business_instance(
    instance_name: str,
    webhook_url: str,
    token: str,
    number: str,
    business_id: str,
) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/instance/create", headers=HEADERS, json={
            "instanceName": instance_name,
            "integration": "WHATSAPP-BUSINESS",
            "token": token,
            "number": number,
            "businessId": business_id,
            "qrcode": False,
            "webhook": {
                "url": webhook_url,
                "enabled": True,
                "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
            },
        })
        r.raise_for_status()
        return r.json()


async def trigger_connect(instance_name: str):
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE}/instance/connect/{instance_name}", headers=HEADERS)


async def get_connection_state(instance_name: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/instance/connectionState/{instance_name}", headers=HEADERS)
        if r.status_code == 404:
            return "not_found"
        data = r.json()
        return data.get("instance", {}).get("state", "unknown")


async def resolve_lid_jid(instance_name: str, push_name: str) -> str | None:
    import logging
    logger = logging.getLogger(__name__)
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE}/contact/findContacts/{instance_name}",
            headers=HEADERS,
            params={"query": push_name},
        )
        if r.status_code != 200:
            logger.warning(f"findContacts {r.status_code}: {r.text}")
            return None
        contacts = r.json()
        logger.info(f"findContacts result: {contacts}")
        if isinstance(contacts, list) and contacts:
            return contacts[0].get("id")
        return None


async def send_text(instance_name: str, phone: str, text: str) -> dict:
    import logging
    logger = logging.getLogger(__name__)
    if "@" in phone:
        number = phone
    else:
        number = phone.replace("+", "").replace(" ", "").replace("-", "")
    logger.info(f"send_text → instance={instance_name} number={number}")
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/message/sendText/{instance_name}", headers=HEADERS,
                              json={"number": number, "text": text})
        if not r.is_success:
            logger.error(f"Evolution API {r.status_code}: {r.text}")
        r.raise_for_status()
        return r.json()


async def _send_typing(instance_name: str, number: str):
    import logging
    logger = logging.getLogger(__name__)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{BASE}/chat/updatePresence/{instance_name}",
                headers=HEADERS,
                json={"number": number, "presence": "composing"},
            )
    except Exception as e:
        logger.warning(f"send_typing failed: {e}")


async def send_text_human(instance_name: str, phone: str, text: str):
    """Split text into sentences and send each with a typing indicator + realistic delay."""
    import re
    import logging
    logger = logging.getLogger(__name__)

    number = phone if "@" in phone else phone.replace("+", "").replace(" ", "").replace("-", "")
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    if not sentences:
        sentences = [text]

    for i, sentence in enumerate(sentences):
        await _send_typing(instance_name, number)
        delay = min(len(sentence) * 0.045, 2.5)
        await asyncio.sleep(delay)
        try:
            await send_text(instance_name, phone, sentence)
        except Exception as e:
            logger.error(f"send_text_human chunk failed: {e}")
            raise
        if i < len(sentences) - 1:
            await asyncio.sleep(0.4)


async def download_media_base64(instance_name: str, message_key: dict, message_obj: dict | None = None) -> str | None:
    import logging
    logger = logging.getLogger(__name__)
    # Evolution API expects WAMessage wrapped inside {"message": {...}, "convertToMp4": false}
    wa_message: dict = {"key": message_key}
    if message_obj:
        wa_message["message"] = message_obj
    body = {"message": wa_message, "convertToMp4": False}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{BASE}/chat/getBase64FromMediaMessage/{instance_name}",
                headers=HEADERS,
                json=body,
            )
            logger.info(f"download_media_base64 status={r.status_code} body_preview={r.text[:300]}")
            if r.is_success:
                data = r.json()
                return data.get("base64") or data.get("data", {}).get("base64")
    except Exception as e:
        logger.warning(f"download_media_base64 failed: {e}")
    return None


async def fetch_instance_info(instance_name: str) -> dict:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(
            f"{BASE}/instance/fetchInstances",
            headers=HEADERS,
            params={"instanceName": instance_name},
        )
        if r.status_code != 200:
            return {}
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
        return {}


async def logout_instance(instance_name: str):
    """Log out from WhatsApp without deleting the instance (preserves leads/metrics)."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.delete(f"{BASE}/instance/logout/{instance_name}", headers=HEADERS)
            if not r.is_success:
                logger.warning(f"logout_instance {r.status_code}: {r.text}")
    except Exception as e:
        logger.warning(f"logout_instance failed (instance may already be disconnected): {e}")


async def delete_instance(instance_name: str):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{BASE}/instance/delete/{instance_name}", headers=HEADERS)


async def send_document(instance_name: str, phone: str, file_path: str, filename: str, caption: str = "") -> dict:
    """Send a PDF document via Evolution API using base64 encoding."""
    import base64
    import logging
    logger = logging.getLogger(__name__)

    number = phone if "@" in phone else phone.replace("+", "").replace(" ", "").replace("-", "")

    with open(file_path, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "number": number,
        "mediatype": "document",
        "mimetype": "application/pdf",
        "media": file_b64,
        "fileName": filename,
    }
    if caption:
        payload["caption"] = caption

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE}/message/sendMedia/{instance_name}",
            headers=HEADERS,
            json=payload,
        )
        if not r.is_success:
            logger.error(f"send_document {r.status_code}: {r.text}")
        r.raise_for_status()
        return r.json()
