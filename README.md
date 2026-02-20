<div align="center">
  <img src="nanobot_logo.png" alt="nanobot-council" width="500">
  <h1>nanobot-council</h1>
  <p>nanobot fork with multi-persona roundtable debates</p>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
  <p>
    <sub>Forked from <a href="https://github.com/HKUDS/nanobot">HKUDS/nanobot</a></sub>
  </p>
</div>

**nanobot-council** extends [nanobot](https://github.com/HKUDS/nanobot) with a **Roundtable** system — multiple LLM personas debate in parallel rounds with automatic convergence detection and final synthesis.

Everything else works the same: ultra-lightweight (~4,500 lines of core code), multi-provider, multi-channel, skills, subagents, MCP, cron, and more.

## Roundtable (Multi-Persona Debate)

The roundtable system lets you run structured debates between personas with different expertise, LLM models, tools, and perspectives. The orchestrator manages rounds, checks for convergence, and synthesizes a final recommendation.

### How It Works

```
Question → [Persona A]  ──┐
           [Persona B]  ──┼── Round 1 → Transcript → [Convergence?] → ... → Synthesis
           [Persona C]  ──┘
```

1. **You ask a question** — the agent picks (or you specify) a roundtable config
2. **Parallel rounds** — all personas respond simultaneously, seeing the full transcript from prior rounds
3. **Convergence check** — after `min_rounds`, the orchestrator LLM checks if personas have aligned
4. **Synthesis** — the orchestrator produces a final, structured recommendation from the full debate

Each persona can use a **different LLM model**, **different tools**, and a **different temperature** — all defined in a simple YAML file.

### Bundled Roundtables

| Roundtable | Personas | Description |
|------------|----------|-------------|
| `strategy-council` | CFO, CTO, CEO | Executive team debate for strategic decisions |
| `devils-advocate` | Champion, Critic | Stress-test an idea with opposing viewpoints |

### Usage

The agent calls the `debate` tool automatically when it detects a question that benefits from multiple perspectives, or you can be explicit:

```
Debate whether we should migrate from PostgreSQL to DynamoDB. Use strategy-council.
```

### Creating Custom Roundtables

Create a YAML file in `workspace/roundtables/`:

```yaml
name: My Roundtable
description: What this roundtable does
trigger: auto  # auto | explicit

orchestrator:
  # model: anthropic/claude-haiku-4-5  # optional, defaults to agent's model
  synthesis_prompt: |
    Synthesize the debate into a clear recommendation.

rounds:
  max: 3
  min: 1
  convergence: true  # check for early convergence after min rounds

personas:
  - name: Optimist
    system_prompt: |
      You see the upside. Build the strongest case for the idea.
    temperature: 0.7
    tools: [web_search, web_fetch]

  - name: Pessimist
    system_prompt: |
      You see the risks. Find every flaw and hidden cost.
    temperature: 0.5
    tools: [web_search, web_fetch]
```

### Persona Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | yes | — | Display name in the transcript |
| `system_prompt` | yes | — | Persona's perspective and instructions |
| `model` | no | agent's model | LLM model (e.g. `openai/gpt-4o`, `anthropic/claude-haiku-4-5`) |
| `temperature` | no | 0.7 | Creativity level |
| `max_tokens` | no | 4096 | Max response length |
| `tools` | no | `[]` | Tools available to this persona (e.g. `web_search`, `web_fetch`, `exec`) |

> **Note:** Personas can never access `message`, `spawn`, `debate`, or `cron` — these are agent-level tools only.

### Cost Estimate

A typical debate with 3 personas and 3 rounds makes ~10 LLM calls: 9 persona responses + 1 synthesis (plus 1-2 convergence checks). Actual cost depends on the models used.

## Getting Started (Docker — Recommended)

Docker is the recommended way to run nanobot. Each instance gets its own isolated config, workspace, and personality.

**1. Clone the repo**

```bash
git clone https://github.com/rmartignoni/council-nanobot.git
cd council-nanobot
```

**2. Edit `docker-compose.yml`**

The default file includes two example services (`alice` and `bob`). Adjust names and ports as needed.

**3. Build the image**

```bash
./nanobot.sh build
```

**4. Run first-time setup**

```bash
./nanobot.sh onboard alice
```

This creates `nano_config/alice/` with the default workspace files.

**5. Configure** (`nano_config/alice/config.json`)

Add your API key, model, and (optionally) a chat channel:

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-sonnet-4-5"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

> Get API keys: [OpenRouter](https://openrouter.ai/keys) (recommended, access to all models) · [Brave Search](https://brave.com/search/api/) (optional, for web search)

**6. Start the service**

```bash
./nanobot.sh start alice
```

**7. (Optional) Personalize**

Edit files in `nano_config/alice/workspace/` to customize your agent:

- `AGENTS.md` — system prompt (instructions for the agent)
- `SOUL.md` — personality and tone
- `roundtables/*.yaml` — debate configurations

### Configuration Files

Each service has its own directory under `nano_config/<name>/`:

```
nano_config/alice/
├── config.json              # API keys, providers, channels, tools
├── cron/jobs.json           # Scheduled jobs
└── workspace/
    ├── AGENTS.md            # System prompt
    ├── SOUL.md              # Personality
    ├── USER.md              # User info
    ├── HEARTBEAT.md         # Periodic tasks
    ├── memory/              # MEMORY.md + HISTORY.md
    ├── skills/              # Custom skills
    ├── sessions/            # Conversation history
    └── roundtables/         # Debate configs (YAML)
```

| File | Purpose |
|------|---------|
| `config.json` | API keys, LLM providers, chat channels, MCP servers, security settings |
| `workspace/AGENTS.md` | System prompt — defines what the agent does and how it behaves |
| `workspace/SOUL.md` | Personality — tone, style, language preferences |
| `workspace/roundtables/*.yaml` | Roundtable debate configurations |

### Management Script

The `nanobot.sh` script wraps Docker Compose for easy management:

| Command | Description |
|---------|-------------|
| `./nanobot.sh build` | Build the Docker image |
| `./nanobot.sh start [service]` | Start services (all if omitted) |
| `./nanobot.sh stop [service]` | Stop services (all if omitted) |
| `./nanobot.sh restart [service]` | Restart services (all if omitted) |
| `./nanobot.sh logs [service]` | Follow logs (all if omitted) |
| `./nanobot.sh status` | Show running containers |
| `./nanobot.sh onboard <service>` | First-time setup for a service |
| `./nanobot.sh cli <service> <msg>` | Send a message to a service's agent |
| `./nanobot.sh reset <service>` | Remove workspace and re-onboard (preserves config.json) |
| `./nanobot.sh help` | Show usage help |

## Getting Started (Native — Development)

For local development or if you prefer running without Docker.

**1. Install**

```bash
git clone https://github.com/rmartignoni/council-nanobot.git
cd council-nanobot
pip install -e .
```

**2. Initialize**

```bash
nanobot onboard
```

**3. Configure** (`~/.nanobot/config.json`)

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-sonnet-4-5"
    }
  }
}
```

> Get API keys: [OpenRouter](https://openrouter.ai/keys) (recommended) · [Brave Search](https://brave.com/search/api/) (optional, for web search)

**4. Chat**

```bash
nanobot agent
```

## Chat Apps

Connect nanobot to your favorite chat platform.

| Channel | What you need |
|---------|---------------|
| **Telegram** | Bot token from @BotFather |
| **Discord** | Bot token + Message Content intent |
| **WhatsApp** | QR code scan |
| **Feishu** | App ID + App Secret |
| **Mochat** | Claw token (auto-setup available) |
| **DingTalk** | App Key + App Secret |
| **Slack** | Bot token + App-Level token |
| **Email** | IMAP/SMTP credentials |
| **QQ** | App ID + App Secret |

<details>
<summary><b>Telegram</b> (Recommended)</summary>

**1. Create a bot**
- Open Telegram, search `@BotFather`
- Send `/newbot`, follow prompts
- Copy the token

**2. Configure**

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

> You can find your **User ID** in Telegram settings. It is shown as `@yourUserId`.
> Copy this value **without the `@` symbol** and paste it into the config file.


**3. Run**

```bash
nanobot gateway
```

</details>

<details>
<summary><b>Mochat (Claw IM)</b></summary>

Uses **Socket.IO WebSocket** by default, with HTTP polling fallback.

**1. Ask nanobot to set up Mochat for you**

Simply send this message to nanobot (replace `xxx@xxx` with your real email):

```
Read https://raw.githubusercontent.com/HKUDS/MoChat/refs/heads/main/skills/nanobot/skill.md and register on MoChat. My Email account is xxx@xxx Bind me as your owner and DM me on MoChat.
```

nanobot will automatically register, configure `~/.nanobot/config.json`, and connect to Mochat.

**2. Restart gateway**

```bash
nanobot gateway
```

That's it — nanobot handles the rest!

<br>

<details>
<summary>Manual configuration (advanced)</summary>

If you prefer to configure manually, add the following to `~/.nanobot/config.json`:

> Keep `claw_token` private. It should only be sent in `X-Claw-Token` header to your Mochat API endpoint.

```json
{
  "channels": {
    "mochat": {
      "enabled": true,
      "base_url": "https://mochat.io",
      "socket_url": "https://mochat.io",
      "socket_path": "/socket.io",
      "claw_token": "claw_xxx",
      "agent_user_id": "6982abcdef",
      "sessions": ["*"],
      "panels": ["*"],
      "reply_delay_mode": "non-mention",
      "reply_delay_ms": 120000
    }
  }
}
```



</details>

</details>

<details>
<summary><b>Discord</b></summary>

**1. Create a bot**
- Go to https://discord.com/developers/applications
- Create an application → Bot → Add Bot
- Copy the bot token

**2. Enable intents**
- In the Bot settings, enable **MESSAGE CONTENT INTENT**
- (Optional) Enable **SERVER MEMBERS INTENT** if you plan to use allow lists based on member data

**3. Get your User ID**
- Discord Settings → Advanced → enable **Developer Mode**
- Right-click your avatar → **Copy User ID**

**4. Configure**

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

**5. Invite the bot**
- OAuth2 → URL Generator
- Scopes: `bot`
- Bot Permissions: `Send Messages`, `Read Message History`
- Open the generated invite URL and add the bot to your server

**6. Run**

```bash
nanobot gateway
```

</details>

<details>
<summary><b>WhatsApp</b></summary>

Requires **Node.js ≥18**.

**1. Link device**

```bash
nanobot channels login
# Scan QR with WhatsApp → Settings → Linked Devices
```

**2. Configure**

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

**3. Run** (two terminals)

```bash
# Terminal 1
nanobot channels login

