"""
Tier 1 本地初筛引擎（Local Checker）。

纯规则/正则检查，不调用任何 LLM。
检测明显问题：硬编码密码、SQL 注入模式、空字段、格式一致性。
"""

import re
import json
from typing import List, Optional
from dataclasses import field
from pydantic import BaseModel, Field


class LocalFinding(BaseModel):
    """本地检查发现"""

    category: str = Field(..., description="问题类别：hardcoded_secret / sql_injection / empty_field / format_error / length_anomaly")
    severity: str = Field(..., description="严重程度：low / medium / high / critical")
    description: str = Field(..., description="问题描述")
    location: Optional[str] = Field(None, description="位置（如行号/片段）")
    evidence: Optional[str] = Field(None, description="具体匹配内容（脱敏后）")


class LocalCheckResult(BaseModel):
    """Tier 1 检查结果"""

    passed: bool = Field(..., description="是否通过所有本地检查")
    findings: List[LocalFinding] = Field(default_factory=list, description="所有发现的问题")
    score: float = Field(0.0, description="质量分数 (0-100)")


# ── 预编译正则模式 ──

# 硬编码密钥/密码模式
_SECRET_PATTERNS: List[tuple] = [
    # (pattern, name, severity)
    (re.compile(r'(?:api[_-]?key|apikey|api_secret|secret[_-]?key)\s*[:=]\s*["\'][a-zA-Z0-9_\-]{20,}["\']', re.IGNORECASE),
     "硬编码 API Key", "critical"),
    (re.compile(r'(?:password|passwd|pwd)\s*[:=]\s*["\'][^"\']{4,}["\']', re.IGNORECASE),
     "硬编码密码", "critical"),
    (re.compile(r'(?:token|access_token|auth_token|jwt)\s*[:=]\s*["\'][a-zA-Z0-9_\-\.]{20,}["\']', re.IGNORECASE),
     "硬编码 Token", "critical"),
    (re.compile(r'(?:private[_-]?key|ssh[_-]?key)\s*[:=]\s*["\']-----BEGIN', re.IGNORECASE),
     "硬编码私钥", "critical"),
    (re.compile(r'(?:connection[_-]?string|conn[_-]?str|database[_-]?url)\s*[:=]\s*["\'][a-zA-Z]+://[^"\']+["\']', re.IGNORECASE),
     "硬编码数据库连接串", "high"),
]

# SQL 注入风险模式
_SQL_INJECTION_PATTERNS: List[tuple] = [
    (re.compile(r'DROP\s+TABLE\s+\w+', re.IGNORECASE), "DROP TABLE 语句", "critical"),
    (re.compile(r'DELETE\s+FROM\s+\w+\s*(?:WHERE\s+1\s*=\s*1)?', re.IGNORECASE), "无条件 DELETE 语句", "high"),
    (re.compile(r"'\s*OR\s+['\"]?\s*1\s*=\s*1\s*['\"]?", re.IGNORECASE), "SQL 注入模式 ' OR 1=1", "critical"),
    (re.compile(r'\bWHERE\s+1\s*=\s*1\b', re.IGNORECASE), "SQL 注入模式 WHERE 1=1", "high"),
    (re.compile(r'\bUNION\s+(?:ALL\s+)?SELECT\b', re.IGNORECASE), "UNION SELECT 注入模式", "high"),
    (re.compile(r'f["\'].*\b(?:SELECT|INSERT|UPDATE|DELETE|DROP)\b', re.IGNORECASE), "Python f-string SQL 拼接（高风险）", "high"),
    (re.compile(r'\+\s*["\']\s*(?:SELECT|INSERT|UPDATE|DELETE)\b', re.IGNORECASE), "字符串拼接 SQL", "high"),
    (re.compile(r'(?:execute|exec|query)\s*\(\s*["\'].*?\b(?:SELECT|INSERT|UPDATE|DELETE)\b', re.IGNORECASE),
     "裸 SQL 执行（潜在注入）", "medium"),
]

# HTML 标签闭合检查
_HTML_TAG_PATTERN = re.compile(r'<(/?)(\w+)[^>]*>')

