import os
import subprocess
import shutil
from typing import Dict, List, Any, Optional
from pathlib import Path
from .base_tool import BaseTool, ToolContext, ToolResult


class GrepTool(BaseTool[Dict[str, Any]]):
    """基于ripgrep的文件内容搜索工具"""
    
    def __init__(self):
        description = """强大的文件内容搜索工具，基于ripgrep构建

使用场景：
- 在代码库中搜索特定模式或字符串
- 支持正则表达式搜索
- 快速查找函数、类、变量定义
- 搜索特定文件类型中的内容

特点：
- 基于ripgrep，搜索速度极快
- 自动忽略.gitignore中的文件
- 支持文件类型过滤
- 按修改时间排序结果
- 自动限制结果数量以保持响应速度

用法：
- pattern: 要搜索的正则表达式模式
- path: 可选，搜索的目录路径，默认为当前工作目录
- include: 可选，要包含的文件模式，如"*.py", "*.{js,ts}"
- output_mode: 输出模式 - "content"显示匹配行(默认)，"files_with_matches"只显示文件路径，"count"显示匹配计数
- context_before: 显示匹配行前的行数
- context_after: 显示匹配行后的行数
- case_insensitive: 是否忽略大小写
- multiline: 是否启用多行模式
- head_limit: 限制输出的前N行/条目

注意：结果会被截断以保持响应速度；如果结果过多，请使用更具体的路径或模式"""
        
        super().__init__("grep", description)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "要搜索的正则表达式模式"
                },
                "path": {
                    "type": "string",
                    "description": "搜索的目录路径，默认为当前工作目录"
                },
                "include": {
                    "type": "string",
                    "description": "要包含的文件模式，如'*.py', '*.{js,ts}'"
                },
                "output_mode": {
                    "type": "string",
                    "enum": ["content", "files_with_matches", "count"],
                    "default": "content",
                    "description": "输出模式：content显示匹配行，files_with_matches只显示文件路径，count显示匹配计数"
                },
                "context_before": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "显示匹配行前的行数"
                },
                "context_after": {
                    "type": "integer", 
                    "minimum": 0,
                    "description": "显示匹配行后的行数"
                },
                "case_insensitive": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否忽略大小写"
                },
                "multiline": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否启用多行模式"
                },
                "head_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "限制输出的前N行/条目"
                }
            },
            "required": ["pattern"]
        }
    
    def _find_ripgrep(self) -> str:
        """查找ripgrep可执行文件"""
        # 首先尝试从PATH中查找
        rg_path = shutil.which("rg")
        if rg_path:
            return rg_path
        
        # 如果没找到，抛出异常
        raise FileNotFoundError("ripgrep (rg) not found in PATH. Please install ripgrep.")
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行grep搜索"""
        pattern = params["pattern"]
        if not pattern:
            raise ValueError("pattern is required")
        
        search_path = params.get("path", os.getcwd())
        if not os.path.isabs(search_path):
            search_path = os.path.abspath(search_path)
        
        try:
            rg_path = self._find_ripgrep()
        except FileNotFoundError as e:
            return ToolResult(
                title=pattern,
                output=str(e),
                metadata={"matches": 0, "truncated": False, "error": True}
            )
        
        # 构建ripgrep命令参数
        args = [rg_path, "-n", pattern]  # -n显示行号
        
        # 添加文件包含模式
        if "include" in params:
            args.extend(["--glob", params["include"]])
        
        # 添加输出模式
        output_mode = params.get("output_mode", "content")
        if output_mode == "files_with_matches":
            args.append("-l")  # 只显示文件名
        elif output_mode == "count":
            args.append("-c")  # 显示匹配计数
        
        # 添加上下文行
        if "context_before" in params:
            args.extend(["-B", str(params["context_before"])])
        if "context_after" in params:
            args.extend(["-A", str(params["context_after"])])
        
        # 添加大小写敏感性
        if params.get("case_insensitive", False):
            args.append("-i")
        
        # 添加多行模式
        if params.get("multiline", False):
            args.extend(["-U", "--multiline-dotall"])
        
        # 添加搜索路径
        args.append(search_path)
        
        try:
            # 执行ripgrep命令
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=30  # 30秒超时
            )
            
            # 处理结果
            if result.returncode == 1:  # 没有找到匹配
                return ToolResult(
                    title=pattern,
                    output="No files found",
                    metadata={"matches": 0, "truncated": False}
                )
            
            if result.returncode != 0:  # 其他错误
                error_msg = result.stderr.strip() if result.stderr else "ripgrep failed"
                return ToolResult(
                    title=pattern,
                    output=f"Error: {error_msg}",
                    metadata={"matches": 0, "truncated": False, "error": True}
                )
            
            output = result.stdout.strip()
            if not output:
                return ToolResult(
                    title=pattern,
                    output="No files found",
                    metadata={"matches": 0, "truncated": False}
                )
            
            # 处理输出
            lines = output.split("\n")
            
            # 应用head_limit限制
            head_limit = params.get("head_limit")
            truncated = False
            if head_limit and len(lines) > head_limit:
                lines = lines[:head_limit]
                truncated = True
            
            # 格式化输出
            if output_mode == "content":
                formatted_output = self._format_content_output(lines, search_path)
            elif output_mode == "files_with_matches":
                formatted_output = self._format_files_output(lines)
            elif output_mode == "count":
                formatted_output = self._format_count_output(lines)
            else:
                formatted_output = "\n".join(lines)
            
            if truncated:
                formatted_output += "\n\n(Results are truncated. Consider using a more specific path or pattern.)"
            
            return ToolResult(
                title=pattern,
                output=formatted_output,
                metadata={
                    "matches": len(lines),
                    "truncated": truncated,
                    "output_mode": output_mode
                }
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                title=pattern,
                output="Search timed out. Consider using a more specific pattern or path.",
                metadata={"matches": 0, "truncated": False, "error": True}
            )
        except Exception as e:
            return ToolResult(
                title=pattern,
                output=f"Error executing search: {str(e)}",
                metadata={"matches": 0, "truncated": False, "error": True}
            )
    
    def _format_content_output(self, lines: List[str], search_path: str) -> str:
        """格式化内容输出"""
        if not lines:
            return "No matches found"
        
        output_lines = [f"Found {len(lines)} matches"]
        current_file = ""
        
        for line in lines:
            if not line:
                continue
            
            # 解析ripgrep输出格式: file:line:content
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            
            file_path, line_num, content = parts
            
            # 显示文件名（如果改变了）
            if current_file != file_path:
                if current_file != "":
                    output_lines.append("")
                current_file = file_path
                # 显示相对路径
                try:
                    rel_path = os.path.relpath(file_path, search_path)
                    output_lines.append(f"{rel_path}:")
                except ValueError:
                    output_lines.append(f"{file_path}:")
            
            # 显示匹配行
            output_lines.append(f"  Line {line_num}: {content}")
        
        return "\n".join(output_lines)
    
    def _format_files_output(self, lines: List[str]) -> str:
        """格式化文件列表输出"""
        if not lines:
            return "No files found"
        
        # 按修改时间排序文件
        files_with_mtime = []
        for file_path in lines:
            if os.path.exists(file_path):
                mtime = os.path.getmtime(file_path)
                files_with_mtime.append((file_path, mtime))
        
        files_with_mtime.sort(key=lambda x: x[1], reverse=True)
        sorted_files = [f[0] for f in files_with_mtime]
        
        output_lines = [f"Found {len(sorted_files)} files"]
        output_lines.extend(sorted_files)
        
        return "\n".join(output_lines)
    
    def _format_count_output(self, lines: List[str]) -> str:
        """格式化计数输出"""
        if not lines:
            return "No matches found"
        
        output_lines = ["Match counts by file:"]
        total_matches = 0
        
        for line in lines:
            if ":" in line:
                file_path, count_str = line.rsplit(":", 1)
                try:
                    count = int(count_str)
                    total_matches += count
                    output_lines.append(f"  {file_path}: {count}")
                except ValueError:
                    output_lines.append(f"  {line}")
        
        output_lines.insert(1, f"Total matches: {total_matches}")
        output_lines.insert(2, "")
        
        return "\n".join(output_lines)
