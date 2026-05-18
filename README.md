<p align="center">
  <img src="docs/img/logo.svg" alt="AI Flow Architect" width="600" />
</p>

<p align="center">
  <strong>API-neutral, token-efficient multi-model workflow engine</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9%2B-3776AB.svg" alt="Python 3.9+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-4CAF50.svg" alt="License"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/status-alpha-FF9800.svg" alt="Alpha"></a>
  <a href="https://github.com/wdnmd1265/ai-flow-architect/actions"><img src="https://img.shields.io/badge/tests-107%20passing-4CAF50.svg" alt="Tests"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> · <a href="#how-it-works">How It Works</a> · <a href="#comparison">Comparison</a> · <a href="#roadmap">Roadmap</a> · <a href="#contributing">Contributing</a>
</p>

---

## The Problem

When you need **multiple AI roles to collaborate on a complex task**, calling a single GPT API doesn't cut it:

| Problem | What happens |
|---------|-------------|
| **Role bleeding** | Stuff all instructions into one context, AI confuses role boundaries, quality drops |
| **Quality black box** | No independent review — hallucinations and omissions go straight to delivery |
| **Token waste** | Redundant calls, bloated context, no skipping of unnecessary steps |

## The Fix

AI Flow Architect enforces a **fixed three-phase workflow** with two independently-moded "brains":

```
  User Input
     |
     v
+------------------------+
|  Brain #1 (Architect)  |  Clarify requirements -> Generate Blueprint -> User approves
|  Independent instance  |
+-----------+------------+
            | Approved Blueprint
            v
+------------------------+
|  Scheduler             |  Serial execution with 4 token-saving mechanisms
+-----------+------------+
            |
   +--------+--------+
   |        |        |       Each expert is an isolated session —
   v        v        v       no cross-contamination, formatted handoffs only
 Creative  Evaluator  Programmer  Reviewer
   |        |        |        |
   +--------+--------+--------+
            |
            v
+------------------------+
|  Brain #2 (Arbiter)   |  Compare blueprint vs deliverables item-by-item
|  DIFFERENT model      |  -> Pass: deliver | Fail: return for revision
+-----------+------------+
            |
            v
        Final Delivery
```

**Key design choices:**
- **Single key works out of the box** — if you omit brain2, it auto-selects a cheaper model from the same provider. One OpenAI key is enough to start.
- **Cross-provider is best** — OpenAI + Anthropic gives you the strongest quality arbitration. brain2 auto-resolves to a Claude model when both keys are present.
- **Different models matter** — same-model self-review lets hallucinations through. brain2 auto-chooses a different model even with one key.
- **Fixed workflow, not free orchestration** — you trade flexibility for predictability and quality control.
- **Every expert is session-isolated** — they don't know about each other, data passes through structured fields only.

## Comparison

