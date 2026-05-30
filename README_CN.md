<p align="center">
  <img src="docs/img/logo.svg" alt="Audison" width="500" />
</p>

<p align="center">
  <strong>AI 的输出不可信。让我们审查它。</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9%2B-3776AB.svg" alt="Python 3.9+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-4CAF50.svg" alt="License"></a>
  <a href="https://github.com/wdnmd1265/audison/actions"><img src="https://img.shields.io/badge/tests-186%20passing-4CAF50.svg" alt="Tests"></a>
  <a href="https://wdnmd1265.github.io/audison/"><img src="https://img.shields.io/badge/demo-playground-58a6ff.svg" alt="Playground"></a>
</p>

<p align="center">
  <a href="#让你警觉的那一刻">为什么</a> &middot;
  <a href="#快速开始">快速开始</a> &middot;
  <a href="#html-报告">HTML 报告</a> &middot;
  <a href="#trustengine">TrustEngine</a> &middot;
  <a href="#工作原理">工作原理</a> &middot;
  <a href="README.md">English</a>
</p>

---

## 让你警觉的那一刻

你让 AI 写一个登录处理函数。它自信地返回了代码：

```
┌─────────────────────────────────────────────────────┐
│ AI 说："这是一个安全的登录实现。"                    │
│                                                     │
│   def login(username, password):                    │
│       query = "SELECT * FROM users "                │
│       query += "WHERE name='" + username + "'"      │
│       query += " AND password='" + hash(password)   │
│       return db.execute(query)                      │
│                                                     │
│ 看起来没问题，对吧？                                 │
└─────────────────────────────────────────────────────┘
```

**TrustEngine 不这么认为。** 两个 AI 模型交叉审查了这段代码。第三个扮演反对者。它们发现了这些问题：

```
┌──────────────────────────────────────────────────────────┐
│ TrustReport — REJECT（置信度 32/100）                    │
│                                                          │
│ > [CRITICAL] SQL 注入 — username 在第 3 行被直接拼接     │
│   进查询字符串                                           │
│   "攻击者输入 ' OR 1=1 --  即可绕过认证"                 │
│                                                          │
│ > [HIGH] 不安全的哈希 — hash() 不是密码学哈希函数。      │
│   请使用 bcrypt 或 argon2。                              │
│                                                          │
│ > [MEDIUM] 缺少频率限制 — 10 分钟内即可暴力破解。        │
│   添加指数退避机制。                                     │
│                                                          │
│ > [!] UNCERTAIN: 会话续期的竞态条件 —                    │
│   两个审查者意见不一致。建议人工复核。                   │
│                                                          │
│ 审查者：GPT-4o + Claude 3.5 Sonnet + Opponent            │
│ 证据链：a1b2c3...（SHA-256，可验证）                     │
│                                                          │
│ Powered by audison                             │
└──────────────────────────────────────────────────────────┘
```

**我们给 AI 配备了一个对手。** 两个大脑从不同角度审查同一份输出。当它们意见不一致时，不确定性会被写入报告——而不是被掩盖。你得到的是一份可验证、可分享的审计报告，而不是一个黑箱答案。

