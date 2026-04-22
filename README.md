# Lead Qualifier — Agente de Qualificação de Leads via WhatsApp

Sistema de automação comercial que recebe mensagens de WhatsApp, qualifica leads automaticamente com IA e permite disparos de campanhas de prospecção em massa. Desenvolvido com FastAPI, SQLAlchemy, Evolution API e Groq (LLaMA 3.3 70B).

---

## O que o sistema faz

1. **Recebe mensagens de WhatsApp** via webhook (Evolution API)
2. **Qualifica o lead automaticamente** usando IA — classifica como `hot`, `warm`, `cold` ou `new`
3. **Coleta dados progressivamente** (nome, cidade, orçamento, tipo de projeto, email)
4. **Responde como consultor humano** com tom natural de WhatsApp
5. **Pausa o agente** quando o vendedor quer assumir a conversa manualmente
6. **Dispara campanhas em massa** filtrando leads por status e enviando via canal WhatsApp Business
7. **Envia follow-ups automáticos** para leads warm/hot que pararam de responder
8. **Dashboard web** para visualizar leads, conversas, configurar o agente e monitorar campanhas

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
      ├── /api/config     ← configuração do agente (prompt, contexto, critérios)
      └── /api/auth       ← login JWT
      │
      ├── Groq API (LLaMA 3.3 70B)   ← qualificação + geração de resposta
      ├── SQLite (aiosqlite)          ← banco de dados local
      └── APScheduler                ← follow-ups automáticos agendados

Frontend (HTML + Tailwind CSS)
      ├── dashboard.html   ← visão geral dos leads
      ├── lead.html        ← conversa individual + envio manual
      ├── channels.html    ← gestão de canais WhatsApp
      ├── campaigns.html   ← campanhas de prospecção
      └── settings.html    ← configuração do agente
```

### Fluxo de uma mensagem recebida

```
Mensagem chega → _extract_message() → texto / transcrição de áudio / descrição de imagem
      ↓
Lead encontrado ou criado no banco
      ↓
qa.qualify() — LLM analisa histórico → retorna status + próxima pergunta + dados coletados
      ↓
Atualiza Lead (status, nome, email, cidade, orçamento...)
      ↓
ra.generate_response() — LLM gera resposta natural em 1-2 frases
      ↓
send_text_human() → typing indicator → delay realista → mensagem enviada
```

---

## Tech Stack

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async) |
| Banco de dados | SQLite com aiosqlite |
| IA | Groq API — LLaMA 3.3 70B (texto) + Whisper Large v3 (áudio) |
| WhatsApp | Evolution API v2.3.7 (Baileys + WhatsApp Business) |
| Frontend | HTML + Tailwind CSS (CDN) |
| Auth | JWT com python-jose |
| Agendador | APScheduler |
| Gerenciador de pacotes | uv |
| Containerização | Docker + Docker Compose |

---

## Pré-requisitos

- **Docker** e **Docker Compose** instalados ([instalar Docker](https://docs.docker.com/engine/install/))
- **Git** instalado
- Conta gratuita no [Groq Console](https://console.groq.com) para obter a API key
- Para canais WhatsApp Business: conta de desenvolvedor Meta com App configurado

> Para desenvolvimento local sem Docker: Python 3.12+ e [uv](https://docs.astral.sh/uv/getting-started/installation/)

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

---

## Setup para desenvolvimento local (sem Docker)

### 1. Instalar uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Instalar dependências

```bash
uv sync
uv sync --optional dev   # inclui pytest
```

### 3. Subir apenas a Evolution API via Docker

```bash
docker compose up -d postgres redis evolution
```

### 4. Criar o diretório de dados

```bash
mkdir -p data
```

### 5. Rodar o servidor

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

O `--reload` reinicia o servidor automaticamente ao salvar arquivos.

### 6. Configurar PUBLIC_URL para webhooks locais

A Evolution API precisa chamar seu backend via webhook. Em desenvolvimento local, use [ngrok](https://ngrok.com) ou [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) para expor a porta 8000:

```bash
ngrok http 8000
```

Defina a URL pública no `.env`:

```env
PUBLIC_URL=https://abc123.ngrok-free.app
```

> **Importante:** reinicie o servidor após alterar `PUBLIC_URL`. Canais já criados precisam ser recriados para apontar para a nova URL.

---

## Rodando os testes

```bash
uv run pytest tests/ -v
```

Resultado esperado: **13 testes passando**, sem warnings.

Os testes cobrem:
- Defaults do modelo Campaign
- Criação de instância WhatsApp Business (payload Evolution)
- Validação de credenciais obrigatórias
- Criação de canal via API
- Envio de campanha (sucesso e falha)
- Preview com deduplicação de telefones
- Criação de campanha em rascunho
- Transição de status ao lançar campanha
- Proteção contra duplo lançamento
- Deleção de campanha

---

## Estrutura do projeto

```
lead-qualifier/
├── backend/
│   ├── main.py              # app FastAPI, lifespan, rotas estáticas
│   ├── models.py            # modelos SQLAlchemy (Lead, Channel, Campaign...)
│   ├── database.py          # engine async, init_db, migrate_db
│   ├── config.py            # settings via .env (pydantic-settings)
│   ├── auth.py              # JWT, hash de senha, dependência get_current_user
│   ├── qr_store.py          # armazenamento temporário do QR Code em memória
│   ├── agents/
│   │   ├── qualification.py # LLM para classificar lead e coletar dados
│   │   ├── response.py      # LLM para gerar resposta natural
│   │   └── followup.py      # lógica de follow-up
│   ├── routers/
│   │   ├── webhooks.py      # POST /webhook/{instance} — coração do sistema
│   │   ├── leads.py         # CRUD leads, envio manual, pause/resume
│   │   ├── channels.py      # CRUD canais, QR code, status
│   │   ├── campaigns.py     # CRUD campanhas, preview, launch, delete
│   │   ├── config_router.py # GET/PUT configurações do agente
│   │   └── auth_router.py   # POST /api/auth/token (login)
│   └── services/
│       ├── evolution.py     # cliente HTTP Evolution API
│       ├── campaign_sender.py # background task de disparo em massa
│       ├── scheduler.py     # APScheduler para follow-ups
│       └── email_service.py # envio de email via SMTP
├── frontend/
│   ├── index.html           # login
│   ├── dashboard.html       # lista de leads com filtros
│   ├── lead.html            # conversa individual
│   ├── channels.html        # gestão de canais
│   ├── campaigns.html       # campanhas de prospecção
│   ├── settings.html        # configuração do agente
│   └── static/js/api.js     # helpers de fetch autenticado
├── tests/
│   ├── conftest.py          # fixtures pytest (db in-memory, client, auth)
│   └── test_campaigns.py    # testes de campanhas e canais
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Variáveis de ambiente — referência completa

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `GROQ_API_KEY` | Sim | — | Chave da API Groq (llm + whisper) |
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

### Pause/resume do agente

Na tela de conversa individual, o vendedor pode pausar o agente para assumir o atendimento manualmente. Novas mensagens continuam sendo salvas, mas o LLM não responde até o agente ser reativado.

### Campanhas de prospecção

1. Crie uma campanha definindo nome, mensagem, canal (WhatsApp Business) e filtro de status
2. Use **Preview** para ver quantos leads serão atingidos antes de lançar
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
