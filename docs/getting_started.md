# Getting Started

## Prerequisites

- Python 3.9+
- API keys from **two different AI providers** (e.g. OpenAI + Anthropic)

## Installation

```bash
git clone https://github.com/wdnmd1265/ai-flow-architect.git
cd ai-flow-architect
pip install -e .
```

## Configuration

### Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Required — you need keys from two different providers
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key

# Optional — Redis for persistent cache (default: in-memory)
# REDIS_URL=redis://localhost:6379/0
```

### Why Two Providers?

Brain #2 (quality arbiter) MUST use a different model from Brain #1. Same-model self-review is the primary cause of hallucination leakage in multi-AI systems. The framework enforces this at initialization — `FlowArchitect()` without a `brain2` config will raise `ValueError`.

## Basic Usage

```python
import asyncio
from ai_flow_architect import FlowArchitect

async def main():
    # Brain #2 is mandatory and must use a different model
    architect = FlowArchitect(config={
        "brain1": "gpt-4o",
        "brain2": "claude-3-5-sonnet-20241022",
    })

    # Enter a vague requirement — the framework handles the rest
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
from ai_flow_architect import FlowArchitect

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
from ai_flow_architect.core.architect import Blueprint

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
pytest tests/unit/ --cov=ai_flow_architect --cov-report=term-missing
```

## FAQ

### Q: Why must Brain #2 use a different model?

If both brains use the same model, it's effectively "self-review" — the same model that generated the output is judging it. Hallucinations and omissions that the model is prone to won't be caught by itself. Forcing a different model creates genuine adversarial quality control.

### Q: What happens if I don't pass a config?

`FlowArchitect()` without config will raise `ValueError: 配置错误：必须配置 brain2 模型`. Brain #2 is not optional.

### Q: Which AI models are supported?

Any model accessible via the OpenAI or Anthropic SDKs. Brain #1 and Brain #2 just need to be from different model families — e.g. GPT-4o + Claude 3.5 Sonnet, or GPT-4 + GPT-3.5 (different capability tiers).

### Q: Can I add custom expert roles?

Yes. Subclass `BaseExpert`, declare `required_input_fields` and `output_format`, and register it in the scheduler's expert registry.
