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
                        "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]},
        })
        r.raise_for_status()
        return r.json()


async def get_qrcode(instance_name: str) -> dict:
    async with httpx.AsyncClient() as client:
        data = {}
        for _ in range(10):
            r = await client.get(f"{BASE}/instance/connect/{instance_name}", headers=HEADERS)
            r.raise_for_status()
            data = r.json()
            if data.get("base64") or data.get("qrcode", {}).get("base64"):
                return data
            await asyncio.sleep(1)
        return data


async def get_connection_state(instance_name: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/instance/connectionState/{instance_name}", headers=HEADERS)
        if r.status_code == 404:
            return "not_found"
        data = r.json()
        return data.get("instance", {}).get("state", "unknown")


async def send_text(instance_name: str, phone: str, text: str) -> dict:
    number = phone.replace("+", "").replace(" ", "").replace("-", "")
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/message/sendText/{instance_name}", headers=HEADERS,
                              json={"number": number, "text": text})
        r.raise_for_status()
        return r.json()


async def delete_instance(instance_name: str):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{BASE}/instance/delete/{instance_name}", headers=HEADERS)
