"""工具执行器"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union

from core.config import Config
from tools.sandbox import SandboxExecutor
from tools.patch_applier import PatchApplier


class ToolExecutor:
    """工具执行器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.sandbox = SandboxExecutor(config)
        self.patch_applier = PatchApplier(config)
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Union[str, Dict[str, Any]]:
        """执行工具调用"""
        
        if tool_name == "execute_command":
            return await self._execute_command(arguments)
        elif tool_name == "read_file":
            return await self._read_file(arguments)
        elif tool_name == "write_file":
            return await self._write_file(arguments)
        elif tool_name == "apply_patch":
            return await self._apply_patch(arguments)
        else:
            return f"未知工具: {tool_name}"
    
    async def _execute_command(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行shell命令"""
        command = arguments.get("command", "")
        cwd = arguments.get("cwd")
        
        if cwd:
            cwd = Path(cwd)
        
        if not command:
            return {
                "success": False,
                "error": "命令不能为空"
            }
        
        # 使用沙箱执行命令
        result = await self.sandbox.execute_command(command, cwd)
        
        return {
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
            "duration": result.get("duration", 0)
        }
    
    async def _read_file(self, arguments: Dict[str, Any]) -> str:
        """读取文件内容"""
        file_path = arguments.get("file_path", "")
        
        if not file_path:
            return "错误: 文件路径不能为空"
        
        try:
            path = Path(file_path)
            
            # 检查文件是否存在
            if not path.exists():
                return f"错误: 文件不存在: {file_path}"
            
            # 检查是否是文件
            if not path.is_file():
                return f"错误: 路径不是文件: {file_path}"
            
            # 检查文件大小（限制为1MB）
            if path.stat().st_size > 1024 * 1024:
                return f"错误: 文件过大 (>1MB): {file_path}"
            
            # 读取文件内容
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            return f"文件内容 ({file_path}):\n```\n{content}\n```"
            
        except PermissionError:
            return f"错误: 没有读取文件的权限: {file_path}"
        except Exception as e:
            return f"错误: 读取文件时出错: {str(e)}"
    
    async def _write_file(self, arguments: Dict[str, Any]) -> str:
        """写入文件内容"""
        file_path = arguments.get("file_path", "")
        content = arguments.get("content", "")
        
        if not file_path:
            return "错误: 文件路径不能为空"
        
        try:
            path = Path(file_path)
            
            # 检查路径是否可写
            if not self.sandbox.is_path_writable(path):
                return f"错误: 没有写入权限: {file_path}"
            
            # 创建目录（如果不存在）
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return f"成功写入文件: {file_path} ({len(content)} 字符)"
            
        except PermissionError:
            return f"错误: 没有写入文件的权限: {file_path}"
        except Exception as e:
            return f"错误: 写入文件时出错: {str(e)}"
    
    async def _apply_patch(self, arguments: Dict[str, Any]) -> str:
        """应用代码补丁"""
        file_path = arguments.get("file_path", "")
        patch = arguments.get("patch", "")
        
        if not file_path:
            return "错误: 文件路径不能为空"
        
        if not patch:
            return "错误: 补丁内容不能为空"
        
        try:
            path = Path(file_path)
            
            # 检查路径是否可写
            if not self.sandbox.is_path_writable(path):
                return f"错误: 没有写入权限: {file_path}"
            
            # 应用补丁
            result = await self.patch_applier.apply_patch(path, patch)
            
            if result["success"]:
                return f"成功应用补丁到 {file_path}: {result['message']}"
            else:
                return f"应用补丁失败: {result['error']}"
                
        except Exception as e:
            return f"错误: 应用补丁时出错: {str(e)}"
    
    def format_command_output(self, result: Dict[str, Any]) -> str:
        """格式化命令输出"""
        if result["success"]:
            output = f"命令执行成功 (退出码: {result['exit_code']})"
            
            if result["stdout"]:
                output += f"\n\n标准输出:\n```\n{result['stdout']}\n```"
            
            if result["stderr"]:
                output += f"\n\n标准错误:\n```\n{result['stderr']}\n```"
            
            duration = result.get("duration", 0)
            if duration > 0:
                output += f"\n\n执行时间: {duration:.2f}秒"
        else:
            output = f"命令执行失败 (退出码: {result['exit_code']})"
            
            if result["stderr"]:
                output += f"\n\n错误信息:\n```\n{result['stderr']}\n```"
            
            if result["stdout"]:
                output += f"\n\n标准输出:\n```\n{result['stdout']}\n```"
        
        return output
    
    async def list_files(self, directory: Path, pattern: str = "*") -> str:
        """列出目录中的文件"""
        try:
            if not directory.exists():
                return f"错误: 目录不存在: {directory}"
            
            if not directory.is_dir():
                return f"错误: 路径不是目录: {directory}"
            
            files = []
            for item in directory.glob(pattern):
                if item.is_file():
                    size = item.stat().st_size
                    files.append(f"📄 {item.name} ({size} bytes)")
                elif item.is_dir():
                    files.append(f"📁 {item.name}/")
            
            if not files:
                return f"目录为空或没有匹配的文件: {directory}"
            
            return f"目录内容 ({directory}):\n" + "\n".join(sorted(files))
            
        except PermissionError:
            return f"错误: 没有访问目录的权限: {directory}"
        except Exception as e:
            return f"错误: 列出文件时出错: {str(e)}"
    
    async def get_file_info(self, file_path: Path) -> str:
        """获取文件信息"""
        try:
            if not file_path.exists():
                return f"错误: 文件不存在: {file_path}"
            
            stat = file_path.stat()
            
            info = f"文件信息 ({file_path}):\n"
            info += f"类型: {'文件' if file_path.is_file() else '目录'}\n"
            info += f"大小: {stat.st_size} bytes\n"
            
            import time
            info += f"修改时间: {time.ctime(stat.st_mtime)}\n"
            info += f"创建时间: {time.ctime(stat.st_ctime)}\n"
            
            # 获取权限信息
            import stat as stat_module
            mode = stat.st_mode
            permissions = stat_module.filemode(mode)
            info += f"权限: {permissions}\n"
            
            return info
            
        except Exception as e:
            return f"错误: 获取文件信息时出错: {str(e)}"
