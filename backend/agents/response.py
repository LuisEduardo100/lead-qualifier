from groq import AsyncGroq
from backend.config import get_settings

settings = get_settings()
client = AsyncGroq(api_key=settings.groq_api_key)

DEFAULT_SYSTEM = """Você é um consultor comercial humano. NUNCA revele que é uma IA.
Tom: consultivo, amigável, linguagem natural. Respostas curtas e diretas.
Foque em entender a necessidade do cliente e avançar para a venda."""


async def generate_response(
    history: list[dict],
    next_question: str | None,
    lead_status: str,
    agent_prompt: str,
    business_context: str = "",
) -> str:
    system = agent_prompt or DEFAULT_SYSTEM
    if business_context:
        system += f"\n\nContexto do negócio: {business_context}"

    instruction = ""
    if next_question:
        instruction = f"\n\nSua próxima ação: pergunte de forma natural — {next_question}"
    elif lead_status == "hot":
        instruction = "\n\nLead quente! Proponha um próximo passo concreto: agendamento, envio de proposta ou demonstração."
    elif lead_status == "cold":
        instruction = "\n\nEste lead está fora do nosso nicho de atuação. Seja cordial, explique brevemente o que nossa empresa oferece e encerre com gentileza. NÃO confirme que vendemos produtos fora do nosso portfólio."

    messages = [
        {"role": "system", "content": system + instruction},
        *history,
    ]

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.7,
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()
