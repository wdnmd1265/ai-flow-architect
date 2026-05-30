# AI Trust Engine — Skill

审查 AI 生成的代码、方案、文章，克服 AI 幻觉。

## 触发条件

当用户要求审查 AI 产出、检查代码安全性、验证方案可靠性时使用。

## 使用方式

### 作为独立审查（推荐）

```python
from audison.engine import TrustEngine

engine = TrustEngine(brain1="gpt-4o", brain2="claude-3-5-sonnet")
report = await engine.audit(requirement="需求描述", ai_output="AI产出内容")

print(report.summary())
# ❌ REJECT | 置信度 40/100 | 发现 3 个问题 | 风险 2 个 | 不确定 1 项

print(report.to_markdown())
# 完整 Markdown 报告
```

### 作为 API 服务

```bash
# 启动服务
uvicorn audison.api:app --host 0.0.0.0 --port 8000

# 调用审查
curl -X POST http://localhost:8000/audit \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "用户登录系统",
    "ai_output": "def login(user, pwd): ..."
  }'
```

### 作为 FlowArchitect 内部组件

```python
from audison import FlowArchitect

architect = FlowArchitect()
result = await architect.execute("用户登录系统")

# result 中自动包含 trust_report
print(result["trust_report"])
```

## 输出格式

TrustReport 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| version | str | 报告版本 |
| timestamp | str | 审查时间 |
| verdict | str | 结论：pass / review / reject |
| confidence | float | 置信度 0-100 |
| findings | list | 发现的问题 |
| risks | list | 风险点 |
| arbiters | list | 审查员投票记录 |
| uncertainty | list | 不确定性（引擎承认不知道的地方） |
| evidence | dict | 证据链（不可篡改） |
| audit_log | list | 审查日志 |

## 审查深度

| 条件 | 深度 | 说明 |
|------|------|------|
| 只传 requirement + ai_output | quick | 快速审查，置信度有上限 |
| 传入 files 或 dependencies | standard | 标准审查 |
| 传入 project_path | deep | 深度审查，可读文件、查依赖 |

## 隔离级别

| 级别 | 条件 | 说明 |
|------|------|------|
| full | 不同 API 提供商 | 完全模型隔离，交叉审查效果最好 |
| partial | 同提供商不同模型 | 部分隔离 |
| simulated | 单 API 多角色 | 尽力隔离，效果打折扣 |

## 依赖

```
pip install audison
```

或从源码安装：

```
pip install -e .
```

## 环境变量

至少配置一个 API key：

```bash
OPENAI_API_KEY=sk-xxx          # OpenAI
ANTHROPIC_API_KEY=sk-ant-xxx   # Anthropic
DASHSCOPE_API_KEY=sk-xxx       # 通义千问
DEEPSEEK_API_KEY=sk-xxx        # DeepSeek
```

配置两个不同提供商的 key 可启用跨模型交叉审查（推荐）。

## MCP Integration

This skill is also available as an MCP server. Configure in your AI editor's `mcp.json`:

```json
{
  "mcpServers": {
    "audison": {
      "command": "uvx",
      "args": ["audison[mcp]", "audison-mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

Then use `audit_code` or `audit_file` tools in your AI assistant. The tools return a structured JSON verdict (PASS/REVIEW/REJECT) with numeric trust score and cryptographic evidence chain.

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `audit_code` | Audit inline AI-generated code for hallucinations |
| `audit_file` | Read a file from disk, then audit it |

Both tools accept `code`/`file_path`, `requirement` (required), and optional `brain1` model name.
