# OpenAI SDK 集成

最底层的集成方式——直接用 OpenAI SDK 调用 LLM 后，用 TrustEngine 审查输出。不依赖任何 Agent 框架，适用于所有 Python 项目。

## 安装

```bash
pip install audison openai
```

## 场景说明

用 OpenAI SDK 直接调用 GPT-4o 生成用户认证模块，TrustEngine 审查后发现密码哈希弱、缺少速率限制、SQL 注入风险，阻止部署。

## 代码示例

```python
from openai import OpenAI
from audison import TrustEngine

# 1. 用 OpenAI SDK 生成代码
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "你是一个 Python 后端工程师。"
        },
        {
            "role": "user",
            "content": "写一个用户认证模块 auth.py，包含注册和登录功能"
        }
    ]
)

ai_output = response.choices[0].message.content

# 2. 挂载 TrustEngine 审查
engine = TrustEngine()
report = engine.audit(
    requirement="检查 SQL 注入、密码哈希和认证漏洞",
    ai_output=ai_output
)

# 3. 根据审查结果决策
if report.verdict == "reject":
    print("代码有严重安全问题，已阻止部署")
    for f in report.findings:
        print(f"  [{f.severity}] {f.description}")
elif report.verdict == "review":
    print("代码存在问题，建议人工 Review")
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

## TrustReport 对象

```python
report = engine.audit(requirement="...", ai_output="...")

# 属性一览
report.verdict    # "pass" | "review" | "reject"
report.score      # int, 0-100
report.findings   # list[Finding]
report.raw        # 原始审查报告文本

# Finding 对象
finding.severity      # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
finding.description   # str
finding.location      # str | None
finding.suggestion    # str | None
```

## 典型工作流

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ OpenAI SDK   │────▶│ TrustEngine  │────▶│ 部署决策     │
│ chat.create()│     │ .audit()     │     │ pass/review/ │
│              │     │              │     │ reject       │
└──────────────┘     └──────────────┘     └──────────────┘
```

1. 用 `client.chat.completions.create()` 生成代码
2. 提取 `response.choices[0].message.content`
3. 传入 `TrustEngine.audit()` 审查
4. 根据 `report.verdict` 决策

## 进阶：流式输出 + 审查

```python
from openai import OpenAI
from audison import TrustEngine

client = OpenAI()

# 流式生成代码
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "写一个用户认证模块"}],
    stream=True,
)

# 收集完整输出
chunks = []
for chunk in stream:
    if chunk.choices[0].delta.content:
        chunks.append(chunk.choices[0].delta.content)
        print(chunk.choices[0].delta.content, end="", flush=True)

ai_output = "".join(chunks)

# 审查完整输出
engine = TrustEngine()
report = engine.audit(
    requirement="检查 SQL 注入和认证漏洞",
    ai_output=ai_output
)
```

## 适用场景

由于不依赖任何 Agent 框架，OpenAI SDK 集成是最通用的方案：

- 任何直接调用 LLM API 的 Python 项目
- 使用 LiteLLM、Anthropic SDK 等其他 SDK 的项目（替换 `client` 即可）
- 作为 LangChain / CrewAI 集成的底层参考实现
- 微服务架构中的独立审查服务