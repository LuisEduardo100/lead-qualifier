# Lead Qualifier

Um sistema para automação e qualificação de leads via WhatsApp, focado em otimizar o tempo de equipes de vendas (SDRs/Closers).

## O Problema

Times comerciais frequentemente perdem horas diárias respondendo as mesmas perguntas no WhatsApp para identificar se um lead tem perfil de compra. Esse processo manual é repetitivo, difícil de escalar e inconsistente. Além disso, disparos em massa exigem exportar listas e usar ferramentas externas, fragmentando o fluxo de trabalho.

## A Solução (O que o projeto faz)

O **Lead Qualifier** centraliza o atendimento e a prospecção no WhatsApp em um único painel:

1. **Qualificação com IA:** Um agente virtual atende os leads 24/7, responde dúvidas e coleta dados importantes gradualmente (nome, cidade, orçamento, etc.). Ele classifica o contato automaticamente como `hot` (quente), `warm` (morno), `cold` (frio) ou `new` (novo).
2. **Atendimento humanizado e RAG:** O agente responde com tom de voz de um consultor real, incluindo delay de digitação para parecer natural. Suporta catálogo em PDF via RAG (Retrieval-Augmented Generation), conseguindo tirar dúvidas com base no seu próprio documento e enviá-lo quando solicitado. Além disso, transcreve áudios e compreende imagens recebidas.
3. **Transição para o vendedor (Handoff):** Se o lead estiver quente e pronto para compra, o vendedor pode pausar a IA e assumir o controle da conversa diretamente pela interface web do sistema, tendo acesso a todo o contexto.
4. **Campanhas de prospecção ativas:** Permite o disparo de mensagens em massa via canal WhatsApp Business Oficial, segmentando leads por status e monitorando a taxa de entrega no mesmo painel.

## Stack Tecnológico

- **Backend:** Python 3.12, FastAPI, SQLite (com aiosqlite).
- **Inteligência Artificial:** LLaMA 3.3 70B (texto), Whisper Large v3 (áudio) e LLaMA 4 Scout (visão) consumidos via API da Groq.
- **Integração WhatsApp:** Evolution API v2.3.7 (suporta WhatsApp Web via Baileys e a API Oficial Business).
- **RAG Local:** fastembed (`paraphrase-multilingual-MiniLM-L12-v2`) rodando sem custo de API externa, usando o próprio SQLite como banco vetorial.
- **Frontend:** HTML nativo e Tailwind CSS (via CDN).

## Instalação e Setup

A arquitetura do projeto foi desenhada para rodar de forma isolada usando Docker Compose.

### Pré-requisitos
- Docker e Docker Compose instalados na máquina.
- Uma conta gratuita no [Groq Console](https://console.groq.com) para obter uma API Key.

### Passo 1: Configuração do ambiente

Clone o repositório e crie o arquivo de variáveis de ambiente:

```bash
git clone <url-do-repositorio>
cd lead-qualifier
cp .env.example .env
```

Abra o arquivo `.env` recém-criado e ajuste as configurações:
- `GROQ_API_KEY`: Insira sua chave de API gerada na Groq.
- `SECRET_KEY`: Digite uma string longa e aleatória (usada para gerar os tokens de autenticação JWT).
- `ADMIN_USERNAME` e `ADMIN_PASSWORD`: Escolha o usuário e senha para acessar o painel de administração.
- `EVOLUTION_API_KEY`: Defina uma senha de segurança para a Evolution API conversar com o seu backend.

### Passo 2: Subindo a aplicação

Com o arquivo `.env` configurado, inicie os containers em background:

```bash
docker compose up -d
```

O Docker baixará as imagens e iniciará 4 serviços: um banco PostgreSQL, um Redis, a Evolution API e o seu Backend FastAPI.

Para acompanhar se tudo subiu corretamente e ver quando a API terminar de carregar, leia os logs:
```bash
docker compose logs -f api
```

### Passo 3: Acesso e Conexão com o WhatsApp

1. Acesse o painel pelo navegador em: **http://localhost:8000**
2. Faça login usando os dados que você configurou no `.env`.
3. Para conectar o seu WhatsApp: vá no menu **Canais** > clique em **Novo Canal** > Escolha **WhatsApp (Baileys)**.
4. Dê um nome ao canal e clique em **Conectar**.
5. Abra o WhatsApp no celular, vá em Dispositivos Vinculados e escaneie o QR Code que aparecerá na tela.

Pronto! Assim que a conexão for estabelecida, a IA assumirá o número e começará a ouvir as mensagens recebidas. Na aba **Configurações**, você pode personalizar o prompt do agente, o contexto do seu negócio e enviar seu arquivo PDF (catálogo).

## Desenvolvimento e Testes Locais

Se quiser rodar localmente sem o Docker para a API (para desenvolver/contribuir), o projeto utiliza o `uv` como gerenciador de pacotes.

Para executar a suíte de testes (composta por mais de 80 testes que não requerem conexão com APIs externas para passar):
```bash
uv run pytest tests/ -v
```

## Integração com Claude Code (MCP Server)

O sistema expõe um servidor Model Context Protocol (MCP) para você interagir com a aplicação diretamente via Claude ou outro assistente compatível. É muito útil durante o desenvolvimento para debugar o banco local, checar os status dos leads (`list_leads`), visualizar um resumo do pipeline (`get_pipeline_summary`) ou alterar dados rapidamente pelo terminal.

Para integrar, inclua o seguinte trecho no seu `claude_desktop_config.json` ou `.claude/settings.json` na raiz:

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
