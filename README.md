# Lead Qualifier — Agente de Qualificação de Leads via WhatsApp

> Automação comercial para equipes de vendas que perdem tempo qualificando leads manualmente no WhatsApp.

---

## Por que esse projeto existe

Times comerciais — especialmente SDRs — gastam horas por dia respondendo as mesmas perguntas no WhatsApp, tentando descobrir se um contato tem perfil de compra antes de passar para o closer. O processo é repetitivo, inconsistente entre atendentes e escala mal.

Além disso, disparar campanhas de prospecção em massa exige exportar listas, usar ferramentas separadas e monitorar retornos manualmente — o que fragmenta o fluxo de trabalho e gera perda de dados.

O **Lead Qualifier** resolve os dois problemas em um único sistema:

1. **Qualificação automática via IA** — o agente conduz a conversa no WhatsApp, coleta dados progressivamente e classifica cada lead como `hot`, `warm`, `cold` ou `new` sem intervenção humana
2. **Campanhas integradas ao pipeline** — dispara mensagens em massa para segmentos filtrados pelo próprio CRM, com acompanhamento de entrega em tempo real
3. **Handoff suave para o vendedor** — quando o lead está quente, o agente pode ser pausado para o humano assumir, com todo o histórico e dados coletados visíveis na interface

O resultado é um SDR que atende dezenas de conversas simultâneas 24/7, filtra o ruído e entrega apenas leads qualificados para o time de vendas.

---

## O que o sistema faz

1. **Recebe mensagens de WhatsApp** via webhook (Evolution API) — texto, áudio (transcrição Whisper), imagem (descrição LLaMA 4 Scout) e documentos
2. **Qualifica o lead automaticamente** usando IA — classifica como `hot`, `warm`, `cold` ou `new`
3. **Coleta dados progressivamente** (nome, cidade, orçamento, tipo de projeto, email)
4. **Responde como consultor humano** com tom natural de WhatsApp e delay realista de digitação
5. **Usa catálogo de produtos (RAG)** — o agente busca chunks relevantes do PDF ativo para responder perguntas sobre produtos/serviços, e envia o arquivo ao lead quando solicitado
6. **Pausa o agente** quando o vendedor quer assumir a conversa manualmente
7. **Dispara campanhas em massa** filtrando leads por status e enviando via canal WhatsApp Business
8. **Envia follow-ups automáticos** para leads warm/hot que pararam de responder
9. **Dashboard web** para visualizar leads, conversas, configurar o agente, gerenciar documentos e monitorar campanhas

---

## Arquitetura

```
WhatsApp (usuário)
      │
      ▼
Evolution API (v2.3.7)          ← gerencia instâncias WA (Baileys ou WA Business)
      │ webhook POST /webhook/{instance}
      ▼
FastAPI Backend (Python 3.12)
      ├── /webhook        ← recebe mensagens, roda qualificação + resposta
      ├── /api/leads      ← CRUD de leads, envio manual, pause/resume agente
      ├── /api/channels   ← criação/gestão de canais WA
      ├── /api/campaigns  ← criação, preview, disparo e monitoramento de campanhas
      ├── /api/documents  ← upload/gestão de catálogo PDF (RAG)
      ├── /api/config     ← configuração do agente (prompt, contexto, critérios)
      └── /api/auth       ← login JWT
      │
      ├── Groq API (LLaMA 3.3 70B + Whisper Large v3)  ← LLM + transcrição de áudio
      ├── SQLite (aiosqlite)                            ← banco principal + vetores RAG
      └── APScheduler                                   ← follow-ups automáticos agendados

Frontend (HTML + Tailwind CSS)
      ├── index.html       ← login
      ├── dashboard.html   ← visão geral dos leads
      ├── lead.html        ← conversa individual + envio manual
      ├── channels.html    ← gestão de canais WhatsApp
      ├── campaigns.html   ← campanhas de prospecção
      └── settings.html    ← configuração do agente e upload de catálogo
```

### Fluxo de uma mensagem recebida

