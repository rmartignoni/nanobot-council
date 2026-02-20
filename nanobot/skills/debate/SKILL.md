---
name: debate
description: "Multi-persona roundtable debate system. Use when the user wants diverse expert perspectives, strategic analysis, or structured discussion with multiple viewpoints on a question."
metadata: '{"nanobot":{"emoji":"🎙️"}}'
---

# Debate (Roundtable)

Start structured multi-persona debates where multiple experts with different perspectives discuss a question across rounds.

## When to Use

- User asks for strategic advice or complex decisions
- User wants multiple perspectives on a topic
- User explicitly asks for a "debate", "roundtable", or "council"
- Questions like "should we...", "what's the best approach to...", "pros and cons of..."

## How It Works

1. Call the `debate` tool with a `question` and optional `roundtable` name
2. Multiple personas analyze the question in parallel (round 1)
3. In subsequent rounds, each persona sees the full transcript and reacts/refines
4. The orchestrator checks for convergence — stops early if personas agree
5. A synthesis LLM produces the final structured recommendation

## Tool Usage

```
debate(question: str, roundtable: str = None)
```

- `question`: The topic to debate (required)
- `roundtable`: Name of the roundtable config (optional — uses first available if omitted)

## Roundtable Configuration

Roundtables are YAML files in `workspace/roundtables/`. Each defines:

- **Personas**: Name, system prompt, LLM model, temperature, allowed tools
- **Rounds**: Min/max rounds, convergence detection
- **Orchestrator**: Model for synthesis, synthesis prompt

### Example: `workspace/roundtables/strategy-council.yaml`

```yaml
name: Strategy Council
description: Executive team debate for strategic decisions
trigger: auto

orchestrator:
  model: anthropic/claude-haiku-4-5
  synthesis_prompt: |
    Synthesize the debate into a clear recommendation with rationale,
    noting points of agreement and disagreement.

rounds:
  max: 3
  min: 1
  convergence: true

personas:
  - name: CFO
    system_prompt: |
      You are the CFO. Evaluate by financial viability, ROI,
      cash flow impact and risk-adjusted returns.
    model: openai/gpt-4o
    temperature: 0.5
    tools: [web_search, web_fetch]

  - name: CTO
    system_prompt: |
      You are the CTO. Evaluate by technical feasibility,
      scalability and engineering effort.
    model: deepseek/deepseek-chat
    temperature: 0.7
    tools: [web_search, web_fetch, exec]

  - name: CEO
    system_prompt: |
      You are the CEO. Holistic view: market, competition,
      team capabilities and long-term vision.
    model: anthropic/claude-haiku-4-5
    temperature: 0.7
    tools: [web_search, web_fetch]
```

### Persona Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name (e.g. "CFO", "Devil's Advocate") |
| `system_prompt` | Yes | Persona's role and evaluation criteria |
| `model` | No | LLM model (defaults to agent's model) |
| `temperature` | No | Sampling temperature (defaults to agent's) |
| `max_tokens` | No | Max response tokens (defaults to agent's) |
| `tools` | No | List of tool names the persona can use |

### Allowed Persona Tools

Personas can use: `read_file`, `write_file`, `edit_file`, `list_dir`, `exec`, `web_search`, `web_fetch`, and any MCP tools.

Personas **cannot** use: `message`, `spawn`, `debate`, `cron` (agent-level only).

### Orchestrator Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `model` | Agent's model | LLM for convergence check and synthesis |
| `synthesis_prompt` | Generic synthesis | Instructions for producing the final output |

### Rounds Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `max` | 3 | Maximum debate rounds |
| `min` | 1 | Minimum rounds before convergence check |
| `convergence` | true | Stop early if personas agree |

## Creating a New Roundtable

1. Create a YAML file in `workspace/roundtables/` (e.g. `my-council.yaml`)
2. Define at least 2 personas with distinct perspectives
3. Set `rounds.max` based on complexity (2-3 for most topics)
4. Use `convergence: true` to avoid unnecessary rounds
5. Each persona can use a different LLM provider

## Cost Considerations

A typical debate (3 personas, 3 rounds + synthesis) makes ~10 LLM calls. The transcript grows each round as personas see full history. Convergence detection reduces unnecessary rounds.
