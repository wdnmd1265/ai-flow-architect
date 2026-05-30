# 更新日志

本项目的所有重要更改都将记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

（暂无）

## [2.3.3] - 2026-05-30

### 新增

**社区基建**

- `CODE_OF_CONDUCT.md`：Contributor Covenant 2.1
- `SECURITY.md`：漏洞报告流程、支持版本、披露流程
- Issue 模板升级为 .yml 表单格式：Bug Report（下拉选择 OS、必填字段）+ Feature Request（复选框选择范围）
- `.github/ISSUE_TEMPLATE/config.yml`：禁用空白 Issue，引导到 Discussions

**GitHub Action — 发布到 Marketplace**

- `action.yml`：composite action，支持 9 个提供商 API Key 输入
- `scripts/action_entry.py`：Action 入口脚本，JSON 结构化输出
- 自动检测 PR 变更文件、支持 fail_on 配置（reject/review/never）、PR 评论 + Job Summary 双模式输出

## [2.3.2] - 2026-05-29

### 变更

**架构整理（Phase A-D）**

- APIPoolManager 成为 API Key 检测唯一来源：新增 `has_key_for_model()` + `get_required_env_var()`，cli.py 和 trust_engine.py 统一调用
- `model_resolver.py` 职责收窄：只保留 `resolve_brain2()` + `get_model_provider()`，Key 相关逻辑移至 APIPoolManager
- `_do_health()` 接真实数据：从 EvidenceDB 加载，3 条降级路径（DB 不存在/表为空/损坏）
- `__import__('time')` 替换为标准 `import time`（5 处）
- Tier 2 路由诚实标注：NOTE 说明未实现，实际路由层级 Tier 1→Tier 3→Tier 4

**CLI 拆包**

- `cli.py`（1492 行）拆为 `cli/` 子包（12 文件，最大 220 行）
- 统一命令分发：`_delegate()` 用 `inspect.signature` 自动判断函数签名
- 渲染常量提取至 `render.py`：`VERDICT_COLORS` / `VERDICT_LABELS` / `SEVERITY_COLORS` / `SEVERITY_LABELS`

**代码整洁**

- 清理 26 处未使用 import（涉及 18 个文件）
- `engine/__init__.py` 补充 deprecated 标注说明
- `templates/__init__.py` 补充注释
- `conscience.py` 清理过期 TODO

### 新增

**漏斗引导链路**

- `audison init` 重写为 3 步交互对话：Provider 菜单（4 选 1）→ API Key（Ollama 跳过）→ Custom 额外问 endpoint + 已有配置覆盖检测
- Playground Demo 新增 "Try with your own code →" 按钮，一键切到 Live 模式
- 文案风格统一：箭头 + 等宽命令，npx Demo → Playground Demo → Playground Live → pip install 引导链路打通

**测试**

- `tests/unit/test_mcp_server.py`：11 个 MCP Server 测试
- `src/audison/config/model_resolver.py`：模型解析器独立模块

### 修复

- `playground_server.py` 临时文件泄漏：`finally` 块检查 `tmp_path` 存在性后再删除
- `cross_family.py` / `brain_blind.py` 类型一致性：`brain_families` 从 tuple 统一为 List[str]

## [2.3.0] - 2026-05-29

### 新增

**MCP Server — 零配置接入 Cursor / Windsurf / Claude Desktop**

- `src/audison/mcp_server.py`：基于 `mcp` SDK，暴露 `audit_code` 和 `audit_file` 两个工具
- 三层 API Key 降级：.env 文件 → 系统环境变量 → 降级为 REVIEW(UNCERTAIN) + 引导提示
- 120 秒超时保护：`asyncio.wait_for` 防止 LLM 卡死
- 启动入口：`audison-mcp` 命令（`pyproject.toml` 注册）
- 配置示例：`mcp.json.example`（支持 uvx 启动，零安装）
- MCP 集成文档：`skills/trust-engine/SKILL.md` 新增 MCP Integration 章节

**npx 一键体验**

- `npx-demo/`：Node.js 包，`npx audison-demo` 即可运行
- 5 个内置演示用例：Stripe API 幻觉 / 密码哈希错误 / 干净工具函数 / Pandas 参数 / 上下文漂移
- JSON 结构化输出，可管道传递给 jq / 其他工具
- 已发布至 npm：`audison-demo`

