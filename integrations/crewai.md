# CrewAI 集成

在 CrewAI Crew 任务执行完成后挂载 TrustEngine，对 AI 生成的代码进行自动安全审查。

## 安装

```bash
pip install audison crewai crewai-tools
```

## 场景说明

CrewAI Crew 完成代码生成任务后，将 `crew.kickoff()` 返回结果传给 TrustEngine 审查。同一场景：用户认证模块，发现密码哈希弱、缺少速率限制、SQL 注入。

## 代码示例

```python
from crewai import Agent, Task, Crew, Process
from audison import TrustEngine

# 1. 定义代码生成 Agent
coder = Agent(
    role="Python 后端工程师",
    goal="根据需求编写安全、可靠的 Python 代码",
    backstory="你是一位资深后端工程师，擅长编写认证系统。",
    allow_delegation=False,
)

# 2. 定义任务
code_task = Task(
    description="编写一个用户认证模块 auth.py，包含注册、登录功能",
    expected_output="完整的 Python 代码，包含 User 模型和认证逻辑",
    agent=coder,
)

# 3. 创建 Crew 并执行
crew = Crew(
    agents=[coder],
    tasks=[code_task],
    process=Process.sequential,
)

# 4. kickoff 返回结果
result = crew.kickoff()

# 5. 在输出端挂载 TrustEngine 审查
engine = TrustEngine()
report = engine.audit(
    requirement="检查 SQL 注入、密码哈希和认证漏洞",
    ai_output=str(result)
)

# 6. 根据审查结果决定是否部署
if report.verdict == "reject":
    print("代码有严重安全问题，已阻止部署")
    for f in report.findings:
        print(f"  [{f.severity}] {f.description}")
elif report.verdict == "review":
    print("代码存在问题，已提交人工 Review")
    for f in report.findings:
        print(f"  [{f.severity}] {f.description}")
else:
    print("审查通过，允许部署")
```

## 输出示例

```
代码有严重安全问题，已阻止部署
  [CRITICAL] SQL 注入：查询语句使用字符串拼接，未参数化
  [HIGH] 弱密码哈希：使用 SHA-256 而非 bcrypt/argon2
  [MEDIUM] 缺少速率限制：登录接口无尝试次数限制
```

## TrustReport 判定逻辑

```python
report = engine.audit(requirement="...", ai_output="...")

# report.verdict 取值：
#   "pass"   — 未发现符合审查需求的问题
#   "review" — 存在问题但非严重，建议人工 Review
#   "reject" — 存在严重问题，应阻止部署

# report.score        — 0-100 评分
# report.findings     — 问题列表
#   .severity         — "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
#   .description      — 问题描述
#   .suggestion       — 修复建议
```

## 典型工作流

```
┌───────────────┐     ┌──────────────┐     ┌──────────────┐
│ CrewAI        │────▶│ TrustEngine  │────▶│ 部署决策     │
│ crew.kickoff()│     │ .audit()     │     │ pass/review/ │
│               │     │              │     │ reject       │
└───────────────┘     └──────────────┘     └──────────────┘
```

1. CrewAI Crew 执行代码生成任务
2. `crew.kickoff()` 返回的字符串结果传入 `TrustEngine.audit()`
3. 根据 `report.verdict` 决策部署流程

## 进阶：多 Agent 协作 + 自动修复

```python
# 添加审查 Agent 和修复 Agent
reviewer = Agent(
    role="安全审查员",
    goal="审查代码安全性并给出修复建议",
    backstory="你是一位安全专家，专注于代码漏洞检测。",
)

fixer = Agent(
    role="代码修复工程师",
    goal="根据安全审查建议修复代码问题",
    backstory="你擅长快速修复安全漏洞。",
)

# 审查 Task
review_task = Task(
    description=lambda: f"审查以下代码的安全问题：\n{str(result)}",
    expected_output="安全问题列表和修复建议",
    agent=reviewer,
)

# 修复 Task
fix_task = Task(
    description=lambda: f"根据审查建议修复代码",
    expected_output="修复后的安全代码",
    agent=fixer,
)
```

## 与 LangChain 集成对比

| 特性 | LangChain | CrewAI |
|------|-----------|--------|
| 集成入口 | `agent.invoke()` 返回后 | `crew.kickoff()` 返回后 |
| 审查对象 | `result["output"]` | `str(result)` |
| 适用场景 | 单 Agent / Chain | 多 Agent 协作 |
| 代码量 | ~15 行 | ~20 行 |

两者接口一致，核心逻辑完全相同——在 AI 输出点挂载 TrustEngine，根据 verdict 决策。