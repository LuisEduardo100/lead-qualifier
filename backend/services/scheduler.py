import json
import logging
from datetime import datetime, UTC, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from backend.database import SessionLocal
from backend.models import Lead, LeadStatus, FollowUpLog, AgentConfig, Message

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def _get_config(configs: list, key: str, default: str) -> str:
    for c in configs:
        if c.key == key:
            return c.value
    return default


async def _run_followups():
    from backend.agents.followup import generate_followup_context
    from backend.services.email_service import send_followup_email

    now = datetime.now(UTC)

    async with SessionLocal() as db:
        configs = (await db.execute(select(AgentConfig))).scalars().all()
        company_name = _get_config(configs, "company_name", "Nossa Empresa")
        whatsapp_number = _get_config(configs, "whatsapp_number", "")
        products_raw = _get_config(configs, "featured_products", "[]")
        try:
            products = json.loads(products_raw)
        except Exception:
            products = []

        leads = (await db.execute(
            select(Lead).where(
                Lead.status.in_([LeadStatus.warm, LeadStatus.hot]),
                Lead.email.isnot(None),
            )
        )).scalars().all()

        for lead in leads:
            days_silent = (now - lead.last_message_at.replace(tzinfo=UTC)).days
            followup_count = len(lead.followups)

            if followup_count == 0 and days_silent >= 3:
                attempt = 1
            elif followup_count == 1 and days_silent >= 10:
                attempt = 2
            else:
                continue

            history = [
                {"role": "user" if m.direction == "inbound" else "assistant", "content": m.content}
                for m in lead.messages[-20:]
            ]

            try:
                context_msg = await generate_followup_context(history, attempt)
                await send_followup_email(
                    to_email=lead.email,
                    lead_name=lead.name,
                    context_message=context_msg,
                    company_name=company_name,
                    products=products,
                    whatsapp_number=whatsapp_number,
                )
                db.add(FollowUpLog(lead_id=lead.id, attempt=attempt))
                await db.commit()
                logger.info(f"Follow-up #{attempt} enviado para lead {lead.id}")
            except Exception as e:
                logger.error(f"Erro no follow-up lead {lead.id}: {e}")


def start_scheduler():
    scheduler.add_job(_run_followups, "interval", hours=6, id="followup_job", replace_existing=True)
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown()