**Playground 双模式**

- Demo 模式（默认）：5 个预生成案例，零 API Key，点击即看完整 TrustReport
- Live 模式：用户填入 API Key，调用真实 LLM 实时审查
- 本地服务器：`audison serve` 或 `python -m audison.playground_server`，浏览器自动打开
- GitHub Pages：`docs/playground.html`，静态托管，无需后端

### 变更

**版本号一致性**

- `trust_report.py` 的 `engine_version` 字段从硬编码 `"0.1.0"` 改为从 `__init__.__version__` 动态读取
- `pyproject.toml` 和 `__init__.py` 版本号同步至 `2.3.0`

**brain_families 类型**

- `TrustReport.brain_families` 从 `tuple` 改为 `List[str]`，解决 Pydantic v2 序列化/反序列化类型不一致

### 修复

**Google/Gemini 模型支持缺失**

- `trust_engine.py` `_check_api_key()` 补全 `gemini-` → `GOOGLE_API_KEY` 映射，Gemini 模型不再被跳过
- `trust_engine.py` `_determine_isolation_level()` 补全 `gemini-` → `google` provider 映射，隔离级别判断正确
- `mcp_server.py` `_check_api_keys()` 补全 `GOOGLE_API_KEY`，用户只配 Gemini Key 时 MCP Server 不再报 no_api_keys

**代码质量**

- `brains/brain_two.py`：3 处 `__import__('time')` / `__import__('datetime')` 内联导入改为顶部 import
- `mcp_server.py`：`audit_code` 和 `audit_file` 提取公共函数 `_run_audit()`，消除 80% 重复代码
- `npx-demo/package.json`：license 从 `MIT` 改为 `Apache-2.0`，仓库地址修正
- `README.md` + `npx-demo/bin/cli.js`：Playground URL 修正为 `wdnmd1265.github.io/audison/playground.html`

### 测试

- 总测试数：481（全量通过）
- 修复 3 个因类型/版本变更导致的测试断言

---

## [2.2.0] - 2026-05-28

### 新增

**External Trace — 推理链推断（V2.1 Phase 3）**

- `TraceEngine.trace_reasoning()` 方法：短语级拆分 → 推理链推断 → 诚实双重标注
- `split_phrases()` 短语级拆分：比句子更细粒度，按逗号/分号/连词拆分
- `ReasoningStep` 数据模型：每步标注 type（fact/inference/assumption/omission）+ evidence_type（strong_match/claimed/none）+ confidence（high/medium/low）
- `ReasoningChain` 数据模型：推理链统计（事实/推断/假设/遗漏计数 + 整体置信度）
- 诚实双重标注：每条推理路径标注“由 X 模型推断生成，非原始推理记录”
- 证据类型区分：强匹配 vs 模型声称 vs 无依据
- CLI `audison trace` 新增 `--trace-type external` 和 `--model-name` 参数
- HTML 报告升级：推理路径可折叠面板（`<details>` 零 JS 依赖），可靠性颜色条（绿/黄/红）
- JSON 输出新增 `reasoning_chain`、`honesty_label`、`inference_model` 字段
- 新增 16 个 External Trace 测试

### 修复

**打包配置（影响所有 pip install 用户）**

- `pyproject.toml` 的 `package-data` 仅声明 `templates/*.html`，V2.1 新增的 3 个 YAML 配置文件（`attack_strategies/core.yaml`、`attack_strategies/schema.yaml`、`conscience/test_bank.yaml`）未被打入 wheel 包。用户 pip install 后 attack 和 conscience 功能会找不到配置文件
- 补全 `package-data`：`config/*.yaml`、`config/attack_strategies/*.yaml`、`config/conscience/*.yaml`

### 变更

**项目清理**

