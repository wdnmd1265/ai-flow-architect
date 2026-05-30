# LangChain 集成

在 LangChain Agent 或 Chain 的输出端挂载 TrustEngine，对 AI 生成的代码进行自动安全审查。

## 安装

```bash
pip install audison langchain langchain-openai
```

## 场景说明

假设用 LangChain Agent 生成用户认证模块 `auth.py`，TrustEngine 审查后发现密码哈希弱、缺少速率限制、SQL 注入风险，阻止部署。

## 代码示例

```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from audison import TrustEngine

# 1. 创建 LangChain Agent
llm = ChatOpenAI(model="gpt-4o")
agent = create_openai_tools_agent(llm, tools=[])
executor = AgentExecutor(agent=agent, tools=[])

# 2. 让 Agent 生成代码
result = executor.invoke({"input": "写一个用户认证模块的 Python 代码"})

# 3. 在输出端挂载 TrustEngine 审查
engine = TrustEngine()
report = engine.audit(
    requirement="检查 SQL 注入、密码哈希和认证漏洞",
    ai_output=result["output"]
)

# 4. 根据审查结果决定是否部署
if report.verdict == "reject":
    print("代码有严重安全问题，已阻止部署")
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

# report.score 为 0-100 评分

# report.findings 为问题列表，每项包含：
#   .severity   — "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
#   .description — 问题描述
#   .location    — 代码位置（如有）
#   .suggestion  — 修复建议（如有）
```

## 典型工作流

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ LangChain   │────▶│ TrustEngine  │────▶│ 部署决策     │
│ Agent 生成  │     │ .audit()     │     │ pass/review/ │
│             │     │              │     │ reject       │
└─────────────┘     └──────────────┘     └──────────────┘
```

1. LangChain Agent 根据用户需求生成代码
2. 将 `result["output"]` 传入 `TrustEngine.audit()`
3. 根据 `report.verdict` 决策：
   - `"pass"` → 直接部署
   - `"review"` → 发送给人工 Review
   - `"reject"` → 阻止部署，将 findings 返回给 Agent 修复

## 进阶：自动修复循环

```python
max_retries = 3
for attempt in range(max_retries):
    result = executor.invoke({"input": "写一个用户认证模块"})
    report = engine.audit(
        requirement="检查 SQL 注入、密码哈希和认证漏洞",
        ai_output=result["output"]
    )

    if report.verdict == "pass":
        print("审查通过")
        break

    # 将问题反馈给 Agent 修复
    feedback = "\n".join(f.desc for f in report.findings)
    executor.invoke({
        "input": f"修复以下安全问题后重新生成代码：\n{feedback}"
    })
```

首次运行 3-5 行即可完成基本集成，后续可按需扩展自动修复、通知等能力。