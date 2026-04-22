import logging
from groq import AsyncGroq
from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
client = AsyncGroq(api_key=settings.groq_api_key)

DEFAULT_SYSTEM = """Você é um consultor comercial humano via WhatsApp. NUNCA revele que é IA.
Tom: direto, informal, como mensagem de WhatsApp real."""


async def generate_response(
    history: list[dict],
    next_question: str | None,
    lead_status: str,
    agent_prompt: str,
    business_context: str = "",
    max_tokens: int = 40,
    temperature: float = 0.7,
    brevity_rule: str = "",
    catalog_chunks: list[str] | None = None,
    has_catalog: bool = False,
    catalog_already_sent: bool = False,
) -> str:
    system = agent_prompt or DEFAULT_SYSTEM
    if business_context:
        system += f"\n\nContexto do negócio: {business_context}"
    if catalog_chunks:
        catalog_text = "\n---\n".join(catalog_chunks)
        system += f"\n\nInformações do catálogo de produtos (use para responder perguntas sobre produtos/serviços):\n{catalog_text}"
    if has_catalog:
        system += "\n\nO catálogo PDF está sendo enviado automaticamente agora. Confirme brevemente que está enviando."
    elif catalog_already_sent:
        system += "\n\nO catálogo já foi enviado anteriormente nesta conversa. Se o usuário pedir de novo, diga que já enviou e peça para verificar as mensagens anteriores."
    if brevity_rule:
        system += f"\n\n{brevity_rule}"

    instruction = ""
    if next_question:
        instruction = f"\n\nPergunte apenas: {next_question}"
    elif lead_status == "hot":
        instruction = "\n\nLead quente. Proponha um único próximo passo."
    elif lead_status == "cold":
        instruction = "\n\nFora do nicho. Encerre com cordialidade."

    messages = [
        {"role": "system", "content": system + instruction},
        *history,
    ]

    # Reserve extra tokens for [ENVIAR_CATALOGO] marker so it isn't truncated
    effective_max_tokens = max_tokens + 15 if has_catalog else max_tokens
    logger.info(f"[generate_response] max_tokens={effective_max_tokens} temperature={temperature} system_preview={system[:80]!r}")
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=temperature,
        max_tokens=effective_max_tokens,
    )

    choice = response.choices[0]
    raw = choice.message.content or ""
    finish = choice.finish_reason
    reply = raw.strip()
    logger.info(f"[generate_response] finish_reason={finish!r} raw={raw!r} reply={reply!r}")
    return reply