- 删除 `setup.py`（与 pyproject.toml 重复，版本号卡在 0.1.0）
- 删除 `MANIFEST.in`（功能已由 pyproject.toml 的 package-data 覆盖）
- 删除 `requirements.txt`（依赖已在 pyproject.toml 声明）
- 删除 `test_mvp.py`（早期临时测试，已在 tests/ 目录覆盖）
- 删除 `GITHUB_SETUP_GUIDE.md`（一次性文档，已完成使命）
- 删除 `IMAGE_SPEC.md`（图片规格说明，图片已制作完成）
- 删除 `example_output.txt` / `example_requirement.txt`（`audison example` 生成文件，已加入 .gitignore）
- 更新 `CONTRIBUTING.md`：安装命令统一为 `pip install -e ".[dev]"`

### 测试

- 总测试数：465 → 481

**Phase 1：增长基础设施**
- README 重写：英文优先，标题 "Two AIs review. A third attacks. You get the truth."，Before/After 对比块、差异化说明、方法论融入正文
- Playground 上线：docs/playground.html，2 个预生成案例卡片（Express.js / React Form），点击跳转完整 TrustReport
- 示例报告：docs/sample-report.html，完整 REJECT 级 TrustReport 演示（4 Findings / 4 Risks / 3 Arbiters / 2 Uncertain）
- OG 图片：docs/og-image.png（1200x630），社交分享预览图
- 中文 README：README_CN.md 独立中文版，结构与英文版对齐
- GitHub Action 示例：.github/workflows/audit-pr.yml，PR 触发自动审查 + 评论摘要

**HTML 报告导出**
- `audison audit` 新增 `--html` 参数，生成自包含单文件 HTML 报告
- Jinja2 模板：src/audison/templates/report.html，与 Python 逻辑分离
- `[html]` 可选依赖组：pip install audison[html]
- `-o` / `--output` 参数：所有输出格式（JSON/HTML/Markdown）均支持写入文件
- setuptools package-data 配置：确保模板文件随包分发

### 修复

**CLI 可用性**
- `audison` 现支持 `init`（生成 .env 模板）、`models`（列出所有模型）、`audit`（审查文件）三个子命令
- API key 检查改为动态：根据 `--brain1` 指定的模型从 models.yaml 查询对应环境变量，不再硬编码 OPENAI_API_KEY
- `audit` 支持 `--brain1` 和 `--brain2` 参数，可指定审查模型

**API 服务**
- FastAPI 实例使用 `lifespan` 缓存 TrustEngine，同模型组合不再重复初始化

**依赖整理**
- `redis`、`diskcache` 移至 `[cache]` 可选依赖，不再强制安装
- `fastapi`、`uvicorn` 移至 `[api]` 可选依赖
- 安装核心包不再拉 redis/fastapi

**TrustEngine 模型兼容**
- `_check_api_key` 补全 glm-/moonshot- 前缀映射，智谱和月之暗面模型的 fallback 不再跳过

**TrustReport 接口统一**
- 删除冗余 `to_json()`，所有调用方迁移至 Pydantic v2 原生 `model_dump_json(indent=2)`
- `__init__.py` 补全 TrustEngine 及相关类型导出

### 新增

**工具系统（Tool System）**
- 新增 `tools/` 模块，支持文件系统交互
- Tool ABC + ToolResult 标准接口，支持 OpenAI/Anthropic Function Calling 格式
- 5个内置工具：read_file、write_file、search_files、list_files、get_file_info
- 结果截断：4000 字符上限，截断时明确告知 LLM
- 错误反馈：error_type + message + suggestion，引导 LLM 下一步
- 工具执行循环：BaseExpert.execute_with_tools()，最多 8 轮，防无限循环
- 权限控制：专家自声明 required_tools，调度器按需注入
- 路径安全：WriteFileTool 限制在 project_dir 内
- 工具系统接入主流程：FlowArchitect.__init__() 自动创建并注册工具
- 改动文件：`tools/__init__.py`, `tools/base.py`, `tools/file_tools.py`, `experts/base.py`, `experts/programmer.py`, `experts/reviewer.py`, `core/scheduler.py`, `core/architect.py`

### 已知局限

**Anthropic 多轮工具对话**
- 工具结果回传时使用 OpenAI 格式，Anthropic 原生 API 不识别
- 不影响 OpenAI 兼容 API（DashScope/DeepSeek/Zhipu/Moonshot）
- 计划后续版本补充 Anthropic 消息格式转换

**write_file 审批流程**
- 当前 write_file 工具会直接执行，无用户审批拦截
- 计划后续版本实现累积审批机制

