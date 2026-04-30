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
- WARM: demonstra interesse mesmo que vago, ou ainda não foi qualificado — precisa de qualificação ativa. Este é o DEFAULT.
- COLD: apenas em DOIS cenários estritos:
  1. Lead pede explicitamente produto/serviço comprovadamente fora do nicho da empresa (ex: "vocês vendem cimento?" para empresa de iluminação).
  2. Após pelo menos 3 mensagens INBOUND do lead, ele continuou sem demonstrar qualquer intenção/interesse mesmo após tentativas claras de qualificação.

REGRAS CRÍTICAS DE CLASSIFICAÇÃO (siga à risca):
- Conte apenas mensagens com role="user" do histórico. Se houver MENOS DE 3 mensagens user, NUNCA retorne "cold" — retorne "warm" e use next_question para qualificar.
- Reações curtas isoladas ("kkkk", "🤣", "ok", "uhum", "rs", emojis sozinhos) NÃO são fora-do-nicho — pergunte algo concreto antes de classificar.
- Saudações vagas ("oi", "boa tarde", "bom dia", "tudo bem?") são WARM por padrão, nunca cold.
- Mensagens claramente off-topic mas não-comerciais (ex: "que horas são?", "vou sair") em primeira ou segunda mensagem ainda são WARM — redirecione para qualificar.
- Só marque cold se houver evidência clara: pedido explícito de produto fora do nicho OU desinteresse persistente em 3+ mensagens.

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
