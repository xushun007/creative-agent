import os
import mimetypes
from typing import Dict, List, Any, Optional
from pathlib import Path
from .base_tool import BaseTool, ToolContext, ToolResult


# 常量配置
DEFAULT_READ_LIMIT = 2000
MAX_LINE_LENGTH = 2000


class ReadTool(BaseTool[Dict[str, Any]]):
    """文件读取工具"""
    
    def __init__(self):
        description = """从本地文件系统读取文件。您可以使用此工具直接访问任何文件。
假设此工具能够读取机器上的所有文件。如果用户提供文件路径，请假设该路径有效。读取不存在的文件是可以的；将返回错误。

用法：
- filePath 参数必须是绝对路径，不是相对路径
- 默认情况下，它从文件开头读取最多 2000 行
- 您可以选择指定行偏移量和限制（对于长文件特别方便），但建议通过不提供这些参数来读取整个文件
- 任何超过 2000 个字符的行都将被截断
- 输出为纯净的文件内容，不包含行号
- 此工具无法读取二进制文件，包括图像
- 您有能力在单个响应中调用多个工具。批量推测性地读取可能有用的多个文件总是更好的
- 如果您读取的文件存在但内容为空，您将收到系统提醒警告而不是文件内容"""
        
        super().__init__("read", description)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "要读取的文件路径"
                },
                "offset": {
                    "type": "number",
                    "description": "开始读取的行号（从0开始）",
                    "minimum": 0
                },
                "limit": {
                    "type": "number", 
                    "description": "要读取的行数（默认为2000）",
                    "minimum": 1,
                    "maximum": 10000,
                    "default": DEFAULT_READ_LIMIT
                }
            },
            "required": ["filePath"]
        }
    
    def _is_image_file(self, file_path: str) -> Optional[str]:
        """检查是否为图像文件"""
        ext = Path(file_path).suffix.lower()
        image_extensions = {
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG', 
            '.png': 'PNG',
            '.gif': 'GIF',
            '.bmp': 'BMP',
            '.webp': 'WebP',
            '.svg': 'SVG',
            '.ico': 'ICO'
        }
        return image_extensions.get(ext)
    
    def _is_binary_file(self, file_path: str) -> bool:
        """检查是否为二进制文件"""
        # 首先检查扩展名
        ext = Path(file_path).suffix.lower()
        binary_extensions = {
            '.zip', '.tar', '.gz', '.exe', '.dll', '.so', '.class', '.jar', 
            '.war', '.7z', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.odt', '.ods', '.odp', '.bin', '.dat', '.obj', '.o', '.a', 
            '.lib', '.wasm', '.pyc', '.pyo', '.pdf'
        }
        
        if ext in binary_extensions:
            return True
        
        # 检查文件内容
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(4096)
                if not chunk:
                    return False
                
                # 检查是否包含空字节
                if b'\x00' in chunk:
                    return True
                
                # 计算非打印字符的比例
                non_printable = 0
                for byte in chunk:
                    if byte < 9 or (13 < byte < 32):
                        non_printable += 1
                
                # 如果超过30%是非打印字符，认为是二进制文件
                return non_printable / len(chunk) > 0.3
                
        except (IOError, OSError):
            return False
    
    def _get_file_suggestions(self, file_path: str) -> List[str]:
        """获取文件建议"""
        try:
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path).lower()
            
            if not os.path.exists(directory):
                return []
            
            suggestions = []
            for entry in os.listdir(directory):
                entry_lower = entry.lower()
                if (filename in entry_lower or entry_lower in filename):
                    suggestions.append(os.path.join(directory, entry))
                    if len(suggestions) >= 3:
                        break
            
            return suggestions
        except (OSError, IOError):
            return []
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行文件读取"""
        file_path = params["filePath"]
        offset = params.get("offset", 0)
        limit = params.get("limit", DEFAULT_READ_LIMIT)
        
        # 转换为绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            suggestions = self._get_file_suggestions(file_path)
            error_msg = f"文件未找到: {file_path}"
            
            if suggestions:
                error_msg += f"\n\n您是否指的是以下文件之一？\n" + "\n".join(suggestions)
            
            return ToolResult(
                title=f"文件未找到: {os.path.basename(file_path)}",
                output=error_msg,
                metadata={
                    "error": "file_not_found",
                    "file_path": file_path,
                    "suggestions": suggestions
                }
            )
        
        # 检查是否为图像文件
        image_type = self._is_image_file(file_path)
        if image_type:
            return ToolResult(
                title=f"无法读取图像文件: {os.path.basename(file_path)}",
                output=f"这是一个 {image_type} 类型的图像文件\n请使用不同的工具来处理图像",
                metadata={
                    "error": "image_file",
                    "file_path": file_path,
                    "image_type": image_type
                }
            )
        
        # 检查是否为二进制文件
        if self._is_binary_file(file_path):
            return ToolResult(
                title=f"无法读取二进制文件: {os.path.basename(file_path)}",
                output=f"无法读取二进制文件: {file_path}",
                metadata={
                    "error": "binary_file",
                    "file_path": file_path
                }
            )
        
        # 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            # 去除行末的换行符
            lines = [line.rstrip('\n\r') for line in lines]
            
            # 应用偏移和限制
            total_lines = len(lines)
            selected_lines = lines[offset:offset + limit]
            
            # 截断过长的行
            truncated_lines = []
            for line in selected_lines:
                if len(line) > MAX_LINE_LENGTH:
                    truncated_lines.append(line[:MAX_LINE_LENGTH] + "...")
                else:
                    truncated_lines.append(line)
            
            # 构建输出（纯净内容，无行号）
            output = "<file>\n"
            output += "\n".join(truncated_lines)
            
            if total_lines > offset + len(selected_lines):
                output += f"\n\n(文件还有更多行。使用 'offset' 参数读取第 {offset + len(selected_lines)} 行之后的内容)"
            
            output += "\n</file>"
            
            # 生成预览（前20行）
            preview_lines = truncated_lines[:20]
            preview = "\n".join(preview_lines)
            
            # 检查空文件
            if total_lines == 0:
                output = "<file>\n(文件为空)\n</file>"
                preview = "(文件为空)"
            
            return ToolResult(
                title=os.path.relpath(file_path, os.getcwd()),
                output=output,
                metadata={
                    "file_path": file_path,
                    "total_lines": total_lines,
                    "lines_read": len(selected_lines),
                    "offset": offset,
                    "limit": limit,
                    "preview": preview
                }
            )
            
        except UnicodeDecodeError:
            return ToolResult(
                title=f"编码错误: {os.path.basename(file_path)}",
                output=f"无法解码文件: {file_path}\n文件可能使用了不支持的编码格式",
                metadata={
                    "error": "encoding_error",
                    "file_path": file_path
                }
            )
        
        except (IOError, OSError) as e:
            return ToolResult(
                title=f"读取错误: {os.path.basename(file_path)}",
                output=f"读取文件时发生错误: {str(e)}",
                metadata={
                    "error": "io_error",
                    "file_path": file_path,
                    "error_message": str(e)
                }
            )


class WriteTool(BaseTool[Dict[str, Any]]):
    """文件写入工具"""
    
    def __init__(self):
        description = """将文件写入本地文件系统。