> **[体验交互式 Playground](https://wdnmd1265.github.io/audison/)** — 查看真实的 AI 输出审计。无需安装，无需 API Key。

---

## 快速开始

```bash
pip install audison[html]
```

设置一个 API Key——或两个以实现跨提供商交叉验证（推荐）：

```bash
export OPENAI_API_KEY="sk-..."        # 必需
export ANTHROPIC_API_KEY="sk-ant-..."  # 可选，用于更强的审计
```

一行命令审计任何内容：

```bash
# 审计一个文件，指定关注点
audison audit login.py -r "检查 SQL 注入、认证绕过和频率限制"

# 导出为可分享的 HTML 报告
audison audit login.py -r "安全审计" --html -o report.html

# 从其他工具管道输入
cat generated_code.py | audison audit -r "验证正确性"
```

```python
# 或使用 Python SDK——三行代码
from audison import TrustEngine

engine = TrustEngine()
report = engine.audit(
    requirement="带频率限制的安全用户认证",
    ai_output=ai_generated_code,
)
print(report.summary())  # "REJECT (32/100): 3 findings, 2 uncertain"
```

---

## HTML 报告

使用 `--html` 导出自包含的 HTML 报告。发送给你的团队，发布到 Issue 里。每一次分享都是一次 AI 没能逃过的审计。

```bash
audison audit contract.pdf -r "检查不公平条款" --html -o contract-audit.html
```

报告包含彩色编码的发现项、标注模型的审查者投票、可折叠的证据链，以及透明的成本明细。无需外部 CSS、无需 JavaScript 框架、无需服务器——一个文件，随处可用。

![TrustReport 示例](docs/og-image.png)

---

## TrustEngine

TrustEngine 是独立的审计层。零状态。零交互。纯粹验证。

```python
report.verdict        # "pass" | "review" | "reject"
report.confidence     # 0-100
report.findings       # 具体的发现项，含严重度和证据
report.uncertainty    # 引擎承认无法确认的内容
report.evidence_chain # SHA-256 哈希 + 时间戳，完全可验证
```

### 输出格式

| 格式 | 命令 | 使用场景 |
|--------|---------|----------|
| 终端 | `audison audit ...` | 交互式，彩色编码 |
| HTML | `audison audit ... --html -o report.html` | 分享给团队，发布到 Issue |
| JSON | `audison audit ... --json` | 管道传给其他工具，CI/CD |
| Markdown | `audison audit ... --markdown` | 嵌入文档、PR 评论 |

### 集成方式

| 集成 | 工作量 | 指南 |
|-------------|--------|-------|
| CLI | 1 行 | `audison audit ...` |
| Python SDK | 3 行 | `TrustEngine().audit(...)` |
| LangChain | 3 行 | `agent.run()` + `engine.audit()` |
| CrewAI | 4 行 | `crew.kickoff()` + `engine.audit()` |
| OpenAI SDK | 5 行 | `client.create()` + `engine.audit()` |
| GitHub Action | YAML | 复制 `.github/workflows/audit-pr.yml` |

### 对比

| 特性 | audison | Mira | 原始 LLM |
|---------|-------------------|------|---------|
| 开源 | ✅ | ❌ | — |
| 多模型交叉验证 | ✅ | ✅ | ❌ |
| 对抗性审查 | ✅ | ❌ | ❌ |
| 不确定性透明 | ✅ | ❌ | ❌ |
| 可验证证据链 | ✅ | ❌ | ❌ |
| 成本 | 免费软件；你只需支付自己的 API 费用 | $X/月订阅 | 免费（信任风险自负） |

---

## 工作原理

```
  你：「这个 AI 输出可信吗？」
         |
         v
+--------------------------+
| Brain #2（主审计）        |  跨模型审查。
| 模型：GPT-4o              |  多个审查者独立投票。
+-----------+--------------+
            |
            v
+--------------------------+
| Opponent Brain            |  5 种对抗性视角从各个角度
| "魔鬼代言人"              |  挑战输出。
+-----------+--------------+
            |
            v
+--------------------------+
| 不确定性计算               |  综合审查者分歧 +
|                           |  对抗性盲区，得出单一分数。
+-----------+--------------+
            |
            v
+--------------------------+
| 证据链                    |  所有发现项哈希 + 时间戳。
| SHA-256，可验证            |  证明发现了什么、何时发现。
+-----------+--------------+
            |
            v
    TrustReport — 不是猜测，是审计。
```

核心洞察：单个模型无法发现自己的盲区。两个在不同数据上训练的模型，加上一个主动尝试破坏输出的对抗性对手，可以捕捉到任何一个单独会遗漏的问题。

**一个 API Key 就够了。** 如果你只提供 `OPENAI_API_KEY`，引擎会自动降级使用 `gpt-4o-mini` 作为辅助审查者。跨提供商（OpenAI + Anthropic）能给出最强结果，因为两个模型的失败模式不同。

### 高级：FlowArchitect

TrustEngine 用于审计已有的 AI 输出。FlowArchitect 从一开始就在审计下构建输出。适用于"生成后再审查"还不够的场景——你需要对手在规划阶段就参与进来。

```python
from audison import FlowArchitect

async def main():
    architect = FlowArchitect(config={"brain1": "gpt-4o"})
    result = await architect.run("设计一个用户管理系统")
    # Brain #1 规划 → Opponent 挑战 → 你批准 → Experts 执行 → Brain #2 审计
```

→ [FlowArchitect 完整文档](docs/flow-architect.md)

---

## 项目结构

```
audison/
├── src/audison/
│   ├── engine/                  # TrustEngine — 独立审计层
│   │   ├── trust_engine.py      # 核心审计接口
│   │   ├── trust_report.py      # TrustReport 数据结构 + 序列化（JSON/MD/HTML）
│   │   └── audit_context.py     # 项目元数据的审计上下文
│   ├── brains/
│   │   ├── brain_one.py         # Brain #1：需求分析 + 蓝图生成
│   │   ├── brain_two.py         # Brain #2：质量仲裁（跨模型）
│   │   └── brain_opponent.py    # Opponent Brain：5 种对抗性审查风格
│   ├── core/
│   │   ├── architect.py         # 三阶段编排 + 用户批准循环
│   │   ├── scheduler.py         # 串行执行 + 4 种 token 节省机制
│   │   ├── context.py           # 会话 CRUD + 历史压缩
│   │   └── cache.py             # CRUD + TTL + 命中统计
│   ├── experts/                 # 专家团队：creative, evaluator, programmer, reviewer
│   ├── utils/
│   │   ├── llm_client.py        # 统一 LLM 客户端（8 个提供商）
│   │   ├── token_counter.py     # Token 计数 + 成本估算
│   │   ├── compressor.py        # 上下文压缩（4 种策略）
│   │   └── validator.py         # 输入验证
│   └── templates/
│       └── report.html          # --html 导出的 Jinja2 模板
├── tests/unit/                  # 186 个单元测试
├── docs/
│   ├── flow-architect.md
│   ├── getting_started.md
│   └── sample-report.html       # TrustReport 示例（浏览器打开查看）
├── .env.example
├── pyproject.toml
└── models.yaml                  # 提供商 + 模型配置
```

---

## 路线图

- [ ] **GitHub Action** — 自动 PR 审查评论，附带 --html 报告链接
- [ ] **PyPI 发布** — `pip install audison`
- [ ] **人格市场** — 社区贡献的对抗性审查风格（`/personas`）
- [ ] **社区擂台赛** — 「你能打败我们的 Opponent Brain 吗？」挑战
- [x] **HTML 报告导出** — 自包含、可分享的审计报告
- [x] **CLI 接口** — `audison audit` 支持 `--html`、`--json`、`--markdown`
- [x] **TrustEngine** — 多审查者 + 对抗性 + 证据链
- [x] **模型提供商** — OpenAI + Anthropic 已生产验证，另有 5 家通过兼容协议接入
- [ ] **并行执行** — 独立步骤并发运行
- [ ] **流式输出** — 实时专家输出流式传输

---

## 参与贡献

欢迎贡献。如果你用我们兼容列表之外的提供商测试过引擎，仅这一项就是有价值的 PR。

```bash
git clone https://github.com/wdnmd1265/audison.git
cd audison
pip install -e ".[html]"
pytest tests/unit/ -v    # 186 个测试
```

---

## 许可证

[Apache License 2.0](LICENSE) — 版权所有 2026 盛鑫

---

<p align="center">
  <em>AI 生成。AI 挑战。你来决定。这就是我们解决幻觉的方式。</em>
</p>