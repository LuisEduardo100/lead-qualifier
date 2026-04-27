# Plano de Implementação em Produção

## Visão Geral

Implantação do Lead Qualifier em uma empresa de médio porte com 1 a 3 canais de WhatsApp ativos, integrando ao fluxo comercial existente em **6 semanas**.

---

## Cronograma de Integrações

### Semana 1 — Infraestrutura e Configuração Base
- Provisionar VPS Hostinger (mín. 4 GB RAM, 2 vCPUs)
- Configurar Docker Compose: Evolution API + backend FastAPI
- Apontar domínio e configurar proxy reverso com certificados HTTPS automáticos (Traefik + Let's Encrypt)
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

| Item | Configuração | Custo estimado |
|---|---|---|
| VPS Hostinger | Plano KVM 2 (mín. 4GB RAM, 2 vCPUs) | ~R$ 35–45/mês |
| Domínio + SSL | Cloudflare (SSL gratuito) | ~R$ 50/ano |
| **Total infraestrutura** | | **~R$ 40–50/mês** |

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
| Infraestrutura (Hostinger) | R$ 40–50 |
| APIs (Groq) | R$ 15–40 |
| **Total** | **R$ 55–90/mês** |

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

### 4. LGPD e Privacidade de Dados
**Problema:** O sistema gerencia e envia dados de contato e dores dos clientes para uma IA na nuvem (Groq).

**Mitigação:**
- O Banco de Dados é hospedado na própria VPS da empresa, e não em uma plataforma SaaS de terceiros.
- A API comercial da Groq tem política estrita (Enterprise-grade) de que **não utiliza os dados enviados via API para treinar seus modelos**, garantindo sigilo comercial e aderência à LGPD.
- Inclusão de um aviso ou opt-out na saudação inicial e implementação de "Direito ao Esquecimento" (exclusão com um clique) caso o lead solicite.

### 5. Dependência de Serviço Externo (Groq)
**Problema:** Se a Groq API ficar indisponível, o agente para de responder.

**Mitigação:**
- Circuit breaker: se a chamada falhar, o agente envia mensagem padrão pedindo para o lead aguardar
- Monitorar uptime da Groq (99.9% SLA declarado)
- Opção de fallback: configurar OpenAI ou Anthropic como provedor alternativo (troca apenas a variável de ambiente)

### 6. Escalabilidade do Banco de Dados
**Problema:** O uso padrão de SQLite pode se tornar um gargalo de escrita caso o volume de leads cresça vertiginosamente de um mês para o outro.

**Mitigação:**
- O SQLite suporta perfeitamente e com alta performance a fase inicial (até ~5.000 leads ativos mensais).
- Se houver necessidade de escalar, o custo de infra é zero: o projeto já sobe um container do PostgreSQL nativamente (usado pela Evolution API). Basta alterar a variável `DATABASE_URL` no `.env` para o backend aproveitar esse mesmo banco de dados super robusto.

---

## Indicadores de Sucesso (KPIs sugeridos)

| KPI | Meta inicial | Como medir |
|---|---|---|
| Tempo médio de primeiro contato | < 30 segundos | Log de mensagens |
| Taxa de classificação correta | > 85% | Revisão amostral pelo gestor |
| Leads hot entregues ao vendedor | > 20% dos novos leads | Dashboard status |
| Taxa de resposta ao follow-up | > 15% | Comparar leads com/sem follow-up |
| Custo por lead qualificado | < R$ 0,50 | Total API ÷ leads qualificados |
