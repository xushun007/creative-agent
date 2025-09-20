import asyncio
import subprocess
import os
import shlex
import signal
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from .base_tool import BaseTool, ToolContext, ToolResult


# 常量配置
MAX_OUTPUT_LENGTH = 30000
DEFAULT_TIMEOUT = 60  # 60秒
MAX_TIMEOUT = 600     # 10分钟


@dataclass
class BashParams:
    """Bash工具参数"""
    command: str
    timeout: Optional[int] = None
    description: Optional[str] = None


class BashTool(BaseTool[Dict[str, Any]]):
    """Bash命令执行工具"""
    
    def __init__(self):
        description = """在持久shell会话中执行给定的bash命令，具有可选的超时设置，确保正确的处理和安全措施。

执行命令前，请遵循以下步骤：

1. 目录验证：
   - 如果命令将创建新目录或文件，首先使用LS工具验证父目录是否存在且位置正确
   - 例如，在运行"mkdir foo/bar"之前，首先使用LS检查"foo"是否存在且是预期的父目录

2. 命令执行：
   - 始终用双引号包围包含空格的文件路径（例如：cd "path with spaces/file.txt"）
   - 正确引用示例：
     - cd "/Users/name/My Documents" (正确)
     - cd /Users/name/My Documents (错误 - 会失败)
     - python "/path/with spaces/script.py" (正确)
     - python /path/with spaces/script.py (错误 - 会失败)
   - 确保正确引用后，执行命令
   - 捕获命令的输出

使用说明：
  - command参数是必需的
  - 您可以指定可选的超时时间（毫秒）（最多600000ms/10分钟）。如果未指定，命令将在60000ms（1分钟）后超时
  - 如果您能写出这个命令功能的清晰、简洁描述（5-10个字），会很有帮助
  - 如果输出超过30000个字符，输出将在返回给您之前被截断
  - 非常重要：您必须避免使用搜索命令如`find`和`grep`。请使用Grep、Glob或Task进行搜索。您必须避免读取工具如`cat`、`head`、`tail`和`ls`，请使用Read和LS读取文件
  - 如果您仍需要运行`grep`，请停止。始终首先使用ripgrep的`rg`（或/usr/bin/rg），所有opencode用户都预装了它
  - 发出多个命令时，使用';'或'&&'操作符分隔它们。不要使用换行符（在引用字符串中换行符是可以的）
  - 通过使用绝对路径并避免使用`cd`来尝试在整个会话中维护您的当前工作目录。如果用户明确要求，您可以使用`cd`

安全注意事项：
  - 命令在受限环境中执行
  - 某些危险命令可能被阻止
  - 输出长度有限制以防止过度消耗资源
  - 超时设置防止长时间运行的进程"""
        
        super().__init__("bash", description)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令"
                },
                "timeout": {
                    "type": "number",
                    "description": "可选的超时时间（秒）",
                    "minimum": 1,
                    "maximum": MAX_TIMEOUT,
                    "default": DEFAULT_TIMEOUT
                },
                "description": {
                    "type": "string",
                    "description": "命令功能的清晰、简洁描述（5-10个字）。示例：\n输入: ls\n输出: 列出当前目录中的文件\n\n输入: git status\n输出: 显示工作树状态\n\n输入: npm install\n输出: 安装包依赖\n\n输入: mkdir foo\n输出: 创建目录'foo'"
                }
            },
            "required": ["command"]
        }
    
    def _validate_command(self, command: str) -> None:
        """验证命令安全性"""
        # 基本的安全检查
        dangerous_patterns = [
            'rm -rf /',
            'rm -rf /*',
            'format',
            'fdisk',
            'mkfs',
            ':(){ :|:& };:',  # fork bomb
            'chmod 777 /',
            'chown root /',
        ]
        
        command_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                raise ValueError(f"命令包含危险模式: {pattern}")
    
    def _parse_command_args(self, command: str) -> List[str]:
        """解析命令参数，处理引号和转义"""
        try:
            return shlex.split(command)
        except ValueError as e:
            # 如果解析失败，回退到简单的空格分割
            return command.split()
    
    async def _execute_command(self, command: str, timeout: int, cwd: Optional[str] = None) -> Tuple[str, int]:
        """异步执行命令"""
        # 设置环境变量
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'  # 确保Python输出不被缓冲
        
        # 创建进程
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # 合并stderr到stdout
            cwd=cwd or os.getcwd(),
            env=env,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # 创建新的进程组
        )
        
        output = ""
        
        try:
            # 等待进程完成，带超时
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            if stdout:
                output = stdout.decode('utf-8', errors='replace')
            
            exit_code = process.returncode or 0
            
        except asyncio.TimeoutError:
            # 超时处理
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                
                # 等待进程结束
                await asyncio.wait_for(process.wait(), timeout=5)
            except (ProcessLookupError, asyncio.TimeoutError):
                # 如果进程已经结束或强制终止失败，尝试SIGKILL
                try:
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass
            
            output += f"\n\n[命令执行超时 ({timeout}秒) 并被终止]"
            exit_code = 124  # 超时退出码
        
        except Exception as e:
            output += f"\n\n[执行错误: {str(e)}]"
            exit_code = 1
        
        return output, exit_code
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行bash命令"""
        # 解析参数
        command = params["command"]
        timeout = min(params.get("timeout", DEFAULT_TIMEOUT), MAX_TIMEOUT)
        description = params.get("description", "")
        
        # 验证命令安全性
        try:
            self._validate_command(command)
        except ValueError as e:
            return ToolResult(
                title=f"命令被拒绝: {command}",
                output=f"安全检查失败: {str(e)}",
                metadata={
                    "command": command,
                    "exit_code": 1,
                    "error": str(e),
                    "description": description
                }
            )
        
        # 执行命令
        try:
            output, exit_code = await self._execute_command(command, timeout)
            
            # 截断过长的输出
            if len(output) > MAX_OUTPUT_LENGTH:
                original_length = len(output)
                output = output[:MAX_OUTPUT_LENGTH]
                output += f"\n\n(输出因长度限制被截断，原始长度: {original_length} 字符)"
            
            # 构建结果
            title = command
            if exit_code != 0:
                title += f" (退出码: {exit_code})"
            
            return ToolResult(
                title=title,
                output=output,
                metadata={
                    "command": command,
                    "exit_code": exit_code,
                    "description": description,
                    "timeout": timeout
                }
            )
            
        except Exception as e:
            return ToolResult(
                title=f"执行失败: {command}",
                output=f"执行错误: {str(e)}",
                metadata={
                    "command": command,
                    "exit_code": 1,
                    "error": str(e),
                    "description": description
                }
            )
