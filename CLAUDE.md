# CLAUDE.md — Guia do Projeto nanobot

## Visão Geral

nanobot é um assistente pessoal de IA ultra-leve (~4.500 linhas de código core). O projeto segue uma filosofia de mínimo código com máximo de funcionalidade.

## Estrutura do Projeto

```
nanobot/
├── agent/              # Core do agente
│   ├── loop.py         # AgentLoop — engine principal (LLM ↔ tool execution)
│   ├── context.py      # ContextBuilder — monta system prompt + mensagens
│   ├── memory.py       # MemoryStore — MEMORY.md e HISTORY.md
│   ├── skills.py       # SkillsLoader — carrega SKILL.md do workspace e builtins
│   ├── subagent.py     # SubagentManager — execução de subtarefas em background
│   ├── debate/         # Sistema de debate multi-persona (roundtable)
│   │   ├── config.py   # Pydantic models (RoundtableConfig, PersonaConfig, etc.)
│   │   ├── persona.py  # Persona — inner loop de cada participante
│   │   └── orchestrator.py  # DebateOrchestrator — rodadas, convergência, síntese
│   └── tools/          # Tools built-in
│       ├── base.py     # Tool ABC (name, description, parameters, execute)
│       ├── registry.py # ToolRegistry — dict-based, register/execute/get_definitions
│       ├── filesystem.py  # read_file, write_file, edit_file, list_dir
│       ├── shell.py    # exec (com safety guards)
│       ├── web.py      # web_search (Brave API), web_fetch (readability)
│       ├── message.py  # message (envia ao usuário)
│       ├── spawn.py    # spawn (cria subagent em background)
│       ├── cron.py     # cron (agendamento)
│       ├── debate.py   # debate (inicia roundtable multi-persona)
│       └── mcp.py      # MCP tool wrappers
├── skills/             # Skills built-in (SKILL.md com YAML frontmatter)
│   ├── debate/         # Skill de debate/roundtable
│   ├── github/         # GitHub CLI via gh
│   ├── weather/        # Previsão do tempo
│   ├── cron/           # Agendamento de tarefas
│   ├── memory/         # Sistema de memória (always: true)
│   ├── summarize/      # Resumo de URLs/textos
│   ├── tmux/           # Controle remoto de tmux
│   ├── clawhub/        # Instalação de skills do registry
│   └── skill-creator/  # Meta-skill para criar skills
├── roundtables/        # Configs YAML de roundtable bundled (copiados no onboard)
├── channels/           # Integrações: telegram, discord, whatsapp, slack, email, etc.
├── providers/          # LLM providers
│   ├── base.py         # LLMProvider ABC, LLMResponse, ToolCallRequest
│   ├── litellm_provider.py  # Provider principal (multi-provider via LiteLLM)
│   ├── custom_provider.py   # OpenAI-compatible direto
│   ├── openai_codex_provider.py  # OAuth-based Codex
│   └── registry.py     # ProviderSpec + PROVIDERS tuple (source of truth)
├── bus/                # MessageBus (events + queue)
├── cron/               # CronService (scheduling)
├── heartbeat/          # HeartbeatService (wake-up periódico)
├── session/            # SessionManager (histórico de conversa)
├── config/
│   ├── schema.py       # Pydantic models (Config, ProvidersConfig, etc.)
│   └── loader.py       # load_config(), save_config()
└── cli/
    └── commands.py     # CLI commands (agent, gateway, onboard, status, cron, etc.)
```

## Padrões Arquiteturais

### Como tools funcionam

1. Toda tool estende `Tool` ABC em `agent/tools/base.py`
2. Implementa: `name`, `description`, `parameters` (JSON Schema), `execute(**kwargs)`
3. Registrada em `AgentLoop._register_default_tools()`
4. Context routing via `set_context()` chamado de `AgentLoop._set_tool_context()`
5. `ToolRegistry` é um dict simples: `register()`, `execute()`, `get_definitions()`

### Como providers funcionam

1. `Config._match_provider(model)` resolve o provider em 3 passes: prefixo exato → keyword → fallback
2. `_make_provider()` em `cli/commands.py` cria a instância correta (LiteLLM, Custom, ou Codex)
3. `ProviderSpec` em `providers/registry.py` é o source of truth (adicionar provider = 2 passos)
4. Cada provider implementa `chat(messages, tools, model, max_tokens, temperature) → LLMResponse`

