# 更新日志

本项目的所有重要更改都将记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 新增

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