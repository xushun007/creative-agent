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
                
                for k in range(len(search_lines)):
                    match_end += len(original_lines[i + k])
                    if k < len(search_lines) - 1:
                        match_end += 1  # 换行符
                
                yield content[match_start:match_end]
    
    def _whitespace_normalized_replacer(self, content: str, find: str) -> Generator[str, None, None]:
        """空白标准化替换器 - 标准化空白字符"""
        def normalize_whitespace(text: str) -> str:
            return re.sub(r'\s+', ' ', text).strip()
        
        normalized_find = normalize_whitespace(find)
        
        # 处理单行匹配
        lines = content.split('\n')
        for line in lines:
            if normalize_whitespace(line) == normalized_find:
                yield line
                continue
            
            # 检查子字符串匹配
            normalized_line = normalize_whitespace(line)
            if normalized_find in normalized_line:
                words = find.strip().split()
                if words:
                    pattern = r'\s+'.join(re.escape(word) for word in words)
                    try:
                        match = re.search(pattern, line)
                        if match:
                            yield match.group(0)
                    except re.error:
                        continue
        
        # 处理多行匹配
        find_lines = find.split('\n')
        if len(find_lines) > 1:
            for i in range(len(lines) - len(find_lines) + 1):
                block = '\n'.join(lines[i:i + len(find_lines)])
                if normalize_whitespace(block) == normalized_find:
                    yield block
    
    def _indentation_flexible_replacer(self, content: str, find: str) -> Generator[str, None, None]:
        """缩进灵活替换器 - 忽略缩进差异"""
        def remove_indentation(text: str) -> str:
            lines = text.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            
            if not non_empty_lines:
                return text
            
            min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
            
            result_lines = []
            for line in lines:
                if line.strip():
                    result_lines.append(line[min_indent:])
                else:
                    result_lines.append(line)
            
            return '\n'.join(result_lines)
        
        normalized_find = remove_indentation(find)
        content_lines = content.split('\n')
        find_lines = find.split('\n')
        
        for i in range(len(content_lines) - len(find_lines) + 1):
            block = '\n'.join(content_lines[i:i + len(find_lines)])
            if remove_indentation(block) == normalized_find:
                yield block
    
    def _block_anchor_replacer(self, content: str, find: str) -> Generator[str, None, None]:
        """块锚点替换器 - 使用首尾行作为锚点"""
        original_lines = content.split('\n')
        search_lines = find.split('\n')
        
        if len(search_lines) < 3:
            return
        
        if search_lines and search_lines[-1] == '':
            search_lines.pop()
        
        first_line_search = search_lines[0].strip()
        last_line_search = search_lines[-1].strip()
        
        # 找到所有候选位置
        candidates = []
        for i in range(len(original_lines)):
            if original_lines[i].strip() != first_line_search:
                continue
            
            # 查找匹配的最后一行
            for j in range(i + 2, len(original_lines)):
                if original_lines[j].strip() == last_line_search:
                    candidates.append((i, j))
                    break
        
        if not candidates:
            return
        
        # 如果只有一个候选，使用宽松的阈值
        if len(candidates) == 1:
            start_line, end_line = candidates[0]
            actual_block_size = end_line - start_line + 1
            
            similarity = 0
            lines_to_check = min(len(search_lines) - 2, actual_block_size - 2)
            
            if lines_to_check > 0:
                for j in range(1, min(len(search_lines) - 1, actual_block_size - 1) + 1):
                    original_line = original_lines[start_line + j].strip()
                    search_line = search_lines[j].strip()
                    max_len = max(len(original_line), len(search_line))
                    
                    if max_len == 0:
                        continue
                    
                    distance = self._levenshtein_distance(original_line, search_line)
                    similarity += (1 - distance / max_len) / lines_to_check
                    
                    if similarity >= 0.0:  # 宽松阈值
                        break
            else:
                similarity = 1.0
            
            if similarity >= 0.0:
                match_start = sum(len(original_lines[k]) + 1 for k in range(start_line))
                match_end = match_start
                
                for k in range(start_line, end_line + 1):
                    match_end += len(original_lines[k])
                    if k < end_line:
                        match_end += 1
                
                yield content[match_start:match_end]
    
    def _replace_content(self, content: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        """执行内容替换"""
        if old_string == new_string:
            raise ValueError("oldString 和 newString 必须不同")
        
        # 尝试不同的替换策略
        replacers = [
            self._simple_replacer,
            self._line_trimmed_replacer,
            self._whitespace_normalized_replacer,
            self._indentation_flexible_replacer,
            self._block_anchor_replacer,
        ]
        
        for replacer in replacers:
            for search_text in replacer(content, old_string):
                index = content.find(search_text)
                if index == -1:
                    continue
                
                if replace_all:
                    return content.replace(search_text, new_string)
                
                # 检查是否唯一
                last_index = content.rfind(search_text)
                if index != last_index:
                    continue  # 不唯一，尝试下一个
                
                # 执行单次替换
                return content[:index] + new_string + content[index + len(search_text):]
        
        raise ValueError("在内容中未找到 oldString 或找到多个匹配项")
    
    def _generate_diff(self, file_path: str, old_content: str, new_content: str) -> str:
        """生成差异报告"""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{os.path.basename(file_path)}",
            tofile=f"b/{os.path.basename(file_path)}",
            lineterm=""
        )
        
        return ''.join(diff)
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行文件编辑"""
        file_path = params["filePath"]
        old_string = params["oldString"]
        new_string = params["newString"]
        replace_all = params.get("replaceAll", False)
        
        # 验证参数
        if not file_path:
            return ToolResult(
                title="错误: 缺少文件路径",
                output="filePath 参数是必需的",
                metadata={"error": "missing_file_path"}
            )
        
        if old_string == new_string:
            return ToolResult(
                title="错误: 字符串相同",
                output="oldString 和 newString 必须不同",
                metadata={"error": "identical_strings"}
            )
        
        # 转换为绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        try:
            # 处理新文件创建（oldString 为空）
            if old_string == "":
                # 确保目录存在
                directory = os.path.dirname(file_path)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_string)
                
                diff = self._generate_diff(file_path, "", new_string)
                
                return ToolResult(
                    title=os.path.relpath(file_path, os.getcwd()),
                    output="文件创建成功",
                    metadata={
                        "file_path": file_path,
                        "diff": diff,
                        "action": "create"
                    }
                )
            
            # 检查文件是否存在（仅当不是创建新文件时）
            if not os.path.exists(file_path):
                return ToolResult(
                    title=f"错误: 文件未找到",
                    output=f"文件不存在: {file_path}",
                    metadata={"error": "file_not_found", "file_path": file_path}
                )
            
            # 检查是否为目录
            if os.path.isdir(file_path):
                return ToolResult(
                    title=f"错误: 路径是目录",
                    output=f"路径是目录，不是文件: {file_path}",
                    metadata={"error": "path_is_directory", "file_path": file_path}
                )
            
            # 读取现有文件
            with open(file_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
            
            # 执行替换
            try:
                new_content = self._replace_content(old_content, old_string, new_string, replace_all)
            except ValueError as e:
                return ToolResult(
                    title=f"编辑失败: {os.path.basename(file_path)}",
                    output=str(e),
                    metadata={
                        "error": "replacement_failed",
                        "file_path": file_path,
                        "old_string": old_string[:100] + "..." if len(old_string) > 100 else old_string
                    }
                )
            
            # 写入新内容
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # 生成差异报告
            diff = self._generate_diff(file_path, old_content, new_content)
            
            return ToolResult(
                title=os.path.relpath(file_path, os.getcwd()),
                output="文件编辑成功",
                metadata={
                    "file_path": file_path,
                    "diff": diff,
                    "action": "edit",
                    "replace_all": replace_all
                }
            )
            
        except UnicodeDecodeError:
            return ToolResult(
                title=f"编码错误: {os.path.basename(file_path)}",
                output=f"无法解码文件: {file_path}\n文件可能使用了不支持的编码格式",
                metadata={"error": "encoding_error", "file_path": file_path}
            )
        
        except (IOError, OSError) as e:
            return ToolResult(
                title=f"IO错误: {os.path.basename(file_path)}",
                output=f"文件操作失败: {str(e)}",
                metadata={
                    "error": "io_error",
                    "file_path": file_path,
                    "error_message": str(e)
                }
            )
