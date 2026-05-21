# TrustEngine 接口规范

版本：v1.0  
日期：2026-05-21  
状态：Stable

---

## 1. 概述

TrustEngine 是一个独立的 AI 产出审查模块。接收需求和 AI 产出，返回结构化的信任报告。

设计原则：
- 不生成任何内容，只审查
- 不与用户交互，无状态
- 可独立调用，也可被 FlowArchitect 内部调用

---

## 2. 核心接口

### 2.1 audit()

```python
async def audit(
    requirement: str,
    ai_output: str,
    context: Optional[AuditContext] = None,
) -> TrustReport
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| requirement | str | ✅ | 用户需求描述，1-10000 字符 |
| ai_output | str | ✅ | AI 生成的产出（代码、方案、文章等），1-100000 字符 |
| context | AuditContext | ❌ | 审查上下文，传入后审查深度自动升级 |

**返回：** TrustReport

**异常：**

| 异常 | 说明 |
|------|------|
| ValueError | requirement 或 ai_output 为空 |
| RuntimeError | 所有审查员均失败且无降级方案 |

---

## 3. 数据模型

### 3.1 TrustReport

| 字段 | 类型 | 说明 |
|------|------|------|
| version | str | 固定 "1.0" |
| timestamp | str | ISO 8601 时间戳 |
| verdict | str | 结论：`pass` / `review` / `reject` |
| confidence | float | 置信度，0.0-100.0 |
| findings | list[Finding] | 发现的问题 |
| risks | list[Risk] | 风险点 |
| arbiters | list[ArbiterVote] | 审查员投票记录 |
| uncertainty | list[Uncertainty] | 不确定性 |
| evidence | EvidenceChain | 证据链 |
| audit_log | list[str] | 审查日志 |

**计算属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| needs_review | bool | verdict != "pass" |
| high_uncertainty_count | int | severity 为 "high" 的不确定性数量 |

**方法：**

| 方法 | 返回 | 说明 |
|------|------|------|
| to_json() | str | JSON 序列化 |
| to_markdown() | str | Markdown 格式化 |
| summary() | str | 一行摘要 |

### 3.2 Finding

| 字段 | 类型 | 说明 |
|------|------|------|
| area | str | 问题所在区域 |
| severity | str | 严重程度：`low` / `medium` / `high` / `critical` |
| description | str | 问题描述 |
| source | str | 来源：`arbiter_0` / `arbiter_1` / `opponent` 等 |
| evidence | Optional[str] | 证据 |

### 3.3 Risk

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | 风险类型：`security` / `logic` / `performance` / `scalability` |
| level | str | 风险等级：`low` / `medium` / `high` / `critical` |
| description | str | 风险描述 |
| mitigation | Optional[str] | 缓解建议 |

### 3.4 ArbiterVote

| 字段 | 类型 | 说明 |
|------|------|------|
| model | str | 审查使用的模型 |
| role | str | 审查员角色 |
| passed | bool | 是否通过 |
| score | float | 质量分数 0-100 |
| issues | list | 发现的问题 |
| suggestions | list | 改进建议 |

### 3.5 Uncertainty

| 字段 | 类型 | 说明 |
|------|------|------|
| area | str | 不确定的区域 |
| reason | str | 不确定的原因 |
| severity | str | 严重程度：`low` / `medium` / `high` |
| suggestion | str | 建议（通常建议人工审查） |

### 3.6 EvidenceChain

| 字段 | 类型 | 说明 |
|------|------|------|
| hash | str | 证据链 SHA-256 哈希 |
| algorithm | str | 哈希算法，固定 "sha256" |
| timestamp | str | ISO 8601 时间戳 |
| isolation_level | str | 隔离级别：`full` / `partial` / `simulated` |
| data_summary | dict | 数据摘要（可选） |

### 3.7 AuditContext

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_path | Optional[str] | ❌ | 项目路径，传入后审查深度升级为 deep |
| files | Optional[dict] | ❌ | 文件内容 {路径: 内容}，传入后审查深度为 standard |
| dependencies | Optional[list] | ❌ | 依赖声明列表，传入后审查深度为 standard |
| language | Optional[str] | ❌ | 编程语言 |
| description | Optional[str] | ❌ | 项目描述 |

**计算属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| has_project_access | bool | 是否有项目访问权限 |
| audit_depth | str | 审查深度：`deep` / `standard` / `quick` |

---

## 4. verdict 判定规则

| 条件 | verdict |
|------|---------|
| 存在 severity=critical 的 finding | reject |
| confidence < 70 或 high findings >= 2 | review |
| confidence < 85 | review |
| confidence >= 85 且无 high/critical findings | pass |

---

## 5. 隔离级别

| 级别 | 条件 | 说明 |
|------|------|------|
| full | 两个审查模型来自不同 API 提供商 | 交叉审查效果最好 |
| partial | 同提供商不同模型 | 部分隔离 |
| simulated | 同一模型不同温度/角色 | 尽力隔离，效果打折扣 |

---

## 6. API 接口

### 6.1 POST /audit

**请求：**

```json
{
    "requirement": "用户登录系统",
    "ai_output": "def login(user, pwd): ...",
    "project_path": null,
    "files": null,
    "dependencies": null,
    "brain1": "gpt-4o",
    "brain2": null
}
```

**响应：**

```json
{
    "version": "1.0",
    "timestamp": "2026-05-21T18:00:00Z",
    "verdict": "review",
    "confidence": 65.0,
    "findings": [...],
    "risks": [...],
    "arbiters": [...],
    "uncertainty": [...],
    "evidence": {...},
    "audit_log": [...]
}
```

### 6.2 GET /health

```json
{"status": "ok"}
```

### 6.3 GET /models

返回支持的模型提供商列表。

---

## 7. 错误码

| HTTP 状态码 | 说明 |
|------------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 500 | 服务端错误（审查失败等） |
| 503 | 无可用 API key |
