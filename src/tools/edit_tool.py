import os
import re
from typing import Dict, List, Any, Optional, Generator
from difflib import unified_diff
from .base_tool import BaseTool, ToolContext, ToolResult

class EditTool(BaseTool[Dict[str, Any]]):
    """文件编辑工具 - 执行精确的字符串替换"""
    
    def __init__(self):
        description = """执行文件中的精确字符串替换。

用法：
- 在编辑之前，您必须在对话中至少使用一次 `Read` 工具。如果您尝试在不读取文件的情况下编辑，此工具将出错
- 编辑来自 Read 工具输出的文本时，请确保保留行号前缀后显示的确切缩进（制表符/空格）。行号前缀格式为：空格 + 行号 + 制表符。制表符后的所有内容都是要匹配的实际文件内容。切勿在 oldString 或 newString 中包含行号前缀的任何部分
- 始终优先编辑代码库中的现有文件。除非明确要求，否则切勿编写新文件
- 仅在用户明确要求时使用表情符号。除非被要求，否则避免向文件添加表情符号
- 如果 `oldString` 在文件中不唯一，编辑将失败。要么提供更大的字符串和更多周围上下文以使其唯一，要么使用 `replaceAll` 更改 `oldString` 的每个实例
- 使用 `replaceAll` 在整个文件中替换和重命名字符串。例如，如果您想重命名变量，此参数很有用"""
        
        super().__init__("edit", description)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "要修改的文件的绝对路径"
                },
                "oldString": {
                    "type": "string",
                    "description": "要替换的文本"
                },
                "newString": {
                    "type": "string",
                    "description": "要替换为的文本（必须与 oldString 不同）"
                },
                "replaceAll": {
                    "type": "boolean",
                    "description": "替换 oldString 的所有出现（默认为 false）",
                    "default": False
                }
            },
            "required": ["filePath", "oldString", "newString"]
        }
    
    def _levenshtein_distance(self, a: str, b: str) -> int:
        """计算两个字符串的编辑距离"""
        if not a or not b:
            return max(len(a), len(b))
        
        matrix = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
        
        for i in range(len(a) + 1):
            matrix[i][0] = i
        for j in range(len(b) + 1):
            matrix[0][j] = j
        
        for i in range(1, len(a) + 1):
            for j in range(1, len(b) + 1):
                cost = 0 if a[i-1] == b[j-1] else 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # 删除
                    matrix[i][j-1] + 1,      # 插入
                    matrix[i-1][j-1] + cost  # 替换
                )
        
        return matrix[len(a)][len(b)]
    
    def _simple_replacer(self, content: str, find: str) -> Generator[str, None, None]:
        """简单替换器 - 直接查找"""
        if find in content:
            yield find
    
    def _line_trimmed_replacer(self, content: str, find: str) -> Generator[str, None, None]:
        """行修剪替换器 - 忽略行首尾空白"""
        original_lines = content.split('\n')
        search_lines = find.split('\n')
        
        if search_lines and search_lines[-1] == '':
            search_lines.pop()
        
        for i in range(len(original_lines) - len(search_lines) + 1):
            matches = True
            
            for j in range(len(search_lines)):
                original_trimmed = original_lines[i + j].strip()
                search_trimmed = search_lines[j].strip()
                
                if original_trimmed != search_trimmed:
                    matches = False
                    break
            
            if matches:
                # 计算匹配的起始和结束位置
                match_start = sum(len(original_lines[k]) + 1 for k in range(i))
                match_end = match_start
                
                for k in