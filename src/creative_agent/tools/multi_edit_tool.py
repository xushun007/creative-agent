import os
from typing import Dict, List, Any, Optional
from .base_tool import BaseTool, ToolContext, ToolResult
from .edit_tool import EditTool


class MultiEditTool(BaseTool[Dict[str, Any]]):
    """多重编辑工具 - 在单个操作中对单个文件执行多次编辑"""
    
    def __init__(self):
        description = """多重编辑工具 - 这是一个在单个操作中对单个文件进行多次编辑的工具。它建立在EditTool之上，允许您高效地执行多个查找和替换操作。当您需要对同一文件进行多次编辑时，优先使用此工具而不是EditTool。

使用此工具之前：
- 使用Read工具了解文件的内容和上下文
- 验证目录路径是否正确

要进行多个文件编辑，请提供以下内容：
- filePath: 要修改的文件的绝对路径（必须是绝对路径，不是相对路径）
- edits: 要执行的编辑操作数组，其中每个编辑包含：
  - oldString: 要替换的文本（必须与文件内容完全匹配，包括所有空白和缩进）
  - newString: 替换oldString的编辑文本
  - replaceAll: 替换oldString的所有出现。此参数是可选的，默认为false

重要说明：
- 所有编辑按照提供的顺序依次应用
- 每个编辑在前一个编辑的结果上操作
- 所有编辑必须有效才能成功执行操作 - 如果任何编辑失败，则不会应用任何编辑
- 此工具非常适合需要对同一文件的不同部分进行多次更改的情况

关键要求：
1. 所有编辑都遵循与单个编辑工具相同的要求
2. 编辑是原子的 - 要么全部成功，要么全部不应用
3. 仔细规划您的编辑以避免顺序操作之间的冲突

警告：
- 如果edits.oldString与文件内容不完全匹配（包括空白），工具将失败
- 如果edits.oldString和edits.newString相同，工具将失败
- 由于编辑是按顺序应用的，请确保较早的编辑不会影响较晚编辑试图查找的文本

进行编辑时：
- 确保所有编辑都产生惯用的、正确的代码
- 不要让代码处于破损状态
- 使用replaceAll在整个文件中替换和重命名字符串。例如，如果您想重命名变量，此参数很有用

如果您想创建新文件：
- 使用新文件路径，如有需要包括目录名
- 第一次编辑：空的oldString和新文件的内容作为newString
- 后续编辑：对创建的内容进行正常的编辑操作"""
        
        super().__init__("multiedit", description)
        self.edit_tool = EditTool()
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "要修改的文件的绝对路径"
                },
                "edits": {
                    "type": "array",
                    "description": "要在文件上按顺序执行的编辑操作数组",
                    "items": {
                        "type": "object",
                        "properties": {
                            "oldString": {
                                "type": "string",
                                "description": "要替换的文本"
                            },
                            "newString": {
                                "type": "string",
                                "description": "要替换为的文本"
                            },
                            "replaceAll": {
                                "type": "boolean",
                                "description": "替换oldString的所有出现（默认为false）",
                                "default": False
                            }
                        },
                        "required": ["oldString", "newString"],
                        "additionalProperties": False
                    },
                    "minItems": 1
                }
            },
            "required": ["filePath", "edits"],
            "additionalProperties": False
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行多重文件编辑"""
        file_path = params.get("filePath")
        edits = params.get("edits")
        
        # 验证参数
        if not file_path:
            return ToolResult(
                title="错误: 缺少文件路径",
                output="filePath 参数是必需的",
                metadata={"error": "missing_file_path"}
            )
        
        if not edits:
            return ToolResult(
                title="错误: 缺少编辑操作",
                output="edits 参数是必需的且不能为空",
                metadata={"error": "missing_edits"}
            )
        
        # 转换为绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        # 验证每个编辑操作
        for i, edit in enumerate(edits):
            if not isinstance(edit, dict):
                return ToolResult(
                    title=f"错误: 编辑操作 {i + 1} 格式无效",
                    output=f"编辑操作 {i + 1} 必须是一个对象",
                    metadata={"error": "invalid_edit_format", "edit_index": i}
                )
            
            if "oldString" not in edit or "newString" not in edit:
                return ToolResult(
                    title=f"错误: 编辑操作 {i + 1} 缺少必需字段",
                    output=f"编辑操作 {i + 1} 必须包含 oldString 和 newString",
                    metadata={"error": "missing_edit_fields", "edit_index": i}
                )
            
            if edit["oldString"] == edit["newString"]:
                return ToolResult(
                    title=f"错误: 编辑操作 {i + 1} 字符串相同",
                    output=f"编辑操作 {i + 1} 的 oldString 和 newString 必须不同",
                    metadata={"error": "identical_strings", "edit_index": i}
                )
        
        # 存储结果
        results = []
        failed_edit_index = None
        
        try:
            # 按顺序执行每个编辑操作
            for i, edit in enumerate(edits):
                edit_params = {
                    "filePath": file_path,
                    "oldString": edit["oldString"],
                    "newString": edit["newString"],
                    "replaceAll": edit.get("replaceAll", False)
                }
                
                result = await self.edit_tool.execute(edit_params, context)
                results.append(result)
                
                # 如果编辑失败，停止处理并记录失败的编辑索引
                if result.metadata and result.metadata.get("error"):
                    failed_edit_index = i
                    break
            
            # 如果有编辑失败，返回失败信息
            if failed_edit_index is not None:
                failed_result = results[failed_edit_index]
                return ToolResult(
                    title=f"多重编辑失败: {os.path.basename(file_path)}",
                    output=f"编辑操作 {failed_edit_index + 1} 失败: {failed_result.output}",
                    metadata={
                        "error": "multiedit_failed",
                        "file_path": file_path,
                        "failed_edit_index": failed_edit_index,
                        "total_edits": len(edits),
                        "completed_edits": failed_edit_index,
                        "results": [r.metadata for r in results]
                    }
                )
            
            # 所有编辑成功
            successful_edits = len(results)
            last_result = results[-1] if results else None
            
            return ToolResult(
                title=os.path.relpath(file_path, os.getcwd()),
                output=f"多重编辑成功完成 - {successful_edits} 个编辑操作已应用",
                metadata={
                    "file_path": file_path,
                    "total_edits": len(edits),
                    "successful_edits": successful_edits,
                    "action": "multiedit",
                    "results": [r.metadata for r in results],
                    "final_diff": last_result.metadata.get("diff") if last_result and last_result.metadata else None
                }
            )
        
        except Exception as e:
            return ToolResult(
                title=f"多重编辑错误: {os.path.basename(file_path)}",
                output=f"执行多重编辑时发生错误: {str(e)}",
                metadata={
                    "error": "multiedit_exception",
                    "file_path": file_path,
                    "error_message": str(e),
                    "completed_edits": len(results),
                    "total_edits": len(edits)
                }
            )