### Como o agent loop funciona

1. `_process_message()` recebe InboundMessage do bus
2. `_set_tool_context()` atualiza routing info em todas as tools
3. `ContextBuilder.build_messages()` monta system prompt + histórico + mensagem atual
4. `_run_agent_loop()` faz o loop LLM ↔ tool execution (max 20 iterações)
5. Resposta final é salva na sessão e publicada no bus

### Como subagents funcionam

1. `SpawnTool.execute()` chama `SubagentManager.spawn()`
2. Cria um `asyncio.Task` com mini agent loop (max 15 iterações)
3. ToolRegistry isolado: sem message, spawn, debate, cron
4. Resultado anunciado via `InboundMessage` no canal "system"

### Como o sistema de debate funciona

1. `DebateTool.execute()` chama `DebateOrchestrator.run_debate()`
2. Orchestrator carrega config YAML de `workspace/roundtables/`
3. Cria `Persona` para cada participante com provider e tools isolados
4. Rodada N: todas as personas executam em paralelo (`asyncio.gather`)
5. Cada persona vê o transcript completo das rodadas anteriores
6. Após `min_rounds`, verifica convergência via LLM
7. Sintetiza o debate em resposta final via LLM do orquestrador
8. Personas podem usar tools diferentes e modelos LLM diferentes

### Como skills funcionam

1. `SkillsLoader` busca em `workspace/skills/` (user) e `nanobot/skills/` (builtin)
2. YAML frontmatter: `name`, `description`, `metadata`, `always`
3. `description` é o trigger — quando o agente vê request que casa, carrega o body
4. Skills com `always: true` (ex: memory) são sempre incluídas no contexto

## Config

- Arquivo: `~/.nanobot/config.json`
- Schema: `config/schema.py` (Pydantic com `alias_generator=to_camel, populate_by_name=True`)
- Aceita tanto camelCase quanto snake_case

### Config do AgentLoop

`AgentLoop.__init__` aceita `config: Config | None` — necessário para o debate tool resolver providers de personas com modelos diferentes.

Todos os 3 pontos em `cli/commands.py` que criam `AgentLoop` passam `config=config`:
- `gateway` command
- `agent` command
- `cron run` command

## Docker

- `Dockerfile`: Python 3.12 + Node.js 20, instala via `uv pip install --system`
- `docker-compose.yml`: services com volumes em `./nano_config/<nome>:/root/.nanobot`
- Workspace path no container: `/root/.nanobot/workspace`
- Roundtables ficam em: `/root/.nanobot/workspace/roundtables/*.yaml`
- Entrypoint: `nanobot`, CMD default: `gateway`
- Build: `docker build -t nanobot .`

### Volumes do docker-compose

Cada instância do nanobot tem seu próprio volume com:
```
nano_config/<nome>/
├── config.json          # Configuração (providers, channels, tools)
├── cron/jobs.json       # Jobs agendados
└── workspace/
    ├── AGENTS.md        # System prompt do agente
    ├── SOUL.md          # Personalidade
    ├── USER.md          # Info do usuário
    ├── HEARTBEAT.md     # Tarefas periódicas
    ├── memory/          # MEMORY.md + HISTORY.md
    ├── skills/          # Skills customizadas
    ├── sessions/        # Histórico de conversas
    └── roundtables/     # Configs YAML de debate
```

## Dependências Chave

- `litellm` — multi-provider LLM routing
- `pydantic` / `pydantic-settings` — config schema
- `typer` / `rich` — CLI
- `pyyaml` — parsing de roundtable configs
- `prompt-toolkit` — input interativo
- `mcp` — Model Context Protocol

## Testes

```bash
./venv/bin/python -m pytest tests/ -x -q
```

63 testes em `tests/`. Todos devem passar.

## Convenções

- Linguagem do código: inglês (docstrings, comments, variable names)
- Linguagem da documentação do usuário: pode ser português ou inglês
- Tools que o agente não pode ter: personas nunca recebem `message`, `spawn`, `debate`, `cron`
- Novos tools: criar classe em `agent/tools/`, registrar em `_register_default_tools()`
- Novos providers: adicionar `ProviderSpec` em `providers/registry.py` + campo em `ProvidersConfig`
- Novos skills: criar diretório em `nanobot/skills/<nome>/SKILL.md`
- Novos roundtables: criar YAML em `nanobot/roundtables/` (bundled) ou `workspace/roundtables/` (user)