| | AI Flow Architect | LangChain | CrewAI |
|---|---|---|---|
| **What it is** | Opinionated workflow engine | Orchestration framework | Agent framework |
| **Quality control** | Built-in (Brain #2 arbitration) | Manual / your responsibility | Optional |
| **Single API key** | ✅ Works out of the box | ✅ Works | ✅ Works |
| **Model isolation** | Auto-enforced (brain2 auto-resolves) | Not enforced | Not enforced |
| **Token saving** | 4 mechanisms, zero-config | Manual optimization | Manual optimization |
| **Flow control** | Fixed 3-phase pipeline | Free-form chains/agents | Configurable process |
| **Best for** | Predictable, auditable multi-AI workflows | Flexible pipeline composition | Role-based agent teams |

If you need maximum flexibility, use LangChain or CrewAI. If you need **auditable quality with minimal configuration**, this is it.

## Supported Providers

AI Flow Architect supports multiple API providers. Add new providers by updating `models.yaml` — no Python code changes needed.

| Provider | Models | API Key | Auto-fallback |
|----------|--------|---------|---------------|
| **OpenAI** | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo | `OPENAI_API_KEY` | ✅ |
| **Anthropic** | claude-3-5-sonnet, claude-3-haiku, claude-3-opus | `ANTHROPIC_API_KEY` | ✅ |
| **通义千问** | qwen-max, qwen-plus, qwen-turbo | `DASHSCOPE_API_KEY` | ✅ |
| **智谱 GLM** | glm-4, glm-4-flash, glm-3-turbo | `ZHIPU_API_KEY` | ✅ |
| **月之暗面** | moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k | `MOONSHOT_API_KEY` | ✅ |
| **DeepSeek** | deepseek-chat, deepseek-coder | `DEEPSEEK_API_KEY` | ✅ |
| **Ollama (本地)** | llama3, qwen2.5-coder, ... | 无需 API key | ✅ |

**Adding a new provider:**
1. Add provider config to `models.yaml` → `providers` section
2. Add model entries to `models.yaml` → `models` section
3. Add fallback paths to `models.yaml` → `fallbacks` section
4. Add API key to `.env.example`

See `models.yaml` for the full configuration structure.

## Token-Saving Mechanisms

All four work out of the box, zero configuration:

| Mechanism | How | Cost |
|-----------|-----|------|
| **Semantic cache** | Same expert+task combo hits cache, skips API call | 0 API calls |
| **Context compression** | History exceeds threshold -> auto-compress | ~60% fewer input tokens |
| **Local rule precheck** | Hardcoded rules (empty task / unknown expert / invalid complexity) reject before any API call | 0 cost |
| **Smart skip** | Current step fails -> skip remaining; all remaining are `low` complexity -> skip; explicit `skip_next` flag | 0 API calls |

## Quick Start

### 1. Install

```bash
git clone https://github.com/wdnmd1265/ai-flow-architect.git
cd ai-flow-architect
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
```

**Single key (works out of the box):**
```bash
OPENAI_API_KEY=sk-your-key
# brain2 auto-selects gpt-4o-mini — one API key is enough to start
```

**Dual key (recommended for best quality):**
```bash
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
# brain2 uses a Claude model → cross-provider arbitration is most effective
```

**Ollama (free, local):**
```bash
# Install: brew install ollama (macOS) or ollama.com
# Start: ollama serve
# Pull model: ollama pull llama3
# Then in config: "brain2": "ollama/llama3"
```

### 3. Run

```python
import asyncio
from ai_flow_architect import FlowArchitect

async def main():
    # Single key: brain2 auto-resolves to gpt-4o-mini
    # Dual key: brain2 defaults to your Anthropic model
    architect = FlowArchitect(config={
        "brain1": "gpt-4o",   # Planning & coordination
        # "brain2": optional — auto-selected if omitted
    })

    result = await architect.run("Design a user management system")

    if result["status"] == "success":
        print(f"Quality score: {result['audit_result'].get('score', 'N/A')}/100")
    else:
        for s in result.get("revision_suggestions", []):
            print(f"  - {s}")

asyncio.run(main())
```

### 4. What happens at runtime

```
============================================================
Task Blueprint
============================================================
Task ID: task_20260518_001
Description: Design a user management system
Estimated tokens: 5000

Steps:
  1. Requirements analysis [expert: evaluator]
     Task: Analyze functional and non-functional requirements...
  2. Architecture design [expert: creative]
     Task: Design system architecture and technical approach...
  3. Implementation [expert: programmer]
     Task: Implement core user management features...

============================================================

[A]pprove / [R]eject + feedback / [C]ancel: A
```

### 5. Run tests

```bash
pip install pytest pytest-asyncio
pytest tests/unit/ -v    # 107 tests
```

## Architecture Deep Dive

### Three-Layer Prompt System

Each expert receives a **three-layer prompt stack**:

1. **Global base** (hardcoded): "All output must be valid JSON, no fluff."
2. **Role preset** (from ExpertConfig): Domain-specific instructions
3. **Brain #1 task directive** (per-task): Specific instructions for the current task

This ensures output format consistency while allowing per-task customization. The scheduler checks for empty prompts at zero cost before any API call.

### Three-Level Error Handling

| Level | Trigger | Response |
|-------|---------|----------|
| **1 — Retry** | Timeout, rate limit (429), connection error | Exponential backoff, up to 3 retries |
| **2 — Fallback** | Model not found, auth error, quota exhausted | Switch to backup model (e.g. gpt-4o -> gpt-4o-mini), 1 retry |
| **3 — User decision** | All else fails | Prompt user: [R]etry / re[P]lan / [T]erminate |

### Field Filtering

Each expert declares `required_input_fields`. The scheduler extracts **only those fields** from previous step results and passes them in — no full context dump, no information overload.

```python
class ProgrammerExpert(BaseExpert):
    required_input_fields = {"architecture", "api_spec", "data_model"}
    # Scheduler extracts only these 3 fields from prior steps
```

## Built-in Expert Roles

| Role | Expert ID | Purpose |
|------|-----------|---------|
| Creative | `creative` | Innovation, design solutions, brainstorming |
| Evaluator | `evaluator` | Requirement analysis, feasibility assessment |
| Programmer | `programmer` | Code implementation, technical solutions |
| Reviewer | `reviewer` | Code review, quality control |

Create custom experts by subclassing `BaseExpert` and declaring `required_input_fields` + `output_format`.

## Project Structure

```
ai-flow-architect/
├── src/ai_flow_architect/
│   ├── __init__.py              # Exports FlowArchitect
│   ├── core/
│   │   ├── architect.py         # Three-phase orchestration + user approval loop
│   │   ├── scheduler.py         # Serial execution + 4 token-saving mechanisms
│   │   ├── context.py           # Session CRUD + history compression
│   │   └── cache.py             # CRUD + TTL + hit stats
│   ├── brains/
│   │   ├── brain_one.py         # Brain #1: requirement analysis + blueprint generation
│   │   └── brain_two.py         # Brain #2: quality arbitration
│   ├── experts/
│   │   ├── base.py              # BaseExpert + ExpertConfig + three-layer prompts
│   │   ├── creative.py          # CreativeExpert
│   │   ├── evaluator.py         # EvaluatorExpert
│   │   ├── programmer.py        # ProgrammerExpert
│   │   └── reviewer.py          # ReviewerExpert
│   └── utils/
│       ├── token_counter.py     # Token counting + cost estimation
│       ├── compressor.py        # Context compression
│       └── validator.py         # Input validation
├── tests/unit/                  # 107 unit tests
│   ├── test_scheduler.py        # 57 tests
│   ├── test_cache.py            # 22 tests
│   ├── test_context.py          # 18 tests
│   └── test_architect.py        # 10 tests
├── examples/
│   └── basic_usage.py
├── docs/
│   └── getting_started.md
├── .env.example
├── requirements.txt
├── setup.py
└── pyproject.toml
```

## Roadmap

- [ ] **PyPI package** — `pip install ai-flow-architect`
- [ ] **CLI interface** — `ai-flow run "design a system"`
- [ ] **Expert team templates** — Pre-configured teams for web dev, data analysis, content creation
- [ ] **Web UI** — Visual blueprint editor and execution monitor
- [ ] **More model providers** — Gemini, Mistral, local models via Ollama
- [ ] **Parallel execution** — Independent steps run concurrently
- [ ] **Streaming output** — Real-time expert output streaming

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

```bash
git clone https://github.com/wdnmd1265/ai-flow-architect.git
cd ai-flow-architect
pip install -e .
pytest tests/unit/ -v
```

## License

[Apache License 2.0](LICENSE)

---

<p align="center">
  <em>Predictable AI collaboration. Quality control baked into the architecture.</em>
</p>