# Terminal 2
nanobot gateway
```

</details>

<details>
<summary><b>Feishu (飞书)</b></summary>

Uses **WebSocket** long connection — no public IP required.

**1. Create a Feishu bot**
- Visit [Feishu Open Platform](https://open.feishu.cn/app)
- Create a new app → Enable **Bot** capability
- **Permissions**: Add `im:message` (send messages)
- **Events**: Add `im.message.receive_v1` (receive messages)
  - Select **Long Connection** mode (requires running nanobot first to establish connection)
- Get **App ID** and **App Secret** from "Credentials & Basic Info"
- Publish the app

**2. Configure**

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": []
    }
  }
}
```

> `encryptKey` and `verificationToken` are optional for Long Connection mode.
> `allowFrom`: Leave empty to allow all users, or add `["ou_xxx"]` to restrict access.

**3. Run**

```bash
nanobot gateway
```

> [!TIP]
> Feishu uses WebSocket to receive messages — no webhook or public IP needed!

</details>

<details>
<summary><b>QQ (QQ单聊)</b></summary>

Uses **botpy SDK** with WebSocket — no public IP required. Currently supports **private messages only**.

**1. Register & create bot**
- Visit [QQ Open Platform](https://q.qq.com) → Register as a developer (personal or enterprise)
- Create a new bot application
- Go to **开发设置 (Developer Settings)** → copy **AppID** and **AppSecret**

**2. Set up sandbox for testing**
- In the bot management console, find **沙箱配置 (Sandbox Config)**
- Under **在消息列表配置**, click **添加成员** and add your own QQ number
- Once added, scan the bot's QR code with mobile QQ → open the bot profile → tap "发消息" to start chatting

**3. Configure**

> - `allowFrom`: Leave empty for public access, or add user openids to restrict. You can find openids in the nanobot logs when a user messages the bot.
> - For production: submit a review in the bot console and publish. See [QQ Bot Docs](https://bot.q.qq.com/wiki/) for the full publishing flow.

```json
{
  "channels": {
    "qq": {
      "enabled": true,
      "appId": "YOUR_APP_ID",
      "secret": "YOUR_APP_SECRET",
      "allowFrom": []
    }
  }
}
```

**4. Run**

```bash
nanobot gateway
```

Now send a message to the bot from QQ — it should respond!

</details>

<details>
<summary><b>DingTalk (钉钉)</b></summary>

Uses **Stream Mode** — no public IP required.

**1. Create a DingTalk bot**
- Visit [DingTalk Open Platform](https://open-dev.dingtalk.com/)
- Create a new app -> Add **Robot** capability
- **Configuration**:
  - Toggle **Stream Mode** ON
- **Permissions**: Add necessary permissions for sending messages
- Get **AppKey** (Client ID) and **AppSecret** (Client Secret) from "Credentials"
- Publish the app

**2. Configure**

```json
{
  "channels": {
    "dingtalk": {
      "enabled": true,
      "clientId": "YOUR_APP_KEY",
      "clientSecret": "YOUR_APP_SECRET",
      "allowFrom": []
    }
  }
}
```

> `allowFrom`: Leave empty to allow all users, or add `["staffId"]` to restrict access.

**3. Run**

```bash
nanobot gateway
```

</details>

<details>
<summary><b>Slack</b></summary>

Uses **Socket Mode** — no public URL required.

**1. Create a Slack app**
- Go to [Slack API](https://api.slack.com/apps) → **Create New App** → "From scratch"
- Pick a name and select your workspace

**2. Configure the app**
- **Socket Mode**: Toggle ON → Generate an **App-Level Token** with `connections:write` scope → copy it (`xapp-...`)
- **OAuth & Permissions**: Add bot scopes: `chat:write`, `reactions:write`, `app_mentions:read`
- **Event Subscriptions**: Toggle ON → Subscribe to bot events: `message.im`, `message.channels`, `app_mention` → Save Changes
- **App Home**: Scroll to **Show Tabs** → Enable **Messages Tab** → Check **"Allow users to send Slash commands and messages from the messages tab"**
- **Install App**: Click **Install to Workspace** → Authorize → copy the **Bot Token** (`xoxb-...`)

**3. Configure nanobot**

```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "appToken": "xapp-...",
      "groupPolicy": "mention"
    }
  }
}
```

**4. Run**

```bash
nanobot gateway
```

DM the bot directly or @mention it in a channel — it should respond!

> [!TIP]
> - `groupPolicy`: `"mention"` (default — respond only when @mentioned), `"open"` (respond to all channel messages), or `"allowlist"` (restrict to specific channels).
> - DM policy defaults to open. Set `"dm": {"enabled": false}` to disable DMs.

</details>

<details>
<summary><b>Email</b></summary>

Give nanobot its own email account. It polls **IMAP** for incoming mail and replies via **SMTP** — like a personal email assistant.

**1. Get credentials (Gmail example)**
- Create a dedicated Gmail account for your bot (e.g. `my-nanobot@gmail.com`)
- Enable 2-Step Verification → Create an [App Password](https://myaccount.google.com/apppasswords)
- Use this app password for both IMAP and SMTP

**2. Configure**

> - `consentGranted` must be `true` to allow mailbox access. This is a safety gate — set `false` to fully disable.
> - `allowFrom`: Leave empty to accept emails from anyone, or restrict to specific senders.
> - `smtpUseTls` and `smtpUseSsl` default to `true` / `false` respectively, which is correct for Gmail (port 587 + STARTTLS). No need to set them explicitly.
> - Set `"autoReplyEnabled": false` if you only want to read/analyze emails without sending automatic replies.

```json
{
  "channels": {
    "email": {
      "enabled": true,
      "consentGranted": true,
      "imapHost": "imap.gmail.com",
      "imapPort": 993,
      "imapUsername": "my-nanobot@gmail.com",
      "imapPassword": "your-app-password",
      "smtpHost": "smtp.gmail.com",
      "smtpPort": 587,
      "smtpUsername": "my-nanobot@gmail.com",
      "smtpPassword": "your-app-password",
      "fromAddress": "my-nanobot@gmail.com",
      "allowFrom": ["your-real-email@gmail.com"]
    }
  }
}
```


**3. Run**

```bash
nanobot gateway
```

</details>

## Configuration

Config file: `~/.nanobot/config.json` (native) or `nano_config/<name>/config.json` (Docker)

### Providers

> [!TIP]
> - **Groq** provides free voice transcription via Whisper. If configured, Telegram voice messages will be automatically transcribed.
> - **Zhipu Coding Plan**: If you're on Zhipu's coding plan, set `"apiBase": "https://open.bigmodel.cn/api/coding/paas/v4"` in your zhipu provider config.
> - **MiniMax (Mainland China)**: If your API key is from MiniMax's mainland China platform (minimaxi.com), set `"apiBase": "https://api.minimaxi.com/v1"` in your minimax provider config.
> - **VolcEngine Coding Plan**: If you're on VolcEngine's coding plan, set `"apiBase": "https://ark.cn-beijing.volces.com/api/coding/v3"` in your volcengine provider config.

| Provider | Purpose | Get API Key |
|----------|---------|-------------|
| `custom` | Any OpenAI-compatible endpoint (direct, no LiteLLM) | — |
| `openrouter` | LLM (recommended, access to all models) | [openrouter.ai](https://openrouter.ai) |
| `anthropic` | LLM (Claude direct) | [console.anthropic.com](https://console.anthropic.com) |
| `openai` | LLM (GPT direct) | [platform.openai.com](https://platform.openai.com) |
| `deepseek` | LLM (DeepSeek direct) | [platform.deepseek.com](https://platform.deepseek.com) |
| `groq` | LLM + **Voice transcription** (Whisper) | [console.groq.com](https://console.groq.com) |
| `gemini` | LLM (Gemini direct) | [aistudio.google.com](https://aistudio.google.com) |
| `minimax` | LLM (MiniMax direct) | [platform.minimax.io](https://platform.minimax.io) |
| `aihubmix` | LLM (API gateway, access to all models) | [aihubmix.com](https://aihubmix.com) |
| `siliconflow` | LLM (SiliconFlow/硅基流动) | [siliconflow.cn](https://siliconflow.cn) |
| `volcengine` | LLM (VolcEngine/火山引擎) | [volcengine.com](https://www.volcengine.com) |
| `dashscope` | LLM (Qwen) | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com) |
| `moonshot` | LLM (Moonshot/Kimi) | [platform.moonshot.cn](https://platform.moonshot.cn) |
| `zhipu` | LLM (Zhipu GLM) | [open.bigmodel.cn](https://open.bigmodel.cn) |
| `vllm` | LLM (local, any OpenAI-compatible server) | — |
| `openai_codex` | LLM (Codex, OAuth) | `nanobot provider login openai-codex` |
| `github_copilot` | LLM (GitHub Copilot, OAuth) | `nanobot provider login github-copilot` |

<details>
<summary><b>OpenAI Codex (OAuth)</b></summary>

Codex uses OAuth instead of API keys. Requires a ChatGPT Plus or Pro account.

**1. Login:**
```bash
nanobot provider login openai-codex
```

**2. Set model** (merge into config):
```json
{
  "agents": {
    "defaults": {
      "model": "openai-codex/gpt-5.1-codex"
    }
  }
}
```

**3. Chat:**
```bash
nanobot agent -m "Hello!"
```

> Docker users: use `docker run -it` for interactive OAuth login.

</details>

<details>
<summary><b>Custom Provider (Any OpenAI-compatible API)</b></summary>

Connects directly to any OpenAI-compatible endpoint — LM Studio, llama.cpp, Together AI, Fireworks, Azure OpenAI, or any self-hosted server. Bypasses LiteLLM; model name is passed as-is.

```json
{
  "providers": {
    "custom": {
      "apiKey": "your-api-key",
      "apiBase": "https://api.your-provider.com/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "your-model-name"
    }
  }
}
```

> For local servers that don't require a key, set `apiKey` to any non-empty string (e.g. `"no-key"`).

</details>

<details>
<summary><b>vLLM (local / OpenAI-compatible)</b></summary>

Run your own model with vLLM or any OpenAI-compatible server, then add to config:

**1. Start the server** (example):
```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8000
```

**2. Add to config** (partial — merge into config):

*Provider (key can be any non-empty string for local):*
```json
{
  "providers": {
    "vllm": {
      "apiKey": "dummy",
      "apiBase": "http://localhost:8000/v1"
    }
  }
}
```

*Model:*
```json
{
  "agents": {
    "defaults": {
      "model": "meta-llama/Llama-3.1-8B-Instruct"
    }
  }
}
```

</details>

<details>
<summary><b>Adding a New Provider (Developer Guide)</b></summary>

nanobot uses a **Provider Registry** (`nanobot/providers/registry.py`) as the single source of truth.
Adding a new provider only takes **2 steps** — no if-elif chains to touch.

**Step 1.** Add a `ProviderSpec` entry to `PROVIDERS` in `nanobot/providers/registry.py`:

```python
ProviderSpec(
    name="myprovider",                   # config field name
    keywords=("myprovider", "mymodel"),  # model-name keywords for auto-matching
    env_key="MYPROVIDER_API_KEY",        # env var for LiteLLM
    display_name="My Provider",          # shown in `nanobot status`
    litellm_prefix="myprovider",         # auto-prefix: model → myprovider/model
    skip_prefixes=("myprovider/",),      # don't double-prefix
)
```

**Step 2.** Add a field to `ProvidersConfig` in `nanobot/config/schema.py`:

```python
class ProvidersConfig(BaseModel):
    ...
    myprovider: ProviderConfig = ProviderConfig()
```

That's it! Environment variables, model prefixing, config matching, and `nanobot status` display will all work automatically.

**Common `ProviderSpec` options:**

| Field | Description | Example |
|-------|-------------|---------|
| `litellm_prefix` | Auto-prefix model names for LiteLLM | `"dashscope"` → `dashscope/qwen-max` |
| `skip_prefixes` | Don't prefix if model already starts with these | `("dashscope/", "openrouter/")` |
| `env_extras` | Additional env vars to set | `(("ZHIPUAI_API_KEY", "{api_key}"),)` |
| `model_overrides` | Per-model parameter overrides | `(("kimi-k2.5", {"temperature": 1.0}),)` |
| `is_gateway` | Can route any model (like OpenRouter) | `True` |
| `detect_by_key_prefix` | Detect gateway by API key prefix | `"sk-or-"` |
| `detect_by_base_keyword` | Detect gateway by API base URL | `"openrouter"` |
| `strip_model_prefix` | Strip existing prefix before re-prefixing | `True` (for AiHubMix) |

</details>


### MCP (Model Context Protocol)

> [!TIP]
> The config format is compatible with Claude Desktop / Cursor. You can copy MCP server configs directly from any MCP server's README.

nanobot supports [MCP](https://modelcontextprotocol.io/) — connect external tool servers and use them as native agent tools.

Add MCP servers to your `config.json`:

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "my-remote-mcp": {
        "url": "https://example.com/mcp/",
        "headers": {
          "Authorization": "Bearer xxxxx"
        }
      }
    }
  }
}
```

Two transport modes are supported:

| Mode | Config | Example |
|------|--------|---------|
| **Stdio** | `command` + `args` | Local process via `npx` / `uvx` |
| **HTTP** | `url` + `headers` (optional) | Remote endpoint (`https://mcp.example.com/sse`) |

MCP tools are automatically discovered and registered on startup. The LLM can use them alongside built-in tools — no extra configuration needed.


### Security

> [!TIP]
> For production deployments, set `"restrictToWorkspace": true` in your config to sandbox the agent.

| Option | Default | Description |
|--------|---------|-------------|
| `tools.restrictToWorkspace` | `false` | When `true`, restricts **all** agent tools (shell, file read/write/edit, list) to the workspace directory. Prevents path traversal and out-of-scope access. |
| `channels.*.allowFrom` | `[]` (allow all) | Whitelist of user IDs. Empty = allow everyone; non-empty = only listed users can interact. |


## CLI Reference

| Command | Description |
|---------|-------------|
| `nanobot onboard` | Initialize config & workspace |
| `nanobot agent -m "..."` | Chat with the agent |
| `nanobot agent` | Interactive chat mode |
| `nanobot agent --no-markdown` | Show plain-text replies |
| `nanobot agent --logs` | Show runtime logs during chat |
| `nanobot gateway` | Start the gateway |
| `nanobot status` | Show status |
| `nanobot provider login openai-codex` | OAuth login for providers |
| `nanobot channels login` | Link WhatsApp (scan QR) |
| `nanobot channels status` | Show channel status |

Interactive mode exits: `exit`, `quit`, `/exit`, `/quit`, `:q`, or `Ctrl+D`.

<details>
<summary><b>Scheduled Tasks (Cron)</b></summary>

```bash
# Add a job
nanobot cron add --name "daily" --message "Good morning!" --cron "0 9 * * *"
nanobot cron add --name "hourly" --message "Check status" --every 3600

# List jobs
nanobot cron list

# Remove a job
nanobot cron remove <job_id>
```

</details>

## Docker Reference

### Multi-Instance with Docker Compose

The `docker-compose.yml` uses a YAML anchor (`&nanobot-base`) so all instances share the same base config:

```yaml
x-nanobot: &nanobot-base
  build:
    context: .
    dockerfile: Dockerfile
  command: ["gateway"]
  restart: unless-stopped
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 1G
      reservations:
        cpus: '0.25'
        memory: 256M

services:
  alice:
    <<: *nanobot-base
    container_name: nanobot-alice
    volumes:
      - ./nano_config/alice:/root/.nanobot
    ports:
      - "18791:18790"
```

**Adding a new instance:** duplicate a service block, change the name, container name, volume path, and port:

```yaml
  charlie:
    <<: *nanobot-base
    container_name: nanobot-charlie
    volumes:
      - ./nano_config/charlie:/root/.nanobot
    ports:
      - "18793:18790"
```

Then run:

```bash
./nanobot.sh onboard charlie
# edit nano_config/charlie/config.json
./nanobot.sh start charlie
```

### Single Instance with Docker

If you don't need Docker Compose, run a single container directly:

```bash
docker build -t nanobot .

docker run -v ~/.nanobot:/root/.nanobot --rm nanobot onboard
vim ~/.nanobot/config.json
docker run -v ~/.nanobot:/root/.nanobot -p 18790:18790 nanobot gateway

# Or run a single command
docker run -v ~/.nanobot:/root/.nanobot --rm nanobot agent -m "Hello!"
```

## Project Structure

```
nanobot/
├── agent/              # Core agent logic
│   ├── loop.py         #   Agent loop (LLM ↔ tool execution)
│   ├── context.py      #   Prompt builder
│   ├── memory.py       #   Persistent memory
│   ├── skills.py       #   Skills loader
│   ├── subagent.py     #   Background task execution
│   ├── debate/         #   Roundtable debate system
│   │   ├── config.py   #     Pydantic models (RoundtableConfig, PersonaConfig, etc.)
│   │   ├── persona.py  #     Persona inner loop
│   │   └── orchestrator.py  # Rounds, convergence, synthesis
│   └── tools/          #   Built-in tools (incl. spawn, debate)
├── skills/             # Bundled skills (github, weather, debate, tmux...)
├── roundtables/        # Bundled roundtable configs (copied on onboard)
├── channels/           # Chat channel integrations
├── bus/                # Message routing
├── cron/               # Scheduled tasks
├── heartbeat/          # Proactive wake-up
├── providers/          # LLM providers (OpenRouter, Anthropic, etc.)
├── session/            # Conversation sessions
├── config/             # Configuration (Pydantic schema)
└── cli/                # CLI commands
```

## Attribution

nanobot-council is a fork of [nanobot](https://github.com/HKUDS/nanobot) by [HKUDS](https://github.com/HKUDS). All credit for the core architecture, tools, providers, channels, and skills system goes to the original authors.

<p align="center">
  <sub>nanobot-council is for educational, research, and technical exchange purposes only</sub>
</p>
