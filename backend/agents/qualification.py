import json
from groq import AsyncGroq
from backend.config import get_settings

settings = get_settings()
client = AsyncGroq(api_key=settings.groq_api_key)

SYSTEM = """Você é um analisador de leads para uma empresa do setor comercial.

Analise o histórico de conversa e retorne um JSON com:
- status: "hot" | "warm" | "cold"
- next_question: pergunta para coletar dados faltantes (null se lead já qualificado ou cold)
- collected: objeto com campos coletados {name, email, city, budget, project_type, interest}
- reasoning: motivo da classificação (1 frase curta)

Critérios:
- HOT: lead sabe exatamente o que quer, menciona produto/aplicação específica, demonstra intenção real de compra
- WARM: demonstra interesse mas com informações vagas — precisa de qualificação ativa
- COLD: fora do nicho da empresa, sem interesse real mesmo após tentativas, ou apenas curiosidade superficial

Dados a coletar progressivamente (pergunte 1 por vez):
- Quando WARM: nome, cidade, produto de interesse, orçamento estimado, tipo de projeto (residencial/comercial/industrial)
- Quando HOT apenas: email — use o contexto de fidelização: "para te incluir em nossas ofertas exclusivas e lançamentos". NUNCA peça email se o lead ainda não for hot.

Retorne APENAS o JSON, sem texto adicional."""


async def qualify(
    history: list[dict],
    business_context: str,
    criteria: str,
) -> dict:
    messages = [
        {"role": "system", "content": f"{SYSTEM}\n\nContexto da empresa: {business_context}\nCritérios adicionais: {criteria}"},
        *history,
    ]

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.1,
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {"status": "warm", "next_question": None, "collected": {}, "reasoning": "erro na análise"}
