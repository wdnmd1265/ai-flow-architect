# Getting Started

## Prerequisites

- Python 3.9+
- At least one API key from a supported provider (OpenAI or Anthropic recommended)

**Single key works.** If you only have an OpenAI key, Brain #2 auto-selects a cheaper model from the same provider (e.g. gpt-4o-mini). Cross-provider (OpenAI + Anthropic) gives the strongest quality arbitration, but is not required.

## Installation

```bash
git clone https://github.com/wdnmd1265/audison.git
cd audison
pip install -e .
```

## Configuration

### Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

**Single key (works out of the box):**
```bash
OPENAI_API_KEY=sk-your-openai-api-key
# Brain #2 auto-resolves to a cheaper model from the same provider
```

**Dual key (recommended for best quality):**
```bash
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key
# Cross-provider arbitration is most effective against hallucinations
```

**Optional — Redis for persistent cache (default: in-memory)**
```bash
# REDIS_URL=redis://localhost:6379/0
```

### Why Cross-Provider Matters

Brain #2 (quality arbiter) should ideally use a different model from Brain #1. Same-model self-review is the primary cause of hallucination leakage in multi-AI systems — a model cannot reliably catch its own blind spots. Different models have different failure modes, creating genuine adversarial quality control.

**If you only have one key, don't worry** — the framework auto-selects a different model tier from the same provider (e.g. gpt-4o for Brain #1, gpt-4o-mini for Brain #2).

## Basic Usage

```python
import asyncio
from audison import FlowArchitect

async def main():
    # Single key: brain2 auto-resolves
    architect = FlowArchitect(config={
        "brain1": "gpt-4o",
        # "brain2" is optional — auto-selected if omitted
    })

    # Dual key: explicit brain2 for cross-provider arbitration
    # architect = FlowArchitect(config={
    #     "brain1": "gpt-4o",
    #     "brain2": "claude-3-5-sonnet-20241022",
    # })

    result = await architect.run("Design a user management system")

    if result["status"] == "success":
        audit = result["audit_result"]
        print(f"Quality score: {audit.get('score', 'N/A')}/100")
    elif result["status"] == "needs_revision":
        print("Quality check failed. Suggestions:")
        for s in result.get("revision_suggestions", []):
            print(f"  - {s}")

asyncio.run(main())
```

## Workflow Walkthrough

When you call `architect.run()`, three phases execute automatically:

### Phase 1: Planning

Brain #1 analyzes your requirement and generates a **Task Blueprint** containing:
- Step-by-step execution plan
- Expert assignment for each step
- Estimated token consumption

### Phase 2: Approval

The blueprint is printed to your terminal. You can:

| Key | Action |
|-----|--------|
| **A** | Approve the blueprint and proceed |
| **R** | Reject with feedback — Brain #1 revises the blueprint |
| **C** | Cancel the task entirely |

Example:

```
============================================================
Task Blueprint
============================================================
Task ID: task_20260518_001
Description: Design a user management system
Estimated tokens: 5000

Steps:
  1. Requirements analysis [expert: evaluator]
  2. Architecture design [expert: creative]
  3. Implementation [expert: programmer]

============================================================

[A]pprove / [R]eject + feedback / [C]ancel: A
```

### Phase 3: Execution + Arbitration

1. The scheduler executes each step serially
2. Each expert runs in an **isolated session** — no cross-contamination
3. After all steps complete, Brain #2 compares the blueprint against deliverables
4. If the quality check passes -> delivery. If not -> revision suggestions

## Using Expert Teams

```python
import asyncio
from audison import FlowArchitect

async def main():
    architect = FlowArchitect(config={
        "brain1": "gpt-4o",
        "brain2": "claude-3-5-sonnet-20241022",
    })

    result = await architect.run_with_team(
        "web_development",
        "Build a blog platform",
    )

    print(f"Status: {result['status']}")

asyncio.run(main())
```

## Custom Blueprint

```python
from audison.core.architect import Blueprint

blueprint = Blueprint(
    task_id="custom_001",
    description="Data analysis pipeline",
    steps=[
        {
            "name": "Data collection",
            "expert": "evaluator",
            "task": "Collect and organize data sources",
            "prompt": "As an evaluator, analyze the following data requirements...",
            "complexity": "medium",
        },
        {
            "name": "Data cleaning",
            "expert": "programmer",
            "task": "Clean and preprocess data",
            "prompt": "As a programmer, write data cleaning scripts...",
            "complexity": "high",
        },
    ],
    experts=["evaluator", "programmer"],
    estimated_tokens=8000,
    status="draft",
)
```

Note: Each step requires a `prompt` field. The scheduler's local rule precheck will reject steps with empty prompts — this is a zero-cost safeguard.

## Token-Saving Mechanisms

All four mechanisms are active by default, no configuration needed:

| Mechanism | Trigger | Effect |
|-----------|---------|--------|
| Semantic cache | Same expert+task combination appears again | Skip API call, return cached result |
| Context compression | Session history exceeds threshold | Auto-compress, reduce input tokens |
| Local rule precheck | Empty task / unknown expert / invalid complexity / empty prompt | Reject before any API call — zero cost |
| Smart skip | Current step fails / all remaining are `low` / `skip_next` flag | Skip subsequent steps |

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all unit tests
pytest tests/unit/ -v

# With coverage report
pytest tests/unit/ --cov=audison --cov-report=term-missing
```

## FAQ

### Q: Do I need two different API providers?

No. A single API key (e.g. OpenAI) works. The framework auto-selects a different model tier for Brain #2. Cross-provider (OpenAI + Anthropic) is recommended for the strongest quality control, but is not required.

### Q: Why use a different model for Brain #2?

If both brains use the same model, it's effectively "self-review" — the same model that generated the output is judging it. Hallucinations and omissions that the model is prone to won't be caught by itself. A different model (even a cheaper one from the same provider) creates genuine adversarial quality control.

### Q: Which AI models are supported?

OpenAI (GPT-4o / GPT-4o-mini / GPT-4-turbo / GPT-3.5-turbo) and Anthropic (Claude 3.5 Sonnet / Haiku / Opus) are fully tested. Five additional providers (DashScope, Zhipu, Moonshot, DeepSeek, Ollama) are supported through OpenAI-compatible protocol and await community verification. See models.yaml for the full configuration.

### Q: Can I add custom expert roles?

Yes. Subclass `BaseExpert`, declare `required_input_fields` and `output_format`, and register it in the scheduler's expert registry.
