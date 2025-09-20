import os
import fnmatch
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from .base_tool import BaseTool, ToolContext, ToolResult


# 默认忽略的目录和文件模式
IGNORE_PATTERNS = [
    "node_modules/",
    "__pycache__/",
    ".git/",
    "dist/",
    "build/",
    "target/",
    "vendor/",
    "bin/",
    "obj/",
    ".idea/",
    ".vscode/",
    ".zig-cache/",
    "zig-out/",
    ".coverage",
    "coverage/",
    "tmp/",
    "temp/",
    ".cache/",
    "cache/",
    "logs/",
    ".venv/",
    "venv/",
    "env/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".tox/",
    "*.pyc",
    "*.pyo",
    "*.egg-info/",
    ".DS_Store",
    "Thumbs.db"
]

# 结果数量限制
LIMIT = 100


class ListTool(BaseTool[Dict[str, Any]]):
    """目录结构列表工具"""
    
    def __init__(self):
        description = """列出指定目录下的文件和子目录结构

功能特点：
- 显示目录的树状结构
- 自动忽略常见的构建输出、缓存、版本控制等目录
- 支持自定义忽略模式
- 按字母顺序排序
- 限制结果数量以保持响应速度

用法：
- path: 可选，要列出的目录路径，必须是绝对路径，默认为当前工作目录
- ignore: 可选，要忽略的glob模式列表，如["*.log", "temp*"]
- show_hidden: 可选，是否显示隐藏文件（以.开头的文件），默认为False
- max_depth: 可选，最大递归深度，默认无限制

输出格式：
- 以树状结构显示目录和文件
- 目录名后带有/标识
- 使用缩进表示层级关系

注意：
- 为保持响应速度，结果会被限制在前100个条目
- 默认忽略常见的构建输出和缓存目录
- 如果结果被截断，会显示提示信息"""
        
        super().__init__("list", description)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要列出的目录路径，必须是绝对路径，默认为当前工作目录"
                },
                "ignore": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要忽略的glob模式列表"
                },
                "show_hidden": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否显示隐藏文件"
                },
                "max_depth": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "最大递归深度"
                }
            },
            "required": []
        }
    
    def _should_ignore(self, path: str, ignore_patterns: List[str], show_hidden: bool) -> bool:
        """检查是否应该忽略该路径"""
        path_obj = Path(path)
        
        # 检查是否为隐藏文件
        if not show_hidden and path_obj.name.startswith('.'):
            return True
        
        # 检查默认忽略模式
        for pattern in IGNORE_PATTERNS:
            if pattern.endswith('/'):
                # 目录模式
                if pattern[:-1] in str(path_obj) or path_obj.name == pattern[:-1]:
                    return True
            else:
                # 文件模式
                if fnmatch.fnmatch(path_obj.name, pattern) or fnmatch.fnmatch(str(path_obj), pattern):
                    return True
        
        # 检查自定义忽略模式
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(path_obj.name, pattern) or fnmatch.fnmatch(str(path_obj), pattern):
                return True
        
        return False
    
    def _collect_files(self, root_path: str, ignore_patterns: List[str], show_hidden: bool, max_depth: Optional[int]) -> List[str]:
        """收集文件列表"""
        files = []
        
        def _walk_directory(current_path: str, current_depth: int = 0):
            if max_depth is not None and current_depth > max_depth:
                return
            
            if len(files) >= LIMIT:
                return
            
            try:
                entries = os.listdir(current_path)
                entries.sort()  # 按字母顺序排序
                
                for entry in entries:
                    if len(files) >= LIMIT:
                        break
                    
                    full_path = os.path.join(current_path, entry)
                    rel_path = os.path.relpath(full_path, root_path)
                    
                    # 检查是否应该忽略
                    if self._should_ignore(full_path, ignore_patterns, show_hidden):
                        continue
                    
                    files.append(rel_path)
                    
                    # 如果是目录，递归处理
                    if os.path.isdir(full_path):
                        _walk_directory(full_path, current_depth + 1)
                        
            except (PermissionError, OSError):
                # 忽略无权限访问的目录
                pass
        
        _walk_directory(root_path)
        return files
    
    def _build_tree_structure(self, files: List[str]) -> Dict[str, Any]:
        """构建树状结构"""
        tree = {}
        
        for file_path in files:
            parts = file_path.split(os.sep)
            current = tree
            
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {}
                
                # 如果这是最后一个部分且不是目录，标记为文件
                if i == len(parts) - 1:
                    full_path = os.path.join(os.getcwd(), file_path) if not os.path.isabs(file_path) else file_path
                    if not os.path.isdir(full_path):
                        current[part] = None  # 文件标记为None
                
                if current[part] is not None:
                    current = current[part]
        
        return tree
    
    def _render_tree(self, tree: Dict[str, Any], prefix: str = "", is_last: bool = True, root_path: str = "") -> List[str]:
        """渲染树状结构"""
        lines = []
        items = sorted(tree.items(), key=lambda x: (x[1] is None, x[0]))  # 目录在前，文件在后
        
        for i, (name, subtree) in enumerate(items):
            is_last_item = i == len(items) - 1
            
            # 确定当前项的连接符
            if prefix == "":
                # 根目录项
                connector = ""
                new_prefix = ""
            else:
                connector = "└── " if is_last_item else "├── "
                new_prefix = prefix + ("    " if is_last_item else "│   ")
            
            # 构建显示名称
            if subtree is None:
                # 文件
                display_name = name
            else:
                # 目录
                display_name = name + "/"
            
            lines.append(f"{prefix}{connector}{display_name}")
            
            # 递归处理子目录
            if subtree is not None and subtree:
                lines.extend(self._render_tree(subtree, new_prefix, is_last_item, root_path))
        
        return lines
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行目录列表"""
        # 获取搜索路径
        search_path = params.get("path", os.getcwd())
        if not os.path.isabs(search_path):
            search_path = os.path.abspath(search_path)
        
        # 检查路径是否存在
        if not os.path.exists(search_path):
            return ToolResult(
                title=f"Directory: {search_path}",
                output=f"Error: Directory '{search_path}' does not exist",
                metadata={"count": 0, "truncated": False, "error": True}
            )
        
        if not os.path.isdir(search_path):
            return ToolResult(
                title=f"Path: {search_path}",
                output=f"Error: '{search_path}' is not a directory",
                metadata={"count": 0, "truncated": False, "error": True}
            )
        
        # 获取参数
        ignore_patterns = params.get("ignore", [])
        show_hidden = params.get("show_hidden", False)
        max_depth = params.get("max_depth")
        
        try:
            # 收集文件列表
            files = self._collect_files(search_path, ignore_patterns, show_hidden, max_depth)
            
            if not files:
                return ToolResult(
                    title=os.path.basename(search_path) or search_path,
                    output=f"{search_path}/\n  (empty directory)",
                    metadata={"count": 0, "truncated": False}
                )
            
            # 构建树状结构
            tree = self._build_tree_structure(files)
            
            # 渲染树状结构
            tree_lines = self._render_tree(tree, "", True, search_path)
            
            # 构建输出
            output_lines = [f"{search_path}/"]
            output_lines.extend(tree_lines)
            
            # 检查是否被截断
            truncated = len(files) >= LIMIT
            if truncated:
                output_lines.append("")
                output_lines.append("(Results are truncated. Consider using a more specific path or ignore patterns.)")
            
            output = "\n".join(output_lines)
            
            return ToolResult(
                title=os.path.basename(search_path) or search_path,
                output=output,
                metadata={
                    "count": len(files),
                    "truncated": truncated,
                    "path": search_path
                }
            )
            
        except Exception as e:
            return ToolResult(
                title=f"Directory: {search_path}",
                output=f"Error listing directory: {str(e)}",
                metadata={"count": 0, "truncated": False, "error": True}
            )
