# audison 集成指南

audison 提供了多种集成方式，从命令行一键审查到框架内部挂载 TrustEngine，覆盖不同工作流需求。

## 集成方式总览

| 集成方式 | 适用场景 | 代码行数 | 文档 |
|----------|----------|----------|------|
| CLI 命令行 | 本地快速审查、CI/CD 流水线、pre-commit hook | 1 行 | [cli.md](./cli.md) |
| LangChain | LangChain Agent / Chain 输出端挂载审查 | ~15 行 | [langchain.md](./langchain.md) |
| CrewAI | CrewAI Crew 任务输出后自动审查 | ~15 行 | [crewai.md](./crewai.md) |
| OpenAI SDK | 原生 LLM 调用后的通用审查 | ~12 行 | [openai-sdk.md](./openai-sdk.md) |

## 场景示例

所有示例围绕同一审查场景展开：

- **待审查代码**：一段 AI 生成的用户认证模块 `auth.py`
- **审查需求**：检查 SQL 注入和认证漏洞
- **发现问题**：密码哈希使用 SHA-256（弱哈希）、缺少登录速率限制、SQL 查询未使用参数化

每种集成方式都展示如何在同一场景下挂载 TrustEngine 并获取 TrustReport。

## 快速选择

- 只想在命令行跑一次 → [CLI](./cli.md)
- 项目已用 LangChain → [LangChain 集成](./langchain.md)
- 项目已用 CrewAI → [CrewAI 集成](./crewai.md)
- 直接用 OpenAI SDK 或通用 Python 项目 → [OpenAI SDK 集成](./openai-sdk.md)