"""
工具系统测试
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from audison.tools.base import Tool, ToolResult
from audison.tools.file_tools import (
    ReadFileTool,
    WriteFileTool,
    SearchFilesTool,
    ListFilesTool,
    GetFileInfoTool,
)


class TestToolResult:
    """测试 ToolResult"""

    def test_success_result(self):
        """成功结果"""
        result = ToolResult(
            status="success",
            tool="test_tool",
            output="test output",
        )
        assert result.status == "success"
        assert result.to_llm_message() == "test output"

    def test_error_result(self):
        """错误结果"""
        result = ToolResult(
            status="error",
            tool="test_tool",
            error_type="file_not_found",
            message="文件不存在",
            suggestion="检查路径",
        )
        assert result.status == "error"
        msg = result.to_llm_message()
        assert "file_not_found" in msg
        assert "文件不存在" in msg
        assert "检查路径" in msg

    def test_to_schema(self):
        """schema 导出"""

        class TestTool(Tool):
            @property
            def name(self):
                return "test"

            @property
            def description(self):
                return "test tool"

            @property
            def parameters(self):
                return {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                }

            async def execute(self, **kwargs):
                return self._success("ok")

        tool = TestTool()
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test"
        assert "path" in schema["function"]["parameters"]["properties"]


class TestReadFileTool:
    """测试 ReadFileTool"""

    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_read_existing_file(self, temp_dir):
        """读取存在的文件"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        tool = ReadFileTool()
        result = await tool.execute(path=str(test_file))

        assert result.status == "success"
        assert "hello world" in result.output

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, temp_dir):
        """读取不存在的文件"""
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_dir / "nonexistent.txt"))

        assert result.status == "error"
        assert result.error_type == "file_not_found"

    @pytest.mark.asyncio
    async def test_read_directory(self, temp_dir):
        """读取目录（应该失败）"""
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_dir))

        assert result.status == "error"
        assert result.error_type == "not_a_file"

    @pytest.mark.asyncio
    async def test_truncation(self, temp_dir):
        """长内容应该被截断"""
        test_file = temp_dir / "long.txt"
        test_file.write_text("x" * 5000, encoding="utf-8")

        tool = ReadFileTool()
        result = await tool.execute(path=str(test_file))

        assert result.status == "success"
        assert "内容截断" in result.output
        assert result.metadata.get("truncated") is True

    @pytest.mark.asyncio
    async def test_missing_path(self):
        """缺少 path 参数"""
        tool = ReadFileTool()
        result = await tool.execute()

        assert result.status == "error"
        assert result.error_type == "missing_parameter"


class TestWriteFileTool:
    """测试 WriteFileTool"""

    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_write_file(self, temp_dir):
        """写入文件"""
        test_file = temp_dir / "output.txt"
        tool = WriteFileTool(project_dir=str(temp_dir))
        result = await tool.execute(path=str(test_file), content="test content")

        assert result.status == "success"
        assert test_file.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_write_creates_dirs(self, temp_dir):
        """自动创建父目录"""
        test_file = temp_dir / "subdir" / "nested" / "output.txt"
        tool = WriteFileTool(project_dir=str(temp_dir))
        result = await tool.execute(path=str(test_file), content="test")

        assert result.status == "success"
        assert test_file.exists()

    @pytest.mark.asyncio
    async def test_write_outside_project(self, temp_dir):
        """写入项目外路径（应该失败）"""
        outside_file = Path(temp_dir).parent / "outside.txt"
        tool = WriteFileTool(project_dir=str(temp_dir))
        result = await tool.execute(path=str(outside_file), content="test")

        assert result.status == "error"
        assert result.error_type == "path_outside_project"

    def test_preview(self, temp_dir):
        """预览功能"""
        tool = WriteFileTool(project_dir=str(temp_dir))
        preview = tool.preview("test.txt", "hello world")
        assert "test.txt" in preview
        assert "hello world" in preview


