<p align="center">
  <img src="docs/img/logo.svg" alt="AI Flow Architect" width="600" />
</p>

<p align="center">
  <strong>开源 AI 输出审查中间件</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9%2B-3776AB.svg" alt="Python 3.9+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-4CAF50.svg" alt="License"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/status-alpha-FF9800.svg" alt="Alpha"></a>
  <a href="https://github.com/wdnmd1265/ai-flow-architect/actions"><img src="https://img.shields.io/badge/tests-177%20passing-4CAF50.svg" alt="Tests"></a>
</p>

<p align="center">
  <a href="#the-problem">The Problem</a> &middot;
  <a href="#trustengine">TrustEngine</a> &middot;
  <a href="#integrations">Integrations</a> &middot;
  <a href="#flowarchitect">FlowArchitect</a> &middot;
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#roadmap">Roadmap</a>
</p>

---

## The Problem

你让 GPT-4 写了一段用户管理代码，它看起来不错。API 设计合理，数据库连接正常。但 TrustEngine 在 1.8 秒内发现：密码哈希用了 MD5、登录端点缺少速率限制。

你信任了一个 AI 模型，它产生了安全幻觉。这不是因为 AI 有恶意——而是因为**单一模型没有机制发现自己的盲点**。

TrustEngine 在终端中的实际输出效果：
> 终端彩色 TrustReport 审查报告，展示 REJECT 结论、5 个 Findings（CRIT~LOW）、3 个风险点、多模型仲裁投票及证据链。完整截图见 [trustreport-cli.html](docs/img/trustreport-cli.html)。

### 三种接入方式

**CLI — 一行命令**

```bash
ai-flow audit query.sql -r "检查 SQL 注入和认证漏洞"
```

**Python SDK — 三行代码**

```python
from ai_flow_architect import TrustEngine
engine = TrustEngine()
report = engine.audit(requirement="实现用户管理系统", ai_output=generated_code)
```

**LangChain 集成 — 无缝配合**

```python
from ai_flow_architect import TrustEngine
from langchain.agents import create_openai_functions_agent

agent = create_openai_functions_agent(llm, tools, prompt)
result = agent.invoke({"input": "设计用户管理系统的数据库Schema"})

engine = TrustEngine()
report = engine.audit(requirement="数据库Schema设计", ai_output=result["output"])
```

---

## TrustEngine

TrustEngine 是独立的审查层：零状态、零交互、纯审计。

### 输出说明

```python
report.verdict       # "pass" | "review" | "reject" — 最终结论
report.confidence    # 0-100 — 置信度
report.findings      # 具体问题列表，含严重等级
report.uncertainty   # 引擎承认自己不确定的事项
report.evidence_chain # SHA-256 哈希 + 时间戳，可审计
```

### 对比

| | TrustEngine | Mira | 什么都不用 |
|---|---|---|---|
| 开源 | ✅ | ❌ | — |
| 多模型交叉审查 | ✅ | ✅ | ❌ |
| 不确定性透明 | ✅ | ❌ | ❌ |
| 证据链可追溯 | ✅ | ❌ | ❌ |
| 价格 | 免费 | $X/月 | 免费（风险自负） |

### 关键设计

- **单 API 密钥即可运行。** 省略 brain2 参数时自动选择同提供商的廉价模型。一个 OpenAI Key 就够。
- **跨提供商审查效果最好。** OpenAI + Anthropic 组合因训练数据和失败模式不同，提供最强的仲裁能力。
- **固定的质量流水线。** 用灵活性换可预测性——每个任务走相同的质量控制流程。
- **专家会话隔离。** 各专家互不知晓彼此存在，数据仅通过结构化字段传递。

---

## Integrations

同一场景：审查一段 AI 生成的代码。选择最适合你的集成方式。

| 集成方式 | 代码量 | 示例 |
|----------|--------|------|
| CLI | 1 行 | `ai-flow audit output.py -r "检查安全漏洞"` — [详情](integrations/cli.md) |
| Python | 3 行 | `TrustEngine().audit(requirement=..., ai_output=...)` — [详情](integrations/python.md) |
| LangChain | 3 行 | `agent.run()` + `engine.audit()` — [详情](integrations/langchain.md) |
| CrewAI | 4 行 | `crew.kickoff()` + `engine.audit()` — [详情](integrations/crewai.md) |
| OpenAI SDK | 5 行 | `client.chat.completions.create()` + `engine.audit()` — [详情](integrations/openai-sdk.md) |
| GitHub Action | YAML | 引用 `.github/workflows/audit.yml` — [查看](.github/workflows/audit.yml) |

---

## FlowArchitect

### 进阶：完整工作流

如果审查 AI 输出还不够——你想要 AI 在生成阶段就接受审查。

