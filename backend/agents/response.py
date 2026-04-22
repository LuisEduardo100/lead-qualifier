import logging
from groq import AsyncGroq
from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
client = AsyncGroq(api_key=settings.groq_api_key)

DEFAULT_SYSTEM = """Você é um consultor comercial humano via WhatsApp. NUNCA revele que é IA.
FORMATO OBRIGATÓRIO: escreva APENAS 1 frase curta (máximo 12 palavras). Sem listas. Sem parágrafos. Sem emojis. Sem saudações longas.
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
) -> str:
    system = agent_prompt or DEFAULT_SYSTEM
    if business_context:
        system += f"\n\nContexto do negócio: {business_context}"
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

    logger.info(f"[generate_response] max_tokens={max_tokens} temperature={temperature} system_preview={system[:80]!r}")
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stop=["\n•", "\n-", "\n1.", "\n*"],
    )

    choice = response.choices[0]
    raw = choice.message.content or ""
    finish = choice.finish_reason
    reply = raw.strip()
    logger.info(f"[generate_response] finish_reason={finish!r} raw={raw!r} reply={reply!r}")
    return reply