```
Mensagem chega → _extract_message() → texto / transcrição de áudio / descrição de imagem / nome do documento
      ↓
Lead encontrado ou criado no banco
      ↓
search_relevant_chunks() — busca semântica por cosseno (embeddings armazenados no SQLite) com fallback por palavras-chave
      ↓
qa.qualify() — LLM analisa histórico → retorna status + próxima pergunta + dados coletados
      ↓
Atualiza Lead (status, nome, email, cidade, orçamento...)
      ↓
ra.generate_response() — LLM gera resposta natural (1-2 frases), com contexto do catálogo se relevante
      ↓
Se resposta contém [ENVIAR_CATALOGO] → envia PDF via Evolution API em background
      ↓
send_text_human() → typing indicator → delay realista → mensagem enviada
```

---

## Tech Stack

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async) |
| Banco de dados | SQLite com aiosqlite — armazena leads, mensagens, config e vetores RAG |
| IA — texto | Groq API — LLaMA 3.3 70B Versatile |
| IA — áudio | Groq API — Whisper Large v3 |
| IA — imagem | Groq API — LLaMA 4 Scout 17B |
| RAG — extração | pypdf — leitura e chunking de PDFs por página |
| RAG — embeddings | fastembed (paraphrase-multilingual-MiniLM-L12-v2) — roda localmente, sem API externa |
| RAG — armazenamento | SQLite — vetores serializados como JSON na tabela `document_chunks` |
| RAG — retrieval | Busca semântica por similaridade de cosseno (numpy) com fallback por palavras-chave |
| WhatsApp | Evolution API v2.3.7 (Baileys + WhatsApp Business) |
| Frontend | HTML + Tailwind CSS (CDN) |
| Auth | JWT com python-jose |
| Agendador | APScheduler |
| Gerenciador de pacotes | uv |
| Containerização | Docker + Docker Compose |

---

## MCP Server — Integração com Claude Code

O projeto expõe um **MCP Server** (Model Context Protocol) que conecta o pipeline de leads diretamente ao Claude Code. Isso serve a dois propósitos:

**Em desenvolvimento:** inspecionar estado do banco, depurar classificações incorretas, verificar o efeito de mudanças no agente e consultar configurações — tudo sem abrir o dashboard ou escrever queries SQL manualmente.

**Em produção:** acompanhar o pipeline, corrigir classificações e obter resumos executivos direto da linha de comando, integrando o Lead Qualifier ao fluxo de trabalho do time técnico.

### Ferramentas disponíveis

| Ferramenta | O que faz |
|---|---|
| `list_leads` | Lista todos os leads com status, nome, cidade e última mensagem. Aceita filtro por status (`hot`, `warm`, `cold`, `new`, `lost`) |
| `get_conversation` | Retorna o histórico completo de uma conversa por `lead_id` |
| `update_lead_status` | Atualiza manualmente o status de um lead |
| `get_pipeline_summary` | Conta leads por status — visão rápida do pipeline |
| `get_config` | Retorna as configurações atuais do agente (prompt, contexto, critérios) |

### Configurar no Claude Code

Adicione ao seu `.claude/settings.json` na raiz do projeto ou ao `claude_desktop_config.json` (Mac: `~/Library/Application Support/Claude/`):

```json
{
  "mcpServers": {
    "lead-qualifier": {
      "command": "uv",
      "args": ["run", "python", "mcp_server.py"],
      "cwd": "/caminho/absoluto/para/lead-qualifier"
    }
  }
}
```

> O MCP Server lê diretamente o banco SQLite em `data/leads.db`. O backend não precisa estar rodando para usar as ferramentas de leitura.

### Exemplos de uso no Claude Code

```
# Ver todos os leads quentes
"Liste os leads com status hot"

# Investigar uma conversa específica
"Mostre o histórico completo do lead 42"

# Resumo executivo do pipeline
"Qual é o resumo do pipeline atual?"

# Corrigir classificação incorreta durante desenvolvimento
"Atualize o status do lead 17 para warm"

# Verificar configuração ativa do agente
"Qual é o prompt atual do agente?"
```

---

## Pré-requisitos