**V2 架构 — 6大方案全部实现**

**方案1：人格注入**
- 默认场景：双脑架构真实陈述，自动注入，无需用户操作
- 极端场景：用户主动触发，5个方向可选（安全压力/竞争压力/成本压力/用户同理心/自定义）
- 预设方向直接执行，自定义方向需用户确认
- 输出标记：极端场景下的结果有红色标签 `【安全压力审查】`
- 改动文件：`brains/brain_one.py`, `core/architect.py`

**方案2：反对者脑**
- 独立第三脑，条件触发（简单任务自动跳过）
- 5种风格：数据派/极简派/未来派/用户派/成本派
- LLM 调用失败自动降级到默认质疑
- 改动文件：`brains/brain_opponent.py`, `core/architect.py`

**方案3：风险标注 + 替代支线**
- Blueprint 新增 `risks` 和 `alternatives` 字段
- 生成蓝图时自动标注风险和提供替代方案
- 默认看到一个方案，风险和替代支线可选展开
- 改动文件：`brains/brain_one.py`, `core/architect.py`

**方案4：深化提问**
- 一个问题一个审批，用户可随时跳过
- 最多3个问题，超出预设问题库后由 LLM 动态生成
- 改动文件：`brains/brain_one.py`, `core/architect.py`

**方案5：影子你（决策记录）**
- 结构化任务属性标签（domain/complexity/involves_db 等）
- 三态冷启动：0次提示"开始记录"、1-9次显示进度、≥10次激活精确匹配建议
- 精确匹配（domain+complexity 相同）+ 宽松匹配（domain 相同）两级策略
- 显式后悔标记：用户可按 [X] 标记上次决策为后悔
- 改动文件：`utils/decision_recorder.py`, `core/architect.py`

**方案6：需求裸奔**
- 放在深化提问之前（第一步）
- 剥离技术假设，回到需求本质
- 纸笔方案 → 技术概念翻译
- 改动文件：`brains/brain_one.py`, `core/architect.py`

**专家执行层真实化**
- 四个专家（评估师、程序员、审核员、创意师）从硬编码 mock 数据升级为真实 LLM 调用
- LLM 调用失败自动回退 mock 数据，不影响流程连续性
- 改动文件：`experts/base.py`, `experts/evaluator.py`, `experts/programmer.py`, `experts/reviewer.py`, `experts/creative.py`, `core/scheduler.py`

**反例攻防机制**
- 反对者脑新增 `generate_adversarial_examples()` — 生成对抗输入、异常流程、边缘条件三类反例
- 一号脑新增 `simulate_defense()` — 针对每个反例即时模拟推演并输出防御方案
- 攻防记录在审批时展示（✅已防御 / ⚠️部分防御 / ❌未防御）
- 最多 3 轮攻防，结果作为附件提交仲裁层
- 改动文件：`brains/brain_opponent.py`, `brains/brain_one.py`, `core/architect.py`

**多元仲裁委员会**
- 二号脑新增 `multi_audit()` — 3 个仲裁者并行独立审计
- 自动高亮所有仲裁者一致指出的缺陷（consensus_issues）
- 多 API 时使用不同模型；单 API 时降级为同模型不同 temperature + 角色
- 复杂任务（≥4 步）自动启用多元仲裁，简单任务保持单裁判
- 改动文件：`brains/brain_two.py`, `core/architect.py`

**证据链（轻量版）**
- 最终交付时打包完整流程数据，生成 SHA-256 哈希 + UTC 时间戳
- 最终交付物 = 代码 + 完整体检报告 + 证据链
- 标注隔离级别（full / degraded）
- 改动文件：`core/architect.py`

**质量信用点**
- 任务执行前预估 API 调用次数和深度（浅层/中层/深层）
- 生成质量预算摘要告知用户
- 支持设置总信用上限，超限自动中断
- 改动文件：`core/architect.py`

**场景感知缓存指纹**
- 缓存键生成前自动提取 prompt 中的核心领域实体词
- 中文复合词规则 + 英文术语模式
- 杜绝"电商用户模块"和"社交用户模块"的语义相似误匹配
- 零 LLM 调用成本，纯规则提取
- 改动文件：`core/cache.py`

