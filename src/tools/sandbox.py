"""沙箱执行器"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import shlex
import platform

from core.protocol import SandboxPolicy
from core.config import Config


class SandboxExecutor:
    """沙箱执行器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.sandbox_policy = SandboxPolicy(config.sandbox_policy)
        self.cwd = config.cwd
        
        # 临时目录用于沙箱
        self.temp_dir = Path(tempfile.mkdtemp(prefix="codex_sandbox_"))
    
    def __del__(self):
        """清理临时目录"""
        import shutil
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def is_command_allowed(self, command: str) -> Tuple[bool, Optional[str]]:
        """检查命令是否被允许"""
        if self.sandbox_policy == SandboxPolicy.DANGER_FULL_ACCESS:
            return True, None
        
        # 危险命令黑名单
        dangerous_commands = {
            "rm -rf /": "禁止删除根目录",
            "format": "禁止格式化磁盘", 
            "fdisk": "禁止磁盘分区操作",
            "mkfs": "禁止创建文件系统",
            "dd if=/dev/zero": "禁止清零磁盘",
            ":(){ :|:& };:": "禁止fork炸弹",
            "chmod 777": "禁止设置777权限",
            "chown root": "禁止更改为root所有者"
        }
        
        command_lower = command.lower()
        for dangerous, reason in dangerous_commands.items():
            if dangerous in command_lower:
                return False, reason
        
        # 网络命令检查
        if self.sandbox_policy == SandboxPolicy.READ_ONLY:
            network_commands = ["curl", "wget", "ssh", "scp", "rsync", "git push"]
            for net_cmd in network_commands:
                if net_cmd in command_lower:
                    return False, f"只读模式下禁止网络操作: {net_cmd}"
        
        return True, None
    
    def get_writable_paths(self) -> List[Path]:
        """获取可写路径列表"""
        writable_paths = []
        
        if self.sandbox_policy == SandboxPolicy.DANGER_FULL_ACCESS:
            # 完全访问模式，返回根目录
            return [Path("/")]
        elif self.sandbox_policy == SandboxPolicy.WORKSPACE_WRITE:
            # 工作区写入模式
            writable_paths.append(self.cwd)
            writable_paths.append(self.temp_dir)
            
            # 添加系统临时目录
            if platform.system() == "Windows":
                writable_paths.append(Path(os.environ.get("TEMP", "C:\\Temp")))
            else:
                writable_paths.append(Path("/tmp"))
                if "TMPDIR" in os.environ:
                    writable_paths.append(Path(os.environ["TMPDIR"]))
        
        return writable_paths
    
    def is_path_writable(self, path: Path) -> bool:
        """检查路径是否可写"""
        if self.sandbox_policy == SandboxPolicy.READ_ONLY:
            return False
        elif self.sandbox_policy == SandboxPolicy.DANGER_FULL_ACCESS:
            return True
        
        path = path.resolve()
        writable_paths = self.get_writable_paths()
        
        for writable in writable_paths:
            try:
                writable = writable.resolve()
                if path == writable or path.is_relative_to(writable):
                    # 检查是否是受保护的子目录（如.git）
                    if any(part.startswith('.git') for part in path.parts):
                        return False
                    return True
            except (OSError, ValueError):
                continue
        
        return False
    
    async def execute_command(
        self, 
        command: str, 
        cwd: Optional[Path] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """在沙箱中执行命令"""
        
        # 检查命令是否被允许
        allowed, reason = self.is_command_allowed(command)
        if not allowed:
            return {
                "success": False,
                "stdout": "",
                "stderr": reason,
                "exit_code": 1,
                "duration": 0
            }
        
        # 设置工作目录
        exec_cwd = cwd or self.cwd
        
        # 准备环境变量
        env = os.environ.copy()
        env["CODEX_SANDBOX"] = "python"
        
        if self.sandbox_policy != SandboxPolicy.DANGER_FULL_ACCESS:
            # 限制网络访问
            env["CODEX_SANDBOX_NETWORK_DISABLED"] = "1"
        
        try:
            import time
            start_time = time.time()
            
            # 执行命令
            if platform.system() == "Windows":
                result = await self._execute_windows(command, exec_cwd, env, timeout)
            else:
                result = await self._execute_unix(command, exec_cwd, env, timeout)
            
            duration = time.time() - start_time
            result["duration"] = duration
            
            return result
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"命令执行超时 ({timeout}秒)",
                "exit_code": 124,
                "duration": timeout
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"执行命令时出错: {str(e)}",
                "exit_code": 1,
                "duration": 0
            }
    
    async def _execute_unix(
        self, 
        command: str, 
        cwd: Path, 
        env: Dict[str, str], 
        timeout: int
    ) -> Dict[str, Any]:
        """在Unix系统中执行命令"""
        
        # 使用asyncio.subprocess执行命令
        import asyncio
        
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True  # 创建新的进程组
        )
        
        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            
            return {
                "success": process.returncode == 0,
                "stdout": stdout_data.decode('utf-8', errors='replace'),
                "stderr": stderr_data.decode('utf-8', errors='replace'),
                "exit_code": process.returncode
            }
        except asyncio.TimeoutError:
            # 终止进程组
            try:
                import signal
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                await asyncio.sleep(1)
                if process.returncode is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except:
                pass
            raise subprocess.TimeoutExpired(command, timeout)
    
    async def _execute_windows(
        self, 
        command: str, 
        cwd: Path, 
        env: Dict[str, str], 
        timeout: int
    ) -> Dict[str, Any]:
        """在Windows系统中执行命令"""
        
        import asyncio
        
        # Windows下使用cmd执行
        full_command = f'cmd /c "{command}"'
        
        process = await asyncio.create_subprocess_shell(
            full_command,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            
            return {
                "success": process.returncode == 0,
                "stdout": stdout_data.decode('gbk', errors='replace'),
                "stderr": stderr_data.decode('gbk', errors='replace'),
                "exit_code": process.returncode
            }
        except asyncio.TimeoutError:
            process.terminate()
            await asyncio.sleep(1)
            if process.returncode is None:
                process.kill()
            raise subprocess.TimeoutExpired(command, timeout)
    
    def create_restricted_env(self) -> Dict[str, str]:
        """创建受限的环境变量"""
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.temp_dir),
            "USER": "codex_user",
            "SHELL": "/bin/bash",
            "LANG": "en_US.UTF-8",
            "TERM": "xterm"
        }
        
        # 添加Python相关环境变量
        if "PYTHONPATH" in os.environ:
            env["PYTHONPATH"] = os.environ["PYTHONPATH"]
        
        return env
