# 贡献指南

感谢你对 AI Flow Architect 项目的关注！我们欢迎所有形式的贡献。

## 如何贡献

### 报告问题

如果你发现了bug或有功能建议，请通过GitHub Issues提交：

1. 使用清晰的标题描述问题
2. 提供详细的复现步骤
3. 包含相关的错误信息或截图
4. 说明你的运行环境（Python版本、操作系统等）

### 提交代码

1. **Fork 本仓库**
   ```bash
   # 点击页面右上角的 Fork 按钮
   ```

2. **克隆你的 Fork**
   ```bash
   git clone https://github.com/wdnmd1265/ai-flow-architect.git
   cd ai-flow-architect
   ```

3. **创建特性分支**
   ```bash
   git checkout -b feature/你的特性名称
   ```

4. **安装开发依赖**
   ```bash
   pip install -e ".[dev]"
   ```

5. **进行修改**
   - 确保代码符合项目规范
   - 添加必要的测试
   - 更新相关文档

6. **运行测试**
   ```bash
   pytest tests/
   ```

7. **代码格式化**
   ```bash
   black src/ tests/
   isort src/ tests/
   ```

8. **提交更改**
   ```bash
   git add .
   git commit -m "feat: 添加你的特性描述"
   ```

9. **推送到你的 Fork**
   ```bash
   git push origin feature/你的特性名称
   ```

10. **创建 Pull Request**
    - 回到GitHub页面，点击 "New Pull Request"
    - 填写详细的描述说明你的修改
    - 等待代码审查

## 代码规范

### Python 代码风格

- 遵循 PEP 8 规范
- 使用 Black 进行代码格式化
- 使用 isort 进行导入排序
- 类型注解：尽可能添加类型提示
- 文档字符串：所有公共函数和类必须有文档字符串

### 提交信息规范

使用 Conventional Commits 规范：

```
<类型>[可选的作用域]: <描述>

[可选的正文]

[可选的脚注]
```

类型包括：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式调整（不影响逻辑）
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

示例：
```
feat(brain): 添加二号脑质量审核功能

- 实现蓝图与交付物的逐项比对
- 添加质量报告生成逻辑
- 支持退回修改机制

Closes #123
```

## 开发环境设置

### 依赖安装

```bash
# 安装（含开发依赖）
pip install -e ".[dev]"
```

### 开发工具

推荐使用以下工具：

- **编辑器**: VS Code + Python扩展
- **代码格式化**: Black + isort
- **类型检查**: mypy
- **测试**: pytest
- **文档**: Sphinx

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_brain_one.py

# 运行带覆盖率的测试
pytest --cov=src/ai_flow_architect tests/
```

## 项目结构说明

```
src/ai_flow_architect/
├── core/           # 核心引擎组件
├── brains/         # 双脑系统实现
├── experts/        # 专家角色定义
├── templates/      # 预置配置模板
├── utils/          # 工具函数
└── config/         # 配置文件
```

### 核心模块职责

- **core/architect.py**: 主框架类，协调整个工作流
- **core/scheduler.py**: 任务调度器，管理专家执行顺序
- **core/context.py**: 上下文管理，处理会话隔离
- **core/cache.py**: 缓存机制，实现Token节省
- **brains/brain_one.py**: 一号脑，负责需求分析和规划
- **brains/brain_two.py**: 二号脑，负责质量审核
- **experts/base.py**: 专家基类，定义通用接口

## 行为准则

### 我们的承诺

为了营造一个开放、友好的环境，我们承诺：

- 使用友好和包容的语言
- 尊重不同的观点和经验
- 优雅地接受建设性批评
- 关注对社区最有利的事情
- 对其他社区成员表示同理心

### 不当行为

不可接受的行为包括：

- 使用性暗示的语言或图像
- 恶意评论、人身攻击或政治攻击
- 公开或私下骚扰
- 未经明确许可发布他人的私人信息
- 其他不道德或不专业的行为

## 许可证

通过贡献代码，你同意你的贡献将在 [Apache License 2.0](LICENSE) 下许可。

## 联系方式

如有任何问题，请通过以下方式联系我们：

- GitHub Issues: [项目Issues页面]
- 邮箱: [项目维护者邮箱]

---

再次感谢你的贡献！🎉