用法：
- 如果提供的路径已存在文件，此工具将覆盖现有文件
- 如果这是现有文件，您必须首先使用 Read 工具读取文件的内容。如果您没有先读取文件，此工具将失败
- 始终优先编辑代码库中的现有文件。除非明确要求，否则切勿编写新文件
- 切勿主动创建文档文件（*.md）或 README 文件。仅在用户明确要求时创建文档文件
- 仅在用户明确要求时使用表情符号。除非被要求，否则避免将表情符号写入文件"""
        
        super().__init__("write", description)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "要写入的文件的绝对路径（必须是绝对路径，不是相对路径）"
                },
                "content": {
                    "type": "string",
                    "description": "要写入文件的内容"
                }
            },
            "required": ["filePath", "content"]
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行文件写入"""
        file_path = params["filePath"]
        content = params["content"]
        
        # 转换为绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        # 检查文件是否已存在
        file_exists = os.path.exists(file_path)
        
        # 创建目录（如果不存在）
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except (IOError, OSError) as e:
                return ToolResult(
                    title=f"创建目录失败: {os.path.basename(directory)}",
                    output=f"无法创建目录: {directory}\n错误: {str(e)}",
                    metadata={
                        "error": "directory_creation_failed",
                        "directory": directory,
                        "error_message": str(e)
                    }
                )
        
        # 写入文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 获取文件统计信息
            file_stats = os.stat(file_path)
            file_size = file_stats.st_size
            line_count = content.count('\n') + 1 if content else 0
            
            # 构建输出消息
            action = "覆盖" if file_exists else "创建"
            output = f"成功{action}文件: {file_path}\n"
            output += f"文件大小: {file_size} 字节\n"
            output += f"行数: {line_count}"
            
            return ToolResult(
                title=os.path.relpath(file_path, os.getcwd()),
                output=output,
                metadata={
                    "file_path": file_path,
                    "file_exists": file_exists,
                    "file_size": file_size,
                    "line_count": line_count,
                    "action": action
                }
            )
            
        except (IOError, OSError) as e:
            return ToolResult(
                title=f"写入失败: {os.path.basename(file_path)}",
                output=f"写入文件时发生错误: {str(e)}",
                metadata={
                    "error": "io_error",
                    "file_path": file_path,
                    "error_message": str(e)
                }
            )


if __name__ == "__main__":
    ReadTool().execute({
        "filePath": "file_tools.py"
    }, ToolContext())