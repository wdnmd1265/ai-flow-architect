"""
文件系统工具 - 只读工具 + 受限写入工具
"""

import os
import fnmatch
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

from .base import Tool, ToolResult


# 结果截断上限
MAX_TOOL_RESULT = 4000


def _truncate(text: str, limit: int = MAX_TOOL_RESULT) -> str:
    """截断文本，附带告知"""
    if len(text) <= limit:
        return text
    return (
        text[:limit]
        + f"\n\n[内容截断：原始 {len(text)} 字符，"
        f"超过上限 {limit} 字符。如需完整内容请缩小范围。]"
    )


class ReadFileTool(Tool):
    """读取文件内容"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取指定路径的文件内容。只读操作，不会修改任何文件。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码，默认 utf-8",
                    "default": "utf-8"
                }
            },
            "required": ["path"]
        }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path")
        encoding = kwargs.get("encoding", "utf-8")

        if not path:
            return self._error("missing_parameter", "缺少必需参数 path")

        try:
            file_path = Path(path)
            if not file_path.exists():
                return self._error(
                    "file_not_found",
                    f"文件 {path} 不存在",
                    suggestion="检查路径拼写或先使用 search_files 查找"
                )

            if not file_path.is_file():
                return self._error(
                    "not_a_file",
                    f"{path} 不是文件",
                    suggestion="使用 list_files 查看目录内容"
                )

            content = file_path.read_text(encoding=encoding)
            truncated = _truncate(content)

            logger.info(f"read_file: {path} ({len(content)} chars)")
            return self._success(
                truncated,
                path=str(file_path.absolute()),
                size=len(content),
                truncated=len(content) > MAX_TOOL_RESULT,
            )

        except UnicodeDecodeError:
            return self._error(
                "encoding_error",
                f"无法用 {encoding} 编码读取文件",
                suggestion="文件可能是二进制文件，或尝试指定其他编码"
            )
        except PermissionError:
            return self._error(
                "permission_denied",
                f"没有权限读取文件 {path}",
                suggestion="检查文件权限"
            )
        except Exception as e:
            return self._error("unknown_error", str(e))


class WriteFileTool(Tool):
    """写入文件（需要审批）"""

    def __init__(self, project_dir: str = None):
        """
        初始化写入工具

        Args:
            project_dir: 项目根目录，写入操作限制在此目录内
        """
        self.project_dir = Path(project_dir) if project_dir else None

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "写入文件内容。注意：此操作需要用户审批，写入前会展示文件路径和内容预览。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文件内容"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码，默认 utf-8",
                    "default": "utf-8"
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "是否自动创建父目录，默认 true",
                    "default": True
                }
            },
            "required": ["path", "content"]
        }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path")
        content = kwargs.get("content")
        encoding = kwargs.get("encoding", "utf-8")
        create_dirs = kwargs.get("create_dirs", True)
        
        # 警告：write_file 会在审批流程实现前直接写入
        logger.warning(f"write_file 直接执行（审批流程尚未实现）: {path}")

        if not path:
            return self._error("missing_parameter", "缺少必需参数 path")
        if content is None:
            return self._error("missing_parameter", "缺少必需参数 content")

        try:
            file_path = Path(path)

            # 路径安全检查：限制在 project_dir 内
            if self.project_dir:
                try:
                    resolved = file_path.resolve()
                    project_resolved = self.project_dir.resolve()
                    if not str(resolved).startswith(str(project_resolved)):
                        return self._error(
                            "path_outside_project",
                            f"路径 {path} 超出项目目录范围",
                            suggestion=f"只能写入 {self.project_dir} 内的文件"
                        )
                except Exception:
                    pass  # 路径解析失败时跳过检查

            # 创建父目录
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            file_path.write_text(content, encoding=encoding)

            logger.info(f"write_file: {path} ({len(content)} chars)")
            return self._success(
                f"文件写入成功: {path}",
                path=str(file_path.absolute()),
                size=len(content),
            )

        except PermissionError:
            return self._error(
                "permission_denied",
                f"没有权限写入文件 {path}",
                suggestion="检查目录权限"
            )
        except Exception as e:
            return self._error("unknown_error", str(e))

    def preview(self, path: str, content: str) -> str:
        """生成审批预览"""
        preview_content = _truncate(content, 500)
        return f"文件路径: {path}\n内容预览:\n{preview_content}"


class SearchFilesTool(Tool):
    """搜索文件内容"""

    def __init__(self, project_dir: str = None):
        self.project_dir = Path(project_dir) if project_dir else Path(".")

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "在项目中搜索文件内容，支持通配符过滤。返回匹配的文件和行号。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "搜索的文本模式（支持正则表达式）"
                },
                "glob": {
                    "type": "string",
                    "description": "文件名过滤（通配符），如 '*.py'、'*.yaml'",
                    "default": "*"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数，默认 20",
                    "default": 20
                }
            },
            "required": ["pattern"]
        }

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern")
        glob_pattern = kwargs.get("glob", "*")
        max_results = kwargs.get("max_results", 20)

        if not pattern:
            return self._error("missing_parameter", "缺少必需参数 pattern")

        try:
            import re
            regex = re.compile(pattern)
        except re.error as e:
            return self._error(
                "invalid_regex",
                f"正则表达式无效: {e}",
                suggestion="检查正则表达式语法"
            )

        results = []
        files_searched = 0

        try:
            for root, dirs, files in os.walk(self.project_dir):
                # 跳过隐藏目录和常见忽略目录
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    '__pycache__', 'node_modules', '.git', '.venv', 'venv'
                }]

                for file in files:
                    if not fnmatch.fnmatch(file, glob_pattern):
                        continue

                    file_path = Path(root) / file
                    files_searched += 1

                    try:
                        content = file_path.read_text(encoding='utf-8')
                        for i, line in enumerate(content.splitlines(), 1):
                            if regex.search(line):
                                rel_path = file_path.relative_to(self.project_dir)
                                results.append({
                                    "file": str(rel_path),
                                    "line": i,
                                    "content": line.strip()[:200],
                                })
                                if len(results) >= max_results:
                                    break
                    except (UnicodeDecodeError, PermissionError):
                        continue

                    if len(results) >= max_results:
                        break

                if len(results) >= max_results:
                    break

            output_lines = [f"搜索完成，找到 {len(results)} 个匹配（搜索了 {files_searched} 个文件）"]
            for r in results:
                output_lines.append(f"{r['file']}:{r['line']}: {r['content']}")

            logger.info(f"search_files: pattern={pattern}, found={len(results)}")
            return self._success(
                _truncate("\n".join(output_lines)),
                total_matches=len(results),
                files_searched=files_searched,
            )

        except Exception as e:
            return self._error("unknown_error", str(e))


class ListFilesTool(Tool):
    """列出目录内容"""

    def __init__(self, project_dir: str = None):
        self.project_dir = Path(project_dir) if project_dir else Path(".")

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "列出指定目录下的文件和子目录。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径（相对于项目根目录），默认为根目录",
                    "default": "."
                },
                "pattern": {
                    "type": "string",
                    "description": "文件名过滤（通配符），如 '*.py'",
                    "default": "*"
                },
                "max_depth": {
                    "type": "integer",
                    "description": "递归深度，默认 1（只看当前层）",
                    "default": 1
                }
            }
        }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        pattern = kwargs.get("pattern", "*")
        max_depth = kwargs.get("max_depth", 1)

        try:
            target_dir = self.project_dir / path

            if not target_dir.exists():
                return self._error(
                    "directory_not_found",
                    f"目录 {path} 不存在",
                    suggestion="检查路径拼写"
                )

            if not target_dir.is_dir():
                return self._error(
                    "not_a_directory",
                    f"{path} 不是目录",
                    suggestion="使用 read_file 读取文件内容"
                )

            entries = []
            self._scan_directory(target_dir, pattern, 0, max_depth, entries)

            output_lines = [f"目录 {path} 内容（共 {len(entries)} 项）"]
            for entry in entries[:50]:  # 最多显示50项
                output_lines.append(entry)

            if len(entries) > 50:
                output_lines.append(f"... 还有 {len(entries) - 50} 项")

            logger.info(f"list_files: {path}, found={len(entries)}")
            return self._success(
                "\n".join(output_lines),
                total_entries=len(entries),
            )

        except Exception as e:
            return self._error("unknown_error", str(e))

    def _scan_directory(
        self,
        directory: Path,
        pattern: str,
        current_depth: int,
        max_depth: int,
        entries: List[str],
        prefix: str = "",
    ):
        """递归扫描目录"""
        if current_depth > max_depth:
            return

        try:
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            for item in items:
                if item.name.startswith('.'):
                    continue

                if item.is_dir():
                    entries.append(f"{prefix}{item.name}/")
                    if current_depth < max_depth:
                        self._scan_directory(
                            item, pattern, current_depth + 1, max_depth,
                            entries, prefix + "  "
                        )
                else:
                    if fnmatch.fnmatch(item.name, pattern):
                        size = item.stat().st_size
                        entries.append(f"{prefix}{item.name} ({size} bytes)")
        except PermissionError:
            entries.append(f"{prefix}[权限不足]")


class GetFileInfoTool(Tool):
    """获取文件元信息"""

    def __init__(self, project_dir: str = None):
        self.project_dir = Path(project_dir) if project_dir else Path(".")

    @property
    def name(self) -> str:
        return "get_file_info"

    @property
    def description(self) -> str:
        return "获取文件的元信息（大小、修改时间、类型等），不读取内容。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于项目根目录）"
                }
            },
            "required": ["path"]
        }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path")

        if not path:
            return self._error("missing_parameter", "缺少必需参数 path")

        try:
            file_path = Path(path)

            if not file_path.exists():
                return self._error(
                    "file_not_found",
                    f"文件 {path} 不存在",
                    suggestion="检查路径拼写"
                )

            stat = file_path.stat()
            info = {
                "name": file_path.name,
                "path": str(file_path.absolute()),
                "type": "directory" if file_path.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
            }

            if file_path.is_file():
                info["extension"] = file_path.suffix

            output = "\n".join(f"{k}: {v}" for k, v in info.items())
            logger.info(f"get_file_info: {path}")
            return self._success(output, **info)

        except Exception as e:
            return self._error("unknown_error", str(e))
