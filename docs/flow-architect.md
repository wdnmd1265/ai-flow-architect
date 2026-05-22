# FlowArchitect

FlowArchitect 是 AI Flow Architect 的完整工作流框架，将 AI 输出审查提前到生成阶段。

## 核心思想

不是等 AI 生成完再审查——而是在生成过程中引入对抗性审查。两个独立 AI 大脑，一个负责规划，一个负责挑战，第三个大脑做最终仲裁。

## 三脑架构

```
  You: "Design a user management system"
         |
         v
+--------------------+
| Brain #1 (Planner) |  Analyzes requirements, generates a step-by-step blueprint
| Model: GPT-4o      |  with risk annotations and alternative approaches
+--------+-----------+
         |
         v
+--------------------+
| Opponent Brain     |  Challenges the blueprint from adversarial perspectives:
| (5 review styles)  |  Security audit, cost analysis, user empathy, data rigor, minimalism
+--------+-----------+
         |
    [You review and approve the blueprint]
         |
         v
+--------------------+
| Expert Team        |  Each expert runs in an isolated session.
| Creative           |  No cross-contamination. Structured handoffs only.
| Evaluator          |
| Programmer         |
| Reviewer           |
+--------+-----------+
         |
         v
+--------------------+
| Brain #2 (Arbiter) |  Compares the blueprint against deliverables item-by-item.
| Model: Claude      |  Cross-model review. Different model = different blind spots.
+--------+-----------+
         |
         v
     You get: a quality report, not a gamble.
```

## FlowArchitect vs LangChain vs CrewAI

| | FlowArchitect | LangChain | CrewAI |
|---|---|---|---|
| **Philosophy** | Adversarial quality control | Flexible pipeline composition | Role-based agent teams |
| **Quality control** | Built-in (dual-brain arbitration + opponent review) | Manual — your responsibility | Optional |
| **Single API key** | Works out of the box | Works | Works |
| **Model isolation** | Auto-enforced (brain2 auto-resolves to different model) | Not enforced | Not enforced |
| **Token saving** | 4 mechanisms, zero-config | Manual optimization | Manual optimization |
| **Flow control** | Fixed 3-phase pipeline with user approval gate | Free-form chains/agents | Configurable process |
| **Best for** | Auditable quality. You need to trust the output. | Maximum flexibility. You own the pipeline. | Multi-agent simulations. |
| **Integration** | Three tiers: Skill → API → Full framework | Framework-first | Framework-first |

## 快速开始

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

详细文档请参考本目录下的其他文档和项目 README。