class TestSearchFilesTool:
    """测试 SearchFilesTool"""

    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_search_found(self, temp_dir):
        """搜索到匹配内容"""
        test_file = temp_dir / "test.py"
        test_file.write_text("def hello():\n    pass\n\ndef world():\n    pass", encoding="utf-8")

        tool = SearchFilesTool(project_dir=str(temp_dir))
        result = await tool.execute(pattern="def ", glob="*.py")

        assert result.status == "success"
        assert "2 个匹配" in result.output or "找到" in result.output

    @pytest.mark.asyncio
    async def test_search_not_found(self, temp_dir):
        """搜索不到匹配内容"""
        test_file = temp_dir / "test.py"
        test_file.write_text("hello world", encoding="utf-8")

        tool = SearchFilesTool(project_dir=str(temp_dir))
        result = await tool.execute(pattern="nonexistent_pattern")

        assert result.status == "success"
        assert "0 个匹配" in result.output

    @pytest.mark.asyncio
    async def test_search_invalid_regex(self, temp_dir):
        """无效正则表达式"""
        tool = SearchFilesTool(project_dir=str(temp_dir))
        result = await tool.execute(pattern="[invalid")

        assert result.status == "error"
        assert result.error_type == "invalid_regex"

    @pytest.mark.asyncio
    async def test_search_max_results(self, temp_dir):
        """最大结果数限制"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("\n".join([f"line {i}" for i in range(100)]), encoding="utf-8")

        tool = SearchFilesTool(project_dir=str(temp_dir))
        result = await tool.execute(pattern="line", max_results=5)

        assert result.status == "success"
        assert result.metadata.get("total_matches", 0) <= 5


class TestListFilesTool:
    """测试 ListFilesTool"""

    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_list_directory(self, temp_dir):
        """列出目录内容"""
        (temp_dir / "file1.txt").write_text("a")
        (temp_dir / "file2.py").write_text("b")
        (temp_dir / "subdir").mkdir()

        tool = ListFilesTool(project_dir=str(temp_dir))
        result = await tool.execute(path=str(temp_dir))

        assert result.status == "success"
        assert "file1.txt" in result.output
        assert "file2.py" in result.output
        assert "subdir/" in result.output

    @pytest.mark.asyncio
    async def test_list_with_pattern(self, temp_dir):
        """带通配符过滤"""
        (temp_dir / "file1.txt").write_text("a")
        (temp_dir / "file2.py").write_text("b")

        tool = ListFilesTool(project_dir=str(temp_dir))
        result = await tool.execute(path=str(temp_dir), pattern="*.py")

        assert result.status == "success"
        assert "file2.py" in result.output
        assert "file1.txt" not in result.output

    @pytest.mark.asyncio
    async def test_list_nonexistent(self, temp_dir):
        """列出不存在的目录"""
        tool = ListFilesTool(project_dir=str(temp_dir))
        result = await tool.execute(path=str(temp_dir / "nonexistent"))

        assert result.status == "error"
        assert result.error_type == "directory_not_found"


class TestGetFileInfoTool:
    """测试 GetFileInfoTool"""

    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_get_file_info(self, temp_dir):
        """获取文件信息"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello", encoding="utf-8")

        tool = GetFileInfoTool(project_dir=str(temp_dir))
        result = await tool.execute(path=str(test_file))

        assert result.status == "success"
        assert "test.txt" in result.output
        assert result.metadata.get("size") == 5

    @pytest.mark.asyncio
    async def test_get_directory_info(self, temp_dir):
        """获取目录信息"""
        tool = GetFileInfoTool(project_dir=str(temp_dir))
        result = await tool.execute(path=str(temp_dir))

        assert result.status == "success"
        assert result.metadata.get("type") == "directory"

    @pytest.mark.asyncio
    async def test_get_nonexistent_info(self, temp_dir):
        """获取不存在文件的信息"""
        tool = GetFileInfoTool(project_dir=str(temp_dir))
        result = await tool.execute(path=str(temp_dir / "nonexistent"))

        assert result.status == "error"
        assert result.error_type == "file_not_found"
