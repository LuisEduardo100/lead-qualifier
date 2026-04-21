from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models import AgentConfig
from backend.auth import get_current_user

router = APIRouter(prefix="/api/config", tags=["config"])

DEFAULTS = {
    "agent_prompt": "Você é um consultor comercial. Seja amigável, consultivo e direto. NUNCA revele que é uma IA.",
    "agent_name": "Carlos",
    "business_context": "Empresa do setor comercial especializada em soluções para clientes B2B e B2C.",
    "qualification_criteria": "Hot: cliente sabe o que quer. Warm: interesse vago. Cold: fora do nicho.",
    "company_name": "Minha Empresa",
    "whatsapp_number": "",
    "featured_products": '[{"name":"Produto A","description":"Descrição breve"},{"name":"Produto B","description":"Descrição breve"}]',
    "followup_template_1": "Olá! Passando para saber se ainda posso ajudá-lo com o que conversamos.",
    "followup_template_2": "Última tentativa de contato — ainda temos ótimas condições para você.",
}


@router.get("")
async def get_config(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    rows = (await db.execute(select(AgentConfig))).scalars().all()
    result = dict(DEFAULTS)
    for r in rows:
        result[r.key] = r.value
    return result


@router.put("")
async def update_config(body: dict, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    for key, value in body.items():
        row = (await db.execute(select(AgentConfig).where(AgentConfig.key == key))).scalar_one_or_none()
        if row:
            row.value = str(value)
        else:
            db.add(AgentConfig(key=key, value=str(value)))
    await db.commit()
    return {"ok": True}
