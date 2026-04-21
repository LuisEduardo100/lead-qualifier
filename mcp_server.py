"""
MCP Server — Lead Qualifier
Expõe ferramentas para inspeção e controle de leads via Claude Code.
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from sqlalchemy import select
from backend.database import SessionLocal, init_db
from backend.models import Lead, Message, Channel, AgentConfig

server = Server("lead-qualifier-mcp")


@server.list_tools()
async def list_tools():
    return [
        types.Tool(name="list_leads", description="Lista todos os leads com status e dados",
                   inputSchema={"type": "object", "properties": {"status": {"type": "string", "description": "Filtrar por status: hot, warm, cold, new, lost"}}}),
        types.Tool(name="get_conversation", description="Retorna histórico completo de conversa de um lead",
                   inputSchema={"type": "object", "required": ["lead_id"], "properties": {"lead_id": {"type": "integer"}}}),
        types.Tool(name="update_lead_status", description="Atualiza manualmente o status de um lead",
                   inputSchema={"type": "object", "required": ["lead_id", "status"], "properties": {"lead_id": {"type": "integer"}, "status": {"type": "string"}}}),
        types.Tool(name="get_pipeline_summary", description="Resumo do pipeline: contagem por status",
                   inputSchema={"type": "object", "properties": {}}),
        types.Tool(name="get_config", description="Retorna configurações atuais do agente",
                   inputSchema={"type": "object", "properties": {}}),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    await init_db()

    async with SessionLocal() as db:
        if name == "list_leads":
            q = select(Lead).order_by(Lead.last_message_at.desc())
            if arguments.get("status"):
                q = q.where(Lead.status == arguments["status"])
            leads = (await db.execute(q)).scalars().all()
            result = [{"id": l.id, "phone": l.phone, "name": l.name, "status": l.status,
                       "interest": l.interest, "city": l.city, "last_message": l.last_message_at.isoformat()} for l in leads]
            return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        if name == "get_conversation":
            lead = (await db.execute(select(Lead).where(Lead.id == arguments["lead_id"]))).scalar_one_or_none()
            if not lead:
                return [types.TextContent(type="text", text="Lead não encontrado")]
            msgs = [{"direction": m.direction, "content": m.content, "at": m.created_at.isoformat()} for m in lead.messages]
            return [types.TextContent(type="text", text=json.dumps({"lead": lead.name or lead.phone, "status": lead.status, "messages": msgs}, ensure_ascii=False, indent=2))]

        if name == "update_lead_status":
            lead = (await db.execute(select(Lead).where(Lead.id == arguments["lead_id"]))).scalar_one_or_none()
            if not lead:
                return [types.TextContent(type="text", text="Lead não encontrado")]
            lead.status = arguments["status"]
            await db.commit()
            return [types.TextContent(type="text", text=f"Status atualizado para {arguments['status']}")]

        if name == "get_pipeline_summary":
            leads = (await db.execute(select(Lead))).scalars().all()
            summary = {}
            for l in leads:
                summary[l.status] = summary.get(l.status, 0) + 1
            return [types.TextContent(type="text", text=json.dumps(summary, ensure_ascii=False))]

        if name == "get_config":
            configs = (await db.execute(select(AgentConfig))).scalars().all()
            return [types.TextContent(type="text", text=json.dumps({c.key: c.value for c in configs}, ensure_ascii=False, indent=2))]

    return [types.TextContent(type="text", text="Ferramenta desconhecida")]


async def main():
    async with stdio_server() as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
