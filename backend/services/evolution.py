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


async def delete_instance(instance_name: str):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{BASE}/instance/delete/{instance_name}", headers=HEADERS)
