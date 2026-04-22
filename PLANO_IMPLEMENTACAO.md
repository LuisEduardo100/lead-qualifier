# Plano de Implementação em Produção

## Visão Geral

Implantação do Lead Qualifier em uma empresa de médio porte com 1 a 3 canais de WhatsApp ativos, integrando ao fluxo comercial existente em **6 semanas**.

---

## Cronograma de Integrações

### Semana 1 — Infraestrutura e Configuração Base
- Provisionar VPS (mín. 4 GB RAM, 2 vCPUs)
- Configurar Docker Compose: Evolution API + backend FastAPI
- Apontar domínio e configurar HTTPS (Nginx + Let's Encrypt)
- Criar variáveis de ambiente (Groq API Key, Evolution API Key, SECRET_KEY)
- Criar usuário admin e testar acesso ao dashboard

### Semana 2 — Conexão WhatsApp e Validação
- Criar canal Baileys e escanear QR Code com número de atendimento
- Enviar mensagens de teste e validar webhook recebendo corretamente
- Configurar prompt do agente, contexto do negócio e critérios de qualificação
- Fazer upload do catálogo de produtos (PDF) e validar busca semântica

### Semana 3 — Piloto Interno
- Equipe interna simula leads com diferentes perfis (hot, warm, cold)
- Ajustar prompt com base nos erros de classificação observados
- Calibrar delay de digitação para o perfil do público
- Testar fluxo completo: nova mensagem → qualificação → resposta → follow-up

### Semana 4 — Soft Launch
- Direcionar 10–20% dos leads novos para o canal com o agente
- Monitorar classificações no dashboard diariamente
- Coletar feedback dos vendedores sobre qualidade dos leads entregues
- Ajustar critérios de qualificação com base nos dados reais

### Semana 5 — Expansão e Campanhas
- Migrar 100% do volume de leads para o agente
- Criar primeiro canal WhatsApp Business (API oficial) para campanhas
- Segmentar base existente e disparar primeira campanha de reativação
- Treinar vendedores no uso do dashboard e do pause/resume do agente

### Semana 6 — Estabilização e Handoff
- Configurar monitoramento de logs (alertas de erro no container)
- Documentar procedimentos de operação para o time interno
- Definir SLA de revisão mensal do prompt do agente
- Avaliar integração com CRM (se houver) via API REST

---

## Planejamento de Custos

### Infraestrutura (mensal recorrente)

| Item | Opção | Custo estimado |
|---|---|---|
| VPS (auto-hospedado) | Hetzner CX22 (4 GB RAM) | ~€5/mês (~R$ 30) |
| VPS (gerenciado) | Railway Starter | ~US$ 5–20/mês |
| Domínio + SSL | Cloudflare (SSL gratuito) | ~R$ 50/ano |
| **Total infraestrutura** | | **~R$ 30–120/mês** |

### APIs (variável por volume)

| Serviço | Modelo | Custo |
|---|---|---|
| Groq — LLM texto | LLaMA 3.3 70B | US$ 0,59/1M tokens input |
| Groq — transcrição áudio | Whisper Large v3 | US$ 0,111/hora de áudio |
| Groq — descrição imagem | LLaMA 4 Scout 17B | US$ 0,11/1M tokens |
| fastembed (embeddings RAG) | MiniLM local | **Gratuito** (roda no servidor) |
| Evolution API | Open source | **Gratuito** (self-hosted) |

**Estimativa para 500 leads/mês com média de 10 mensagens cada:**
- ~5M tokens/mês → ~US$ 3,00/mês em LLM
- Total APIs: **< US$ 5/mês** para a maioria dos cenários de PME

### Custo total estimado (PME — até 1.000 leads/mês)

| Categoria | Custo mensal |
|---|---|
| Infraestrutura | R$ 30–120 |
| APIs (Groq) | R$ 15–40 |
| **Total** | **R$ 45–160/mês** |

Comparativo: um SDR júnior (salário + encargos) custa ~R$ 3.000–5.000/mês para fazer a mesma qualificação manual.

---

## Antecipação de Problemas e Desafios

### 1. Risco de Ban do WhatsApp (canal Baileys)
**Problema:** O canal Baileys usa uma conexão não oficial ao WhatsApp, podendo ser banido se o comportamento parecer automatizado em excesso.

**Mitigação:**
- Delay realista de digitação configurado (evita respostas instantâneas)
- Limitar volume de mensagens enviadas por hora
- Usar WhatsApp Business API (canal oficial) para campanhas em massa
- Manter número exclusivo para o agente, separado do número pessoal do vendedor

### 2. Alucinações do LLM
**Problema:** O modelo pode inventar informações sobre produtos que não existem no catálogo.

**Mitigação:**
- Prompt instrui o agente a responder apenas com base no contexto fornecido
- RAG garante que apenas chunks relevantes chegam ao modelo
- Threshold de similaridade (0.10) evita chunks irrelevantes no contexto
- Monitoramento regular das conversas pelo gestor

### 3. Falha na Transcrição de Áudio
**Problema:** Mensagens de voz com ruído, sotaque ou áudio ruim podem ser transcritas incorretamente.

**Mitigação:**
- Se a transcrição falhar, o agente solicita ao lead que repita por texto
- Log de erros registra falhas para revisão

### 4. LGPD — Proteção de Dados
**Problema:** O sistema coleta dados pessoais (nome, telefone, e-mail, cidade) sem consentimento explícito formal.

**Mitigação:**
- Incluir aviso de coleta de dados na primeira mensagem do agente
- Banco de dados local (SQLite) — dados não saem da infraestrutura da empresa
- Implementar rota de exclusão de dados por solicitação do lead
- Garantir que a Groq API processa dados conforme GDPR (verificar DPA)

### 5. Dependência de Serviço Externo (Groq)
**Problema:** Se a Groq API ficar indisponível, o agente para de responder.

**Mitigação:**
- Circuit breaker: se a chamada falhar, o agente envia mensagem padrão pedindo para o lead aguardar
- Monitorar uptime da Groq (99.9% SLA declarado)
- Opção de fallback: configurar OpenAI ou Anthropic como provedor alternativo (troca apenas a variável de ambiente)

### 6. Escalabilidade do Banco de Dados
**Problema:** SQLite não suporta alto volume de escrita concorrente.

**Mitigação:**
- Para até ~5.000 leads ativos, SQLite é suficiente
- Acima disso: migrar para PostgreSQL (mudança de `DATABASE_URL` no `.env`, sem alteração de código graças ao SQLAlchemy)

---

## Indicadores de Sucesso (KPIs sugeridos)

| KPI | Meta inicial | Como medir |
|---|---|---|
| Tempo médio de primeiro contato | < 30 segundos | Log de mensagens |
| Taxa de classificação correta | > 85% | Revisão amostral pelo gestor |
| Leads hot entregues ao vendedor | > 20% dos novos leads | Dashboard status |
| Taxa de resposta ao follow-up | > 15% | Comparar leads com/sem follow-up |
| Custo por lead qualificado | < R$ 0,50 | Total API ÷ leads qualificados |
