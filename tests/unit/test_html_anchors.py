"""
测试：HTML 报告锚点导航

覆盖场景：
- 模板中存在 <nav> 目录
- 各 section 有 id 锚点
- <a href="#..."> 链接正确指向 section
- 纯静态 HTML（零 JS）
"""

import re
from pathlib import Path


def get_report_template_path():
    """获取 report.html 模板路径"""
    return Path(__file__).parent.parent.parent / "src" / "ai_flow_architect" / "templates" / "report.html"


def read_template():
    """读取 report.html 模板内容"""
    path = get_report_template_path()
    assert path.exists(), f"模板文件不存在: {path}"
    return path.read_text(encoding="utf-8")


class TestHTMLNavExists:
    """HTML 导航目录存在性测试"""

    def test_nav_element_exists(self):
        """模板包含 <nav> 目录元素"""
        content = read_template()
        assert "<nav" in content, "模板缺少 <nav> 导航目录"

    def test_nav_contains_toc_heading(self):
        """导航包含目录标题"""
        content = read_template()
        assert "Table of Contents" in content, "导航缺少 Table of Contents 标题"

    def test_nav_links_use_anchor_syntax(self):
        """导航链接使用 <a href='#...'> 锚点语法"""
        content = read_template()
        # 提取所有链接
        links = re.findall(r'<a\s+href="(#\w[\w-]*)"', content)
        assert len(links) > 0, "导航中缺少锚点链接"
        for link in links:
            assert link.startswith("#"), f"锚点格式错误: {link}"


class TestHTMLAnchorIDs:
    """HTML section 锚点 ID 测试"""

    # 期望的锚点列表
    EXPECTED_ANCHORS = [
        "summary",
        "findings",
        "risks",
        "arbiter-votes",
        "uncertainty",
        "blind-review",
        "cross-family",
        "model-performance",
        "evidence",
        "cross-examine",
        "attack-results",
        "audit-log",
    ]

    def test_section_anchor_ids_exist(self):
        """各 section 均有正确的 id 锚点"""
        content = read_template()
        # 提取所有 id 属性值
        all_ids = set(re.findall(r'\bid="([^"]+)"', content))

        for anchor in self.EXPECTED_ANCHORS:
            assert anchor in all_ids, f"缺少锚点 id='{anchor}'"


class TestHTMLAnchorMatching:
    """导航链接与锚点匹配测试"""

    def test_nav_links_match_section_ids(self):
        """导航 href 与对应元素 id 一一匹配"""
        content = read_template()

        # 提取导航中所有 href
        nav_match = re.search(r'<nav[^>]*>.*?</nav>', content, re.DOTALL)
        assert nav_match, "未找到 <nav> 标签"
        nav_content = nav_match.group(0)
        nav_hrefs = set(re.findall(r'href="(#\w[\w-]*)"', nav_content))

        # 提取所有元素 id（section + div 等，因为 summary 在 div 中）
        all_ids = set(re.findall(r'\bid="([^"]+)"', content))

        for href in nav_hrefs:
            anchor_name = href.lstrip("#")
            assert anchor_name in all_ids, f"导航链接 #{anchor_name} 无对应元素"


class TestHTMLNoJavaScript:
    """HTML 脚本策略验证：仅允许内联分享脚本，禁止外部引用和无关事件处理器。"""

    def test_no_external_script_deps(self):
        """模板不包含外部脚本引用（<script src=），但允许内联 <script> 块"""
        content = read_template()
        # 检测外部引用
        external = re.findall(r'<\s*script[^>]*\bsrc\s*=', content, re.IGNORECASE)
        assert len(external) == 0, f"模板中包含外部脚本引用: {external}"

        # 检测内联 <script> 块数量（至少应有 1 个分享功能脚本）
        inline_scripts = re.findall(r'<\s*script[\s>]', content, re.IGNORECASE)
        assert len(inline_scripts) == 1, (
            f"模板应有且仅有 1 个内联 <script> 块，实际: {len(inline_scripts)}"
        )

        # 验证内联脚本内容仅包含分享相关函数
        script_match = re.search(r'<script>(.*?)</script>', content, re.DOTALL)
        assert script_match is not None, "未找到内联 <script> 内容"
        script_body = script_match.group(1)
        assert "copyShareText" in script_body, "内联脚本应包含 copyShareText 函数"
        assert "navigator.clipboard" in script_body, "内联脚本应使用 navigator.clipboard"

    def test_onclick_only_on_share_button(self):
        """onclick 处理器仅存在于分享按钮上下文中"""
        content = read_template()
        # 提取所有 onclick= 出现的行
        onclick_lines = []
        for i, line in enumerate(content.split("\n"), 1):
            if re.search(r'\bonclick\s*=', line):
                onclick_lines.append((i, line.strip()))

        assert len(onclick_lines) > 0, "模板中应至少有一个 onclick 处理器（分享按钮）"

        for line_no, line in onclick_lines:
            assert (
                "copyShareText" in line or "share" in line.lower()
            ), (
                f"第 {line_no} 行的 onclick 不在分享按钮上下文中: {line}"
            )