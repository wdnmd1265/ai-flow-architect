# CLI 集成

通过 `ai-flow audit` 命令直接审查 AI 生成代码，零代码集成，适合本地开发、CI/CD 流水线和 pre-commit hook。

## 安装

```bash
pip install ai-flow-architect
```

## 使用方式

### 1. 单文件审查

最基本的用法——审查单个 Python 文件：

```bash
ai-flow audit auth.py -r "检查 SQL 注入、密码哈希和认证漏洞"
```

**输出示例**：

```
TrustReport ─────────────────────────────────────────────
  Verdict:  REJECT
  Score:    34/100
  Findings: 3

  [CRITICAL] SQL 注入风险：第 42 行 query = f"SELECT * FROM users WHERE email='{email}'"
             未使用参数化查询，攻击者可注入恶意 SQL。
  [HIGH]     弱密码哈希：第 18 行 hashlib.sha256(password.encode()).hexdigest()
             SHA-256 不适合密码存储，应使用 bcrypt 或 argon2。
  [MEDIUM]   缺少速率限制：登录接口未限制尝试次数，存在暴力破解风险。

  Recommendation: 代码存在严重安全问题，建议修复后重新审查。
─────────────────────────────────────────────────────────
```

### 2. 管道输入（stdin）

从其他命令管道传入代码内容：

```bash
cat auth.py | ai-flow audit - -r "检查安全漏洞" --json
```

管道模式下文件名用 `-` 占位。

### 3. 输出 Markdown 格式

生成可嵌入 PR 评论或文档的 Markdown 报告：

```bash
ai-flow audit auth.py -r "检查 SQL 注入和认证漏洞" --markdown
```

**输出示例**：

```markdown
## TrustReport — REJECT (34/100)

### 审查结果：不通过

| # | 严重程度 | 问题 | 位置 |
|---|----------|------|------|
| 1 | CRITICAL | SQL 注入风险 | auth.py:42 |
| 2 | HIGH | 弱密码哈希 (SHA-256) | auth.py:18 |
| 3 | MEDIUM | 缺少登录速率限制 | auth.py:35 |

> 代码存在严重安全问题，建议修复后重新审查。
```

### 4. 集成到 CI/CD

GitHub Actions 示例：

```yaml
- name: AI Code Audit
  run: |
    pip install ai-flow-architect
    ai-flow audit src/auth.py \
      -r "检查 SQL 注入、XSS、认证漏洞" \
      --markdown > audit-report.md
- name: Upload Audit Report
  uses: actions/upload-artifact@v4
  with:
    name: audit-report
    path: audit-report.md
```

pre-commit hook 示例（`.pre-commit-config.yaml`）：

```yaml
repos:
  - repo: local
    hooks:
      - id: ai-audit
        name: AI Code Audit
        entry: ai-flow audit
        language: system
        files: \.py$
        args: ["-r", "检查安全漏洞"]
```

## 命令参考

| 参数 | 说明 |
|------|------|
| `<file>` | 待审查文件路径，`-` 表示从 stdin 读取 |
| `-r, --requirement` | 审查需求描述 |
| `--json` | 输出 JSON 格式（默认文本格式） |
| `--markdown` | 输出 Markdown 格式 |
| `--model` | 指定 LLM 模型（默认 gpt-4o） |

## 典型工作流

1. AI 生成代码 → 保存为 `.py` 文件
2. 运行 `ai-flow audit <file> -r "<审查需求>"`
3. 根据 TrustReport 的 `verdict` 决定是否合入代码
4. 修复 `findings` 中的问题后重新审查