# Pitch — Lead Qualifier

## A Dor Real

A demora no primeiro contato está matando as taxas de conversão. Um estudo amplamente citado pela **Harvard Business Review** (baseado em dados do MIT e InsideSales) estabeleceu a "Regra dos 5 Minutos": as chances de conseguir qualificar um lead caem **21 vezes** se a empresa demorar 30 minutos para responder em vez de 5 minutos. Além disso, cerca de **78% dos clientes** fecham negócio com a primeira empresa que os atende.

No Brasil, a urgência é ainda maior. Segundo o relatório panorama mensageria da **Mobile Time/Opinion Box**, o WhatsApp está presente em **99% dos smartphones**, e o consumidor exige respostas em tempo real nesse canal. 

No entanto, o atendimento humano gera gargalos: depende de vendedores que têm horário comercial limitado, demoram a responder quando há pico de demanda e fazem perguntas de qualificação de forma inconsistente.

O resultado prático:
- Lead chega às 21h por um anúncio, ninguém responde até o dia seguinte. A intenção de compra despenca e ele já foi atendido pela concorrência.
- Vendedores (SDRs e Closers) desperdiçam a maior parte do dia respondendo as mesmas dúvidas básicas para leads curiosos que nunca vão comprar.
- Não há rastreabilidade — o histórico das conversas e os dados dos clientes ficam "sequestrados" no celular do vendedor, sem ir para o CRM.

---

## A Solução

**Lead Qualifier** é um agente de IA que atende leads via WhatsApp 24/7, qualifica automaticamente o interesse e coleta os dados necessários para o time comercial fechar a venda.

O agente:
1. Responde imediatamente como um consultor humano (delay realista, linguagem natural)
2. Classifica o lead como `hot`, `warm`, `cold` ou `new` a cada mensagem
3. Coleta progressivamente: nome, cidade, produto de interesse, orçamento, tipo de projeto, e-mail
4. Usa o catálogo de produtos da empresa como base de conhecimento (RAG)
5. Envia o PDF do catálogo automaticamente quando solicitado
6. Dispara follow-ups para leads que pararam de responder
7. Entrega o lead qualificado para o vendedor humano no momento certo

O vendedor só entra quando o lead já está quente e com dados coletados.

---

## Área de Negócio

**Comercial / Vendas** — qualquer empresa que gera leads via WhatsApp e depende de atendimento consultivo para fechar vendas. Exemplos diretos: lojas de iluminação, arquitetura e decoração, clínicas, imobiliárias, cursos, serviços B2C de ticket médio.

---

## Ganhos Mensuráveis

| Métrica | Antes | Depois |
|---|---|---|
| Tempo de primeiro contato | Horas (ou dias) | Imediato, 24/7 |
| Taxa de qualificação manual | 100% do tempo do vendedor | 0% para leads cold/new |
| Dados coletados por lead | Incompletos, no celular | 100% no sistema, estruturados |
| Follow-up de leads esquecidos | Raramente acontece | Automático, 2 tentativas |
| Capacidade de atendimento simultâneo | 1 vendedor = ~5 chats | Ilimitado |

---

## Por que Claude Code?

O agente foi construído do zero usando **Claude Code** como ferramenta principal de desenvolvimento — desde a arquitetura inicial até os testes e documentação. O fluxo incluiu:

- Geração e iteração dos prompts do agente de qualificação e de resposta
- Implementação do pipeline RAG (extração de PDF, embeddings, busca semântica)
- Criação de testes automatizados (80 testes cobrindo todos os módulos)
- Exposição de um **MCP Server** para que o Claude Code possa inspecionar e controlar o pipeline de leads diretamente pelo terminal

O MCP Server permite comandos como:
```
"Liste os leads quentes de hoje"
"Mostre o histórico do lead 42"
"Qual é o resumo do pipeline atual?"
```

Isso fecha o ciclo: a IA não só atende os leads — ela também pode ser consultada pelo time para analisar o próprio pipeline.

---

## Como Auxilia no Dia a Dia de uma Empresa

- **Time comercial**: acorda com uma lista de leads já qualificados e dados coletados, foca energia em fechar — não em prospectar ou perguntar "qual é seu orçamento?" pela décima vez
- **Gestor**: dashboard em tempo real com status de cada lead, sem depender de relatório manual do vendedor
- **Marketing**: sabe quais leads converteram de cada campanha, ajusta verba com dados reais
- **Operação**: follow-ups e envio de catálogo acontecem sem intervenção humana, reduzindo carga operacional
