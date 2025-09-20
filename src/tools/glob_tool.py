import os
import glob
import fnmatch
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from .base_tool import BaseTool, ToolContext, ToolResult


class GlobTool(BaseTool[Dict[str, Any]]):
    """文件名模式匹配工具"""
    
    def __init__(self):
        description = """文件名模式匹配工具，用于查找匹配特定模式的文件

使用场景：
- 查找特定类型的文件（如所有.py文件）
- 按文件名模式搜索文件
- 递归搜索目录结构
- 批量文件操作前的文件收集

特点：
- 支持标准glob模式匹配
- 自动递归搜索子目录
- 按修改时间排序结果
- 自动限制结果数量
- 支持多种文件匹配模式

模式语法：
- * 匹配任意字符（除了路径分隔符）
- ? 匹配单个字符
- [seq] 匹配seq中的任意字符
- [!seq] 匹配不在seq中的任意字符
- ** 递归匹配任意层级目录
- {a,b} 匹配a或b（需要使用pattern参数）

用法：
- pattern: 要匹配的文件模式，如"*.py", "**/*.js", "test_*.py"
- path: 可选，搜索的根目录，默认为当前工作目录

注意：
- 如果未指定路径，将使用当前工作目录
- 结果按修改时间降序排序
- 结果数量限制为100个以保持响应速度
- 不以"**/"开头的模式会自动添加"**/"以启用递归搜索"""
        
        super().__init__("glob", description)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "要匹配的文件模式，如'*.py', '**/*.js', 'test_*.py'"
                },
                "path": {
                    "type": "string",
                    "description": "搜索的根目录路径，默认为当前工作目录。重要：省略此字段以使用默认目录，不要输入'undefined'或'null'"
                }
            },
            "required": ["pattern"]
        }
    
    def _expand_braces(self, pattern: str) -> List[str]:
        """展开大括号模式，如{a,b}变成[a, b]"""
        if '{' not in pattern or '}' not in pattern:
            return [pattern]
        
        patterns = []
        start = pattern.find('{')
        end = pattern.find('}', start)
        
        if start == -1 or end == -1:
            return [pattern]
        
        prefix = pattern[:start]
        suffix = pattern[end + 1:]
        options = pattern[start + 1:end].split(',')
        
        for option in options:
            new_pattern = prefix + option.strip() + suffix
            # 递归处理可能存在的嵌套大括号
            patterns.extend(self._expand_braces(new_pattern))
        
        return patterns
    
    def _glob_recursive(self, pattern: str, root_path: str) -> List[str]:
        """递归glob搜索"""
        matches = []
        
        # 展开大括号模式
        patterns = self._expand_braces(pattern)
        
        for pat in patterns:
            # 如果模式不以**/开头，自动添加以启用递归搜索
            if not pat.startswith('**/') and not os.path.isabs(pat):
                pat = '**/' + pat
            
            # 使用glob进行匹配
            full_pattern = os.path.join(root_path, pat)
            try:
                found = glob.glob(full_pattern, recursive=True)
                matches.extend(found)
            except Exception:
                # 如果glob失败，尝试手动递归搜索
                matches.extend(self._manual_recursive_search(pat, root_path))
        
        # 去重并过滤
        unique_matches = []
        seen = set()
        for match in matches:
            abs_match = os.path.abspath(match)
            if abs_match not in seen and os.path.isfile(abs_match):
                unique_matches.append(abs_match)
                seen.add(abs_match)
        
        return unique_matches
    
    def _manual_recursive_search(self, pattern: str, root_path: str) -> List[str]:
        """手动递归搜索（当glob失败时的后备方案）"""
        matches = []
        
        # 移除开头的**/
        if pattern.startswith('**/'):
            pattern = pattern[3:]
        
        try:
            for root, dirs, files in os.walk(root_path):
                # 跳过隐藏目录和常见的忽略目录
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    'node_modules', '__pycache__', '.git', 'dist', 'build', 
                    'target', 'vendor', 'bin', 'obj'
                }]
                
                for file in files:
                    if fnmatch.fnmatch(file, pattern):
                        full_path = os.path.join(root, file)
                        matches.append(full_path)
        except (OSError, PermissionError):
            pass  # 忽略权限错误
        
        return matches
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行glob匹配"""
        pattern = params["pattern"]
        if not pattern:
            raise ValueError("pattern is required")
        
        # 确定搜索路径
        search_path = params.get("path", os.getcwd())
        if not os.path.isabs(search_path):
            search_path = os.path.abspath(search_path)
        
        # 验证搜索路径存在
        if not os.path.exists(search_path):
            return ToolResult(
                title=pattern,
                output=f"Error: Search path does not exist: {search_path}",
                metadata={"count": 0, "truncated": False, "error": True}
            )
        
        if not os.path.isdir(search_path):
            return ToolResult(
                title=pattern,
                output=f"Error: Search path is not a directory: {search_path}",
                metadata={"count": 0, "truncated": False, "error": True}
            )
        
        try:
            # 执行glob搜索
            matches = self._glob_recursive(pattern, search_path)
            
            if not matches:
                return ToolResult(
                    title=pattern,
                    output="No files found",
                    metadata={"count": 0, "truncated": False}
                )
            
            # 获取文件修改时间并排序
            files_with_mtime = []
            for file_path in matches:
                try:
                    mtime = os.path.getmtime(file_path)
                    files_with_mtime.append((file_path, mtime))
                except OSError:
                    # 如果无法获取修改时间，使用0
                    files_with_mtime.append((file_path, 0))
            
            # 按修改时间降序排序
            files_with_mtime.sort(key=lambda x: x[1], reverse=True)
            
            # 应用限制
            limit = 100
            truncated = len(files_with_mtime) > limit
            final_files = files_with_mtime[:limit] if truncated else files_with_mtime
            
            # 生成输出
            output_lines = []
            if final_files:
                # 显示相对路径（如果可能）
                display_files = []
                for file_path, _ in final_files:
                    try:
                        rel_path = os.path.relpath(file_path, search_path)
                        # 如果相对路径更短，使用相对路径，否则使用绝对路径
                        if len(rel_path) < len(file_path):
                            display_files.append(rel_path)
                        else:
                            display_files.append(file_path)
                    except ValueError:
                        # 如果无法计算相对路径，使用绝对路径
                        display_files.append(file_path)
                
                output_lines.extend(display_files)
                
                if truncated:
                    output_lines.append("")
                    output_lines.append("(Results are truncated. Consider using a more specific path or pattern.)")
            else:
                output_lines.append("No files found")
            
            return ToolResult(
                title=f"{pattern} in {os.path.basename(search_path)}",
                output="\n".join(output_lines),
                metadata={
                    "count": len(final_files),
                    "truncated": truncated,
                    "search_path": search_path
                }
            )
            
        except Exception as e:
            return ToolResult(
                title=pattern,
                output=f"Error during glob search: {str(e)}",
                metadata={"count": 0, "truncated": False, "error": True}
            )