**README 定位声明**
- 顶部重写定位："Every framework helps you run more AI. This one helps you trust it less."
- 第一印象直接打破"又一个 Agent 框架"的刻板印象
- 改动文件：`README.md`

### 变更

**自适应质量等级**
- 启动时自动扫描可用 API 提供商数量
- 单 Key 时打印清晰的降级警告（含缺少哪个提供商、环境变量设置方法）
- 改动文件：`core/architect.py`

**上下文压缩透明标记**
- 历史被有损压缩后自动追加系统标记，告知压缩前后 token 数和"精确细节可能遗失"
- 确保仲裁者和用户知晓信息完整性状态
- 改动文件：`utils/compressor.py`

### 修复

**Blueprint 字段名**
- `persona_scenario` → `scenario_label`，语义更准确
- 改动文件：`core/architect.py`, `brains/brain_one.py`

**人格注入确认流程**
- 预设方向直接执行（省一步），自定义方向需要用户确认
- 改动文件：`core/architect.py`

**反对者脑 LLM 降级**
- `critique()` 方法添加 try/catch，LLM 失败时降级到默认质疑
- 改动文件：`brains/brain_opponent.py`

**缩进错误**
- 修复 `_extreme_scenario_review` 方法的缩进错误
- 改动文件：`core/architect.py`

### 测试

**新增 19 个高风险路径测试**
- 场景感知缓存：`_extract_domain_entities` 6个测试
- 影子冷启动：空数据库/积累中/已激活 3个测试
- 影子匹配：精确匹配/宽松匹配/无匹配/后悔追踪 4个测试
- 多元仲裁降级：单API降级/多API全模式 3个测试
- 反例攻防降级：LLM失败路径 3个测试
- 全部 133 个单元测试通过（零回归）
- 改动文件：`tests/unit/test_cache_domain_entities.py`, `tests/unit/test_shadow_cold_start.py`, `tests/unit/test_shadow_matching.py`, `tests/unit/test_multi_arbitration.py`, `tests/unit/test_adversarial_fallback.py`

## [0.1.2] - 2026-05-25

### 新增

**Phase 2 生产化**
- 超时配置：`utils/llm_client.py` 超时从 30s 延长至 120s
- JSON 异常降级处理：`brains/brain_two.py` 中 `_audit_with_llm`、`_single_arbiter_audit`、`_single_arbiter_audit_raw` 三处新增 `except json.JSONDecodeError` 降级路径
- trace_id 注入：新建 `engine/logging_config.py`，`engine/trust_engine.py` 的 `audit()` 方法调用 `set_trace_id()` 实现请求链路追踪
- 新增依赖：`shortuuid`（`pyproject.toml`）

**测试**
- 新增 35 个测试用例：`test_trust_report_serialization.py`（10 个）、`test_cli_e2e.py`（14 个）、`test_trust_engine_degradation.py`（11 个）
- 总测试数：186 → 221

## [0.1.0] - 2026-05-18

### 新增
- 项目创建
- Apache 2.0 许可证
- 基础项目结构
- README文档
- 贡献指南
- 更新日志

---

## 版本说明

### 版本号规则

我们使用语义化版本号：`主版本号.次版本号.修订号`

- **主版本号**：不兼容的API修改
- **次版本号**：向下兼容的功能性新增
- **修订号**：向下兼容的问题修正

### 更改类型

- **新增** - 新功能
- **变更** - 对现有功能的变更
- **弃用** - 即将移除的功能
- **移除** - 已移除的功能
- **修复** - 问题修复
- **安全** - 安全相关的更改

---

## 如何更新此文件

当进行重要更改时，请按以下格式添加条目：

```markdown
## [版本号] - YYYY-MM-DD

### 新增
- 新功能描述

### 变更
- 变更描述

### 修复
- 修复描述
```

### 示例

```markdown
## [1.2.0] - 2026-06-01

### 新增
- 添加数据可视化专家角色
- 支持自定义模型配置
- 新增Web界面

### 变更
- 优化缓存策略，提升30%性能
- 改进错误提示信息

### 修复
- 修复并发执行时的竞态条件
- 解决Token计数不准确的问题
```