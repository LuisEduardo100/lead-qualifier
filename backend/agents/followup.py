from groq import AsyncGroq
from backend.config import get_settings

settings = get_settings()
client = AsyncGroq(api_key=settings.groq_api_key)

SYSTEM = """Você é um consultor comercial. Com base no histórico de conversa com um lead que não respondeu,
gere UMA frase personalizada (máx 2 linhas) que retome a conexão de forma natural e humana.
Sem saudações genéricas. Mencione algo específico da conversa anterior.
Retorne apenas a frase, sem aspas."""


async def generate_followup_context(history: list[dict], attempt: int) -> str:
    urgency = " Crie um senso leve de urgência sem pressionar." if attempt == 2 else ""
    messages = [
        {"role": "system", "content": SYSTEM + urgency},
        *history[-6:],
        {"role": "user", "content": "Gere a frase de retomada para o email de follow-up."},
    ]

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.8,
        max_tokens=150,
    )

    return response.choices[0].message.content.strip()
