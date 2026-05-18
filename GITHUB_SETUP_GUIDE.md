# GitHub 仓库创建指南

## 前置准备

### 1. 安装 Git

如果还没有安装 Git，请先安装：

**Windows:**
```bash
# 下载安装包
# https://git-scm.com/download/win
```

**macOS:**
```bash
# 使用 Homebrew
brew install git
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install git
```

### 2. 配置 Git

```bash
# 设置用户名和邮箱
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"

# 验证配置
git config --list
```

### 3. 注册 GitHub 账号

如果还没有 GitHub 账号，请访问 https://github.com 注册。

## 创建仓库

### 步骤 1: 在 GitHub 上创建新仓库

1. 登录 GitHub
2. 点击右上角的 "+" 按钮，选择 "New repository"
3. 填写仓库信息：
   - **Repository name**: `ai-flow-architect`
   - **Description**: `一个开源、API中立、极致省Token的多模型协作工作流引擎`
   - **Visibility**: 选择 Public（开源）
   - **Initialize this repository with**: 不要勾选任何选项（我们已经有了本地文件）
4. 点击 "Create repository" 按钮

### 步骤 2: 初始化本地仓库

打开终端，进入项目目录：

```bash
# 进入项目目录
cd D:/HANAKO/ai-flow-architect

# 初始化 Git 仓库
git init

# 添加所有文件到暂存区
git add .

# 查看状态
git status
```

### 步骤 3: 首次提交

```bash
# 提交所有文件
git commit -m "feat: 初始化项目结构

- 添加 Apache 2.0 许可证
- 创建项目基础架构
- 实现双脑系统框架
- 添加专家角色定义
- 配置文件和依赖管理
- 单元测试和示例代码"

# 查看提交历史
git log
```

### 步骤 4: 连接远程仓库

```bash
# 添加远程仓库（替换 YOUR_USERNAME 为你的 GitHub 用户名）
git remote add origin https://github.com/YOUR_USERNAME/ai-flow-architect.git

# 验证远程仓库
git remote -v
```

### 步骤 5: 推送到 GitHub

```bash
# 推送到远程仓库
git push -u origin main

# 如果遇到问题，可能需要先拉取（新仓库通常不需要）
# git pull origin main --allow-unrelated-histories
```

## 仓库设置

### 1. 设置仓库描述和主题

在 GitHub 仓库页面：

1. 点击右侧的 "About" 部分
2. 点击齿轮图标编辑
3. 添加：
   - **Description**: `一个开源、API中立、极致省Token的多模型协作工作流引擎`
   - **Website**: （可选）项目主页
   - **Topics**: `ai`, `workflow`, `multi-model`, `python`, `open-source`

### 2. 启用 GitHub Pages（可选）

如果需要项目主页：

1. 进入仓库 Settings
2. 找到 Pages 部分
3. 选择 Source 分支（通常是 main）
4. 选择目录（通常是 /docs）
5. 保存

### 3. 设置分支保护（推荐）

1. 进入仓库 Settings
2. 找到 Branches 部分
3. 点击 "Add rule"
4. 设置规则：
   - Branch name pattern: `main`
   - 勾选 "Require pull request reviews before merging"
   - 勾选 "Require status checks to pass before merging"

## 后续维护

### 日常开发流程

```bash
# 1. 创建新分支
git checkout -b feature/新功能名称

# 2. 进行开发...

# 3. 提交更改
git add .
git commit -m "feat: 添加新功能描述"

# 4. 推送分支
git push origin feature/新功能名称

# 5. 在 GitHub 创建 Pull Request

# 6. 代码审查后合并到 main 分支
```

### 发布版本

```bash
# 1. 更新版本号（在 setup.py 和 pyproject.toml 中）
# 2. 更新 CHANGELOG.md
# 3. 提交更改
git add .
git commit -m "chore: 发布 v0.1.0 版本"

# 4. 创建标签
git tag -a v0.1.0 -m "版本 0.1.0"

# 5. 推送标签
git push origin v0.1.0

# 6. 在 GitHub 创建 Release
```

## 常见问题

### Q: 推送时提示权限错误
A: 检查是否正确配置了 GitHub 账号，可能需要使用 Personal Access Token。

### Q: 如何撤销最近的提交？
A: 
```bash
# 撤销最后一次提交（保留更改）
git reset --soft HEAD~1

# 撤销最后一次提交（丢弃更改）
git reset --hard HEAD~1
```

### Q: 如何解决合并冲突？
A: 
```bash
# 拉取最新代码
git pull origin main

# 手动解决冲突文件中的冲突标记

# 添加解决后的文件
git add .

# 提交合并
git commit -m "merge: 解决合并冲突"
```

## 下一步

仓库创建完成后，你可以：

1. 邀请协作者
2. 设置 CI/CD（GitHub Actions）
3. 创建 Issue 模板
4. 添加 Pull Request 模板
5. 设置代码覆盖率徽章

---

祝你的开源项目顺利！🎉