# JSON 语法检查（简单 pre-check，不替代完整 JSON parser）
_JSON_LINE_PATTERN = re.compile(r'^\s*["\{}\[\]]')


class LocalChecker:
    """
    本地规则检查器（Tier 1）。

    纯规则引擎，零 LLM 调用，零外部依赖。
    用于快速初筛明显问题，避免对简单问题浪费 API 调用。
    """

    def __init__(self):
        pass

    def check(self, requirement: str, ai_output: str) -> LocalCheckResult:
        """
        执行所有本地检查。

        Args:
            requirement: 用户需求描述
            ai_output: AI 生成的产出

        Returns:
            LocalCheckResult 包含所有发现和总分
        """
        findings: List[LocalFinding] = []

        # 1. 硬编码密钥检测
        findings.extend(self._check_hardcoded_secrets(ai_output))

        # 2. SQL 注入风险检测
        findings.extend(self._check_sql_injection(ai_output))

        # 3. 空值/缺失字段检查
        findings.extend(self._check_empty_fields(ai_output))

        # 4. 格式一致性检查
        findings.extend(self._check_format_consistency(ai_output))

        # 5. 长度异常检查
        findings.extend(self._check_length_anomaly(requirement, ai_output))

        # 计算分数
        score = self._calculate_score(findings)
        passed = all(
            f.severity not in ("critical", "high") for f in findings
        ) and score >= 70.0

        return LocalCheckResult(
            passed=passed,
            findings=findings,
            score=score,
        )

    def _check_hardcoded_secrets(self, text: str) -> List[LocalFinding]:
        """检测硬编码密钥/密码。"""
        findings = []
        for pattern, name, severity in _SECRET_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                # 脱敏：截断长密钥
                evidence = match if isinstance(match, str) else str(match)
                if len(evidence) > 60:
                    evidence = evidence[:57] + "..."
                findings.append(LocalFinding(
                    category="hardcoded_secret",
                    severity=severity,
                    description=f"{name}: 代码中包含明文敏感信息",
                    evidence=evidence,
                ))
                if len(findings) >= 20:
                    return findings
        return findings

    def _check_sql_injection(self, text: str) -> List[LocalFinding]:
        """检测 SQL 注入风险模式。"""
        findings = []
        for pattern, name, severity in _SQL_INJECTION_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                findings.append(LocalFinding(
                    category="sql_injection",
                    severity=severity,
                    description=f"SQL 注入风险: {name}",
                    evidence=str(matches[0])[:80] if matches else None,
                ))
        return findings

    def _check_empty_fields(self, text: str) -> List[LocalFinding]:
        """检测空值/缺失字段。"""
        findings = []

        # 常见占位符模式
        placeholder_patterns = [
            (r'(?:TODO|FIXME|XXX|HACK)\s*:\s*$', "代码中遗留 TODO/FIXME 标记"),
            (r'pass\s*#.*(?:TODO|implement|待实现)', "pass 占位未实现"),
            (r'raise\s+NotImplementedError', "NotImplementedError 未实现"),
            (r'return\s+None\s*#\s*(?:TODO|placeholder)', "返回 None 占位"),
            (r'""\s*#\s*(?:placeholder|占位)', "空字符串占位"),
        ]

        for pattern_str, desc in placeholder_patterns:
            pat = re.compile(pattern_str, re.IGNORECASE)
            matches = pat.findall(text)
            if matches:
                findings.append(LocalFinding(
                    category="empty_field",
                    severity="medium",
                    description=desc,
                    evidence=str(matches[0])[:60] if matches else None,
                ))

        # 检查输出是否几乎为空
        stripped = text.strip()
        if len(stripped) < 10:
            findings.append(LocalFinding(
                category="empty_field",
                severity="high",
                description="AI 输出几乎为空（< 10 字符）",
                evidence=stripped[:50],
            ))

        return findings

    def _check_format_consistency(self, text: str) -> List[LocalFinding]:
        """检查格式一致性（HTML 标签闭合、JSON 语法）。"""
        findings = []

        # HTML 标签闭合检查
        html_findings = self._check_html_tags(text)
        findings.extend(html_findings)

        # JSON 语法简单检查
        json_findings = self._check_json_syntax(text)
        findings.extend(json_findings)

        return findings

    def _check_html_tags(self, text: str) -> List[LocalFinding]:
        """检查 HTML 标签是否闭合。"""
        findings = []
        tags = _HTML_TAG_PATTERN.findall(text)

        if not tags:
            return findings

        stack = []
        for is_closing, tag_name in tags:
            tag_lower = tag_name.lower()
            # 自闭合标签
            if tag_lower in ("br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"):
                continue

            if is_closing:
                # 闭合标签
                if stack and stack[-1] == tag_lower:
                    stack.pop()
                elif stack:
                    findings.append(LocalFinding(
                        category="format_error",
                        severity="medium",
                        description=f"HTML 标签闭合错误: <{tag_name}> 与期望的 </{stack[-1]}> 不匹配",
                    ))
                    stack = []  # 重置避免级联报错
                else:
                    findings.append(LocalFinding(
                        category="format_error",
                        severity="low",
                        description=f"HTML 多余闭合标签: </{tag_name}> 无对应开标签",
                    ))
            else:
                stack.append(tag_lower)

        if stack:
            findings.append(LocalFinding(
                category="format_error",
                severity="medium",
                description=f"HTML 未闭合标签: {', '.join(f'<{t}>' for t in stack[:5])}",
            ))

        return findings

    def _check_json_syntax(self, text: str) -> List[LocalFinding]:
        """简单 JSON 语法检查。"""
        findings = []

        # 仅当文本看起来像 JSON 时才检查
        stripped = text.strip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            return findings

        # 大括号/方括号配对
        braces = 0
        brackets = 0
        in_string = False
        escape = False

        for i, ch in enumerate(stripped):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                braces += 1
            elif ch == '}':
                braces -= 1
            elif ch == '[':
                brackets += 1
            elif ch == ']':
                brackets -= 1

        if braces != 0:
            direction = "多出" if braces > 0 else "缺少"
            findings.append(LocalFinding(
                category="format_error",
                severity="medium",
                description=f"JSON 大括号不匹配: {direction} {abs(braces)} 个 {'{' if braces > 0 else '}'}",
            ))

        if brackets != 0:
            direction = "多出" if brackets > 0 else "缺少"
            findings.append(LocalFinding(
                category="format_error",
                severity="medium",
                description=f"JSON 方括号不匹配: {direction} {abs(brackets)} 个 {'[' if brackets > 0 else ']'}",
            ))

        # 尾随逗号
        if re.search(r',\s*[}\]]', stripped):
            findings.append(LocalFinding(
                category="format_error",
                severity="low",
                description="JSON 尾随逗号（trailing comma）",
            ))

        return findings

    def _check_length_anomaly(self, requirement: str, ai_output: str) -> List[LocalFinding]:
        """检查输出长度异常（明显短于需求）。"""
        findings = []

        req_len = len(requirement.strip())
        out_len = len(ai_output.strip())

        # 输出明显短于需求（需求 > 200 字符时，输出不足需求的 20%）
        if req_len > 200 and out_len < req_len * 0.2:
            findings.append(LocalFinding(
                category="length_anomaly",
                severity="high",
                description=f"AI 输出异常短: 需求 {req_len} 字符，输出仅 {out_len} 字符 ({out_len / max(req_len, 1) * 100:.1f}%)",
            ))

        # 输出完全为空
        if out_len == 0:
            findings.append(LocalFinding(
                category="length_anomaly",
                severity="critical",
                description="AI 输出完全为空",
            ))

        return findings

    def _calculate_score(self, findings: List[LocalFinding]) -> float:
        """基于发现计算质量分数。"""
        if not findings:
            return 100.0

        severity_penalties = {
            "critical": 30,
            "high": 15,
            "medium": 5,
            "low": 2,
        }

        total_penalty = sum(
            severity_penalties.get(f.severity, 0) for f in findings
        )

        return max(0.0, 100.0 - total_penalty)