```
  You: "Design a user management system"
         |
         v
+--------------------+
| Brain #1 (Planner) |  Analyzes requirements, generates blueprint
| Model: GPT-4o      |  with risk annotations
+--------+-----------+
         |
         v
+--------------------+
| Opponent Brain     |  5 adversarial perspectives challenge the plan
+--------+-----------+
         |
    [You review and approve]
         |
         v
+--------------------+
| Expert Team        |  Isolated sessions. Structured handoffs only.
+--------+-----------+
         |
         v
+--------------------+
| Brain #2 (Arbiter) |  Cross-model review. Different blind spots.
| Model: Claude      |
+--------+-----------+
         |
         v
     Quality report, not a gamble.
```

```python
import asyncio
from ai_flow_architect import FlowArchitect

async def main():
    architect = FlowArchitect(config={"brain1": "gpt-4o"})
    result = await architect.run("Design a user management system")
    if result["status"] == "success":
        print(f"Quality score: {result['audit_result'].get('score', 'N/A')}/100")

asyncio.run(main())
```

→ 详细文档: [docs/flow-architect.md](docs/flow-architect.md)

---

## Quick Start

### 安装

```bash
git clone https://github.com/wdnmd1265/ai-flow-architect.git
cd ai-flow-architect
pip install -e .
```

### 配置

```bash
cp .env.example .env
```

**单 API 密钥（开箱即用）：**
```bash
OPENAI_API_KEY=sk-your-key
# brain2 自动选择 gpt-4o-mini，一个 Key 即可启动
```

**双 API 密钥（推荐，审查质量最高）：**
```bash
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
# brain2 使用 Claude 模型，跨提供商仲裁效果最佳
```

### 运行测试

```bash
pip install pytest pytest-asyncio
pytest tests/unit/ -v    # 177 tests
```

---

## Project Structure

```
ai-flow-architect/
├── src/ai_flow_architect/
│   ├── __init__.py              # Exports FlowArchitect, TrustEngine, TrustReport
│   ├── core/
│   │   ├── architect.py         # Three-phase orchestration + user approval loop
│   │   ├── scheduler.py         # Serial execution + 4 token-saving mechanisms
│   │   ├── context.py           # Session CRUD + history compression
│   │   └── cache.py             # CRUD + TTL + hit stats
│   ├── brains/
│   │   ├── brain_one.py         # Brain #1: requirement analysis + blueprint generation
│   │   ├── brain_two.py         # Brain #2: quality arbitration (cross-model)
│   │   └── brain_opponent.py    # Opponent Brain: 5 adversarial review styles
│   ├── experts/
│   │   ├── base.py              # BaseExpert + ExpertConfig + three-layer prompts
│   │   ├── creative.py          # CreativeExpert
│   │   ├── evaluator.py         # EvaluatorExpert
│   │   ├── programmer.py        # ProgrammerExpert
│   │   └── reviewer.py          # ReviewerExpert
│   ├── engine/                  # TrustEngine — standalone audit layer
│   │   ├── trust_engine.py      # Core audit interface
│   │   ├── trust_report.py      # TrustReport schema + serialization
│   │   └── audit_context.py     # AuditContext for project metadata
│   └── utils/
│       ├── llm_client.py        # Unified LLM client (8 providers)
│       ├── token_counter.py     # Token counting + cost estimation
│       ├── compressor.py        # Context compression (4 strategies)
│       └── validator.py         # Input validation
├── tests/unit/                  # 177 unit tests
├── integrations/                # Integration guides
│   ├── cli.md
│   ├── python.md
│   ├── langchain.md
│   ├── crewai.md
│   └── openai-sdk.md
├── docs/
│   ├── flow-architect.md
│   ├── getting_started.md
│   └── img/
├── .env.example
├── pyproject.toml
└── models.yaml                  # Provider + model configuration
```

---

## Roadmap

- [ ] **PyPI package** — `pip install ai-flow-architect`
- [x] **CLI interface** — `ai-flow audit "..."` with custom review rules
- [x] **Expert execution layer** — Real LLM calls with tool support
- [x] **TrustEngine** — Standalone audit layer with multi-arbiter + adversarial + evidence chain
- [ ] **Expert team templates** — Pre-configured teams for web dev, data analysis, content creation
- [ ] **Web UI** — Visual blueprint editor and execution monitor
- [ ] **DeepSeek verification** — Most cost-effective provider, high priority for community validation
- [x] **Model providers** — OpenAI + Anthropic production-tested, 5 more via OpenAI-compatible protocol
- [ ] **Parallel execution** — Independent steps run concurrently
- [ ] **Streaming output** — Real-time expert output streaming

---

## Contributing

Contributions are welcome — especially provider verification PRs. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
git clone https://github.com/wdnmd1265/ai-flow-architect.git
cd ai-flow-architect
pip install -e .
pytest tests/unit/ -v    # 177 tests
```

## License

[Apache License 2.0](LICENSE) — Copyright 2026 盛鑫

---

<p align="center">
  <em>AI generates. AI challenges. You decide. This is how we solve hallucination.</em>
</p>