- **Docker** e **Docker Compose** instalados ([instalar Docker](https://docs.docker.com/engine/install/))
- **Git** instalado
- Conta gratuita no [Groq Console](https://console.groq.com) para obter a API key
- Para canais WhatsApp Business: conta de desenvolvedor Meta com App configurado

---

## Setup — passo a passo

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd lead-qualifier
```

### 2. Configurar variáveis de ambiente

Copie o arquivo de exemplo e preencha os valores:

```bash
cp .env.example .env
```

Edite o `.env`:

```env
# Chave da API Groq (obter em https://console.groq.com)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Chave secreta para assinar os tokens JWT — gere uma string aleatória longa
SECRET_KEY=mude-para-uma-chave-secreta-aleatoria-longa

# Credenciais do painel admin (login na interface web)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=senha-segura-aqui

# URL interna da Evolution API (não alterar se usar Docker Compose)
EVOLUTION_API_URL=http://evolution:8080

# Chave de autenticação da Evolution API — defina um valor e use o mesmo abaixo
EVOLUTION_API_KEY=sua-chave-evolution-aqui

# Email para follow-ups (opcional — se não usar, deixe em branco)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu@gmail.com
SMTP_PASSWORD=sua-app-password-gmail
EMAIL_FROM_NAME=Consultor Comercial
```

### 3. Configurar a Evolution API no Docker Compose

Abra `docker-compose.yml` e certifique-se que `AUTHENTICATION_API_KEY` usa o mesmo valor que você definiu em `EVOLUTION_API_KEY` no `.env`:

```yaml
environment:
  - AUTHENTICATION_API_KEY=${EVOLUTION_API_KEY}
```

Isso já está configurado no arquivo — desde que o `.env` tenha o valor correto, está pronto.

### 4. Subir os containers

```bash
docker compose up -d
```

Isso vai subir 4 serviços:
- `postgres` — banco da Evolution API (PostgreSQL 16)
- `redis` — cache da Evolution API
- `evolution` — Evolution API na porta 8080
- `api` — o backend FastAPI na porta 8000

Acompanhe os logs para confirmar que tudo iniciou corretamente:

```bash
docker compose logs -f api
```

Você deve ver algo como:
```
INFO:     Application startup complete.
```

### 5. Acessar a interface

Abra no navegador: [http://localhost:8000](http://localhost:8000)

Login com as credenciais definidas em `ADMIN_USERNAME` e `ADMIN_PASSWORD`.

### 6. Criar um canal WhatsApp (Baileys — QR Code)

1. Acesse **Canais** no menu
2. Clique em **Novo Canal**
3. Escolha o tipo **WhatsApp (Baileys)**
4. Digite um nome para o canal (ex: `Atendimento`)
5. Clique em **Conectar** para exibir o QR Code
6. Escaneie com o WhatsApp do celular em **Dispositivos Vinculados**

> O canal fica com status **conectado** após o scan. Mensagens recebidas já serão processadas pelo agente.

### 7. Criar um canal WhatsApp Business (API oficial — campanhas)

Para disparar campanhas em massa, você precisa de um canal WhatsApp Business:

1. Acesse **Canais → Novo Canal**
2. Escolha **WhatsApp Business (API oficial)**
3. Preencha:
   - **Token de acesso** (do seu App Meta)
   - **Phone Number ID** (do painel Meta for Developers)
   - **Business ID** (ID da sua conta business)
4. Clique em **Criar**

### 8. Configurar o agente

Acesse **Configurações** e personalize:

- **Prompt do agente**: como o consultor deve se comportar
- **Contexto do negócio**: descreva sua empresa, produtos, público-alvo
- **Critérios de qualificação**: quando considerar um lead hot/warm/cold
- **Produtos em destaque**: lista de produtos/serviços para o agente referenciar

### 9. Fazer upload do catálogo (opcional)

Na aba **Documentos** em Configurações, faça upload de um PDF (catálogo, tabela de preços, etc.). O sistema:
- Extrai e indexa o texto de cada página
- Usa busca por palavras-chave para encontrar chunks relevantes a cada mensagem
- Inclui o conteúdo relevante no contexto do agente
- Envia o PDF ao lead quando ele pedir "catálogo", "folheto" ou "material"

---

## Rodando os testes

```bash
uv run pytest tests/ -v
```

Resultado esperado: **80 testes passando**.

Os testes cobrem todos os módulos principais sem precisar de conexões externas (Evolution API e Groq são mockados):

| Arquivo | Testes | O que cobre |
|---|---|---|
| `test_auth.py` | 3 | Login válido, senha errada, usuário inexistente |
| `test_campaigns.py` | 13 | Modelo, envio (sucesso/falha), preview, criação, launch, delete |
| `test_channels_extra.py` | 10 | List, create baileys/WA Business/duplicado, delete cascade, status, QR Code |
| `test_config.py` | 4 | GET defaults, PUT persiste, sobrescreve, merge DB + defaults |
| `test_documents.py` | 8 | List, upload PDF (sucesso/vazio/não-PDF), substituição do doc ativo, delete |
| `test_leads.py` | 9 | CRUD completo, filtro por status, toggle pause, send message |
| `test_rag.py` | 11 | Busca sem doc, com match, ranking, query curta, doc ativo, extract PDF, filtro de chunk curto (title-only), threshold de similaridade semântica |
| `test_agents.py` | 8 | qualify (warm/hot/fallback JSON), generate_response (catálogo, empty), followup |
| `test_webhooks.py` | 13 | Funções puras (`_normalize_number`, `_cfg`) + handler (from_me, grupo, novo lead, paused, status hot, erro qualify, documento) |

---

## Estrutura do projeto

```
lead-qualifier/
├── backend/
│   ├── main.py              # app FastAPI, lifespan, rotas estáticas
│   ├── models.py            # modelos SQLAlchemy (Lead, Channel, Campaign, AgentDocument...)
│   ├── database.py          # engine async, init_db, migrate_db
│   ├── config.py            # settings via .env (pydantic-settings)
│   ├── auth.py              # JWT, hash de senha, dependência get_current_user
│   ├── qr_store.py          # armazenamento temporário do QR Code em memória
│   ├── agents/
│   │   ├── qualification.py # LLM para classificar lead e coletar dados
│   │   ├── response.py      # LLM para gerar resposta natural
│   │   └── followup.py      # geração de mensagem de follow-up personalizada
│   ├── routers/
│   │   ├── webhooks.py      # POST /webhook/{instance} — coração do sistema
│   │   ├── leads.py         # CRUD leads, envio manual, pause/resume
│   │   ├── channels.py      # CRUD canais, QR code, status
│   │   ├── campaigns.py     # CRUD campanhas, preview, launch, delete
│   │   ├── documents.py     # upload/gestão de catálogo PDF
│   │   ├── config_router.py # GET/PUT configurações do agente
│   │   └── auth_router.py   # POST /api/auth/token (login)
│   └── services/
│       ├── evolution.py     # cliente HTTP Evolution API
│       ├── rag.py           # extração de chunks PDF, geração de embeddings e busca semântica
│       ├── campaign_sender.py # background task de disparo em massa
│       ├── scheduler.py     # APScheduler para follow-ups
│       └── email_service.py # envio de email via SMTP
├── frontend/
│   ├── index.html           # login
│   ├── dashboard.html       # lista de leads com filtros
│   ├── lead.html            # conversa individual
│   ├── channels.html        # gestão de canais
│   ├── campaigns.html       # campanhas de prospecção
│   ├── settings.html        # configuração do agente + upload de catálogo
│   └── static/js/api.js     # helpers de fetch autenticado
├── tests/
│   ├── conftest.py              # fixtures pytest (SQLite in-memory, client HTTP, auth)
│   ├── test_auth.py             # endpoint de login
│   ├── test_campaigns.py        # campanhas e canais WA Business
│   ├── test_channels_extra.py   # canais (baileys, status, delete cascade)
│   ├── test_config.py           # configurações do agente
│   ├── test_documents.py        # upload e gestão de documentos
│   ├── test_leads.py            # CRUD de leads
│   ├── test_rag.py              # serviço de busca e extração de PDF
│   ├── test_agents.py           # agentes LLM (mocked)
│   └── test_webhooks.py         # handler de webhook + funções auxiliares
├── mcp_server.py            # MCP Server para integração com Claude Code
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Variáveis de ambiente — referência completa

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `GROQ_API_KEY` | Sim | — | Chave da API Groq (LLM + Whisper) |
| `SECRET_KEY` | Sim | `change-this` | Segredo para assinar tokens JWT |
| `ADMIN_USERNAME` | Não | `admin` | Usuário do painel web |
| `ADMIN_PASSWORD` | Não | `admin123` | Senha do painel web |
| `EVOLUTION_API_URL` | Não | `http://localhost:8080` | URL da Evolution API |
| `EVOLUTION_API_KEY` | Sim | `lead-qualifier-key` | Chave de autenticação Evolution |
| `PUBLIC_URL` | Sim (prod) | `http://api:8000` | URL pública para webhooks |
| `DATABASE_URL` | Não | `sqlite+aiosqlite:///./data/leads.db` | String de conexão do banco |
| `SMTP_HOST` | Não | `smtp.gmail.com` | Servidor SMTP para follow-up por email |
| `SMTP_PORT` | Não | `587` | Porta SMTP |
| `SMTP_USER` | Não | — | Email remetente |
| `SMTP_PASSWORD` | Não | — | App Password Gmail |
| `EMAIL_FROM_NAME` | Não | `Consultor Comercial` | Nome exibido nos emails |

---

## Funcionalidades do agente

### Qualificação automática

O agente analisa o histórico completo de conversa a cada mensagem e classifica o lead:

- **hot**: sabe exatamente o que quer, menciona produto/aplicação específica, intenção real de compra → agente solicita email para "ofertas exclusivas"
- **warm**: demonstra interesse mas com informações vagas → agente coleta nome, cidade, produto de interesse, orçamento, tipo de projeto
- **cold**: fora do nicho, sem interesse real → agente encerra com cordialidade
- **new**: primeira mensagem, sem histórico suficiente para classificar

### Dados coletados automaticamente

Para leads warm/hot, o agente coleta progressivamente (1 pergunta por vez):
nome, cidade, produto de interesse, orçamento estimado, tipo de projeto, e-mail (apenas para hot)

### Catálogo de produtos (RAG)

1. Faça upload de um PDF em **Configurações → Documentos**
2. O sistema extrai o texto de cada página — páginas com menos de 8 palavras (ex: títulos ou capas) são descartadas automaticamente para evitar ruído no retrieval
3. Cada chunk é vetorizado com o modelo `paraphrase-multilingual-MiniLM-L12-v2` (fastembed, roda localmente) e o vetor é serializado como JSON e armazenado no SQLite
4. A cada mensagem recebida, a query do usuário é embeddada e comparada contra todos os chunks via similaridade de cosseno: apenas chunks com score ≥ 0.10 são incluídos no contexto — chunks irrelevantes são suprimidos mesmo que sejam os "menos piores"
5. Fallback por sobreposição de palavras-chave quando o documento ainda não possui embeddings
6. Se o lead pedir "catálogo", "folheto", "PDF" ou "material", o agente inclui `[ENVIAR_CATALOGO]` na resposta e o arquivo é enviado automaticamente via WhatsApp
7. Apenas um documento fica ativo por vez — novo upload desativa o anterior

### Suporte a mídia

- **Áudio / PTT**: transcrição automática via Whisper Large v3. Se a transcrição falhar, o agente pede ao lead que digite
- **Imagem**: descrição automática via LLaMA 4 Scout 17B Vision. Caption original preservado como fallback
- **Documento**: nome do arquivo e caption extraídos e incluídos no histórico
- **Sticker / Reação**: ignorado silenciosamente

### Pause/resume do agente

Na tela de conversa individual, o vendedor pode pausar o agente para assumir o atendimento manualmente. Novas mensagens continuam sendo salvas, mas o LLM não responde até o agente ser reativado.

### Campanhas de prospecção

1. Crie uma campanha definindo nome, mensagem, canal (WhatsApp Business) e filtro de status
2. Use **Preview** para ver quantos leads serão atingidos antes de lançar (deduplicação automática de telefones)
3. Ao lançar, o sistema percorre todos os destinatários com delay de 1,5s entre envios
4. Acompanhe o progresso em tempo real: enviados, falhas, status por destinatário

---

## Implantação em produção

### Opção 1 — VPS com Docker Compose (recomendado para início)

1. Provisione um servidor com mínimo **4 GB RAM** e **2 vCPUs** (Hetzner CX21 ~€4/mês, DigitalOcean Basic ~$12/mês)
2. Instale Docker e Docker Compose no servidor
3. Copie os arquivos ou clone o repositório
4. Configure o `.env` com `PUBLIC_URL` apontando para o domínio/IP público
5. Aponte um domínio para o IP do servidor
6. Configure HTTPS com Nginx + Let's Encrypt (obrigatório para webhooks do Meta/WhatsApp)
7. Rode `docker compose up -d`

### Opção 2 — Railway / Render (mais simples, sem gerenciar servidor)

O `Dockerfile` está pronto. Basta conectar o repositório ao serviço de deploy e configurar as variáveis de ambiente pelo painel da plataforma.

> **Atenção para produção:** a Evolution API precisa que o webhook seja HTTPS. Configure um reverse proxy (Nginx ou Caddy) na frente do container `api`.
