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
    """纯静态 HTML 验证"""

    def test_no_script_tag(self):
        """模板不包含裸 <script> 标签（允许 jinja2 模板引用变量中含有 script 词但不属于标签）"""
        content = read_template()
        # 匹配真实的 <script> 标签（非变量名中的 script）
        script_tags = re.findall(r'<\s*script[\s>]', content, re.IGNORECASE)
        assert len(script_tags) == 0, "模板中包含 <script> 标签，应为纯静态 HTML"

    def test_no_onclick_handler(self):
        """模板不包含 onclick 等 JS 事件处理器"""
        content = read_template()
        js_handlers = re.findall(r'\bon\w+\s*=', content)
        assert len(js_handlers) == 0, f"模板中包含 JS 事件处理器: {js_handlers}"