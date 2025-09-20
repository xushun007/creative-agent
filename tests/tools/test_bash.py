#!/usr/bin/env python3
"""BashTool 单元测试"""

import unittest
import asyncio
import os
import tempfile
import shutil
from unittest.mock import patch, AsyncMock

# 添加src目录到路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from tools.bash import BashTool
    from tools.base_tool import ToolContext
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.bash import BashTool
    from tools.base_tool import ToolContext


class TestBashTool(unittest.TestCase):
    """BashTool 测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.bash_tool = BashTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
        
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
    
    def tearDown(self):
        """测试后清理"""
        # 恢复原始工作目录
        os.chdir(self.original_cwd)
        # 清理临时目录
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_tool_basic_properties(self):
        """测试工具基本属性"""
        self.assertEqual(self.bash_tool.name, "bash")
        self.assertGreater(len(self.bash_tool.description), 0)
        self.assertIn("bash命令", self.bash_tool.description)
    
    def test_parameters_schema(self):
        """测试参数模式"""
        schema = self.bash_tool.get_parameters_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("command", schema["properties"])
        self.assertIn("timeout", schema["properties"])
        self.assertIn("description", schema["properties"])
        self.assertIn("command", schema["required"])
        
        # 验证timeout参数限制
        timeout_schema = schema["properties"]["timeout"]
        self.assertEqual(timeout_schema["minimum"], 1)
        self.assertEqual(timeout_schema["maximum"], 600)
    
    def test_simple_command_execution(self):
        """测试简单命令执行"""
        async def run_test():
            params = {
                "command": "echo 'Hello World'",
                "description": "输出Hello World"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            self.assertEqual(result.title, "echo 'Hello World'")
            self.assertIn("Hello World", result.output)
            self.assertEqual(result.metadata["exit_code"], 0)
            self.assertEqual(result.metadata["command"], "echo 'Hello World'")
            self.assertEqual(result.metadata["description"], "输出Hello World")
        
        asyncio.run(run_test())
    
    def test_command_with_exit_code(self):
        """测试带退出码的命令"""
        async def run_test():
            params = {
                "command": "exit 42",
                "description": "退出码42"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            self.assertIn("(退出码: 42)", result.title)
            self.assertEqual(result.metadata["exit_code"], 42)
        
        asyncio.run(run_test())
    
    def test_command_timeout(self):
        """测试命令超时"""
        async def run_test():
            params = {
                "command": "sleep 5",
                "timeout": 1,  # 1秒超时
                "description": "睡眠5秒"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            self.assertIn("超时", result.output)
            self.assertEqual(result.metadata["exit_code"], 124)  # 超时退出码
        
        asyncio.run(run_test())
    
    def test_dangerous_command_blocked(self):
        """测试危险命令被阻止"""
        async def run_test():
            dangerous_commands = [
                "rm -rf /",
                "rm -rf /*",
                "format",
                ":(){ :|:& };:"  # fork bomb
            ]
            
            for cmd in dangerous_commands:
                params = {
                    "command": cmd,
                    "description": "危险命令测试"
                }
                
                result = await self.bash_tool.execute(params, self.context)
                
                self.assertIn("命令被拒绝", result.title)
                self.assertIn("安全检查失败", result.output)
                self.assertEqual(result.metadata["exit_code"], 1)
        
        asyncio.run(run_test())
    
    def test_file_operations(self):
        """测试文件操作"""
        async def run_test():
            # 切换到测试目录
            os.chdir(self.test_dir)
            
            # 创建文件
            params1 = {
                "command": "echo 'test content' > test_file.txt",
                "description": "创建测试文件"
            }
            
            result1 = await self.bash_tool.execute(params1, self.context)
            self.assertEqual(result1.metadata["exit_code"], 0)
            
            # 读取文件
            params2 = {
                "command": "cat test_file.txt",
                "description": "读取测试文件"
            }
            
            result2 = await self.bash_tool.execute(params2, self.context)
            self.assertEqual(result2.metadata["exit_code"], 0)
            self.assertIn("test content", result2.output)
            
            # 删除文件
            params3 = {
                "command": "rm test_file.txt",
                "description": "删除测试文件"
            }
            
            result3 = await self.bash_tool.execute(params3, self.context)
            self.assertEqual(result3.metadata["exit_code"], 0)
        
        asyncio.run(run_test())
    
    def test_multiline_output(self):
        """测试多行输出"""
        async def run_test():
            params = {
                "command": "echo -e 'line1\\nline2\\nline3'",
                "description": "多行输出"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            self.assertEqual(result.metadata["exit_code"], 0)
            self.assertIn("line1", result.output)
            self.assertIn("line2", result.output)
            self.assertIn("line3", result.output)
        
        asyncio.run(run_test())
    
    def test_command_with_special_characters(self):
        """测试包含特殊字符的命令"""
        async def run_test():
            params = {
                "command": "echo 'Hello & World | Test'",
                "description": "特殊字符测试"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            self.assertEqual(result.metadata["exit_code"], 0)
            self.assertIn("Hello & World | Test", result.output)
        
        asyncio.run(run_test())
    
    def test_environment_variables(self):
        """测试环境变量"""
        async def run_test():
            params = {
                "command": "echo $HOME",
                "description": "显示HOME环境变量"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            self.assertEqual(result.metadata["exit_code"], 0)
            self.assertGreater(len(result.output.strip()), 0)
        
        asyncio.run(run_test())
    
    def test_command_chaining(self):
        """测试命令链"""
        async def run_test():
            params = {
                "command": "echo 'first' && echo 'second'",
                "description": "命令链测试"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            self.assertEqual(result.metadata["exit_code"], 0)
            self.assertIn("first", result.output)
            self.assertIn("second", result.output)
        
        asyncio.run(run_test())
    
    def test_stderr_capture(self):
        """测试stderr捕获"""
        async def run_test():
            params = {
                "command": "echo 'error message' >&2",
                "description": "stderr测试"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            # stderr应该被合并到stdout中
            self.assertIn("error message", result.output)
        
        asyncio.run(run_test())
    
    def test_working_directory(self):
        """测试工作目录"""
        async def run_test():
            # 在测试目录中创建子目录
            subdir = os.path.join(self.test_dir, "subdir")
            os.makedirs(subdir)
            
            params = {
                "command": f"cd {subdir} && pwd",
                "description": "工作目录测试"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            self.assertEqual(result.metadata["exit_code"], 0)
            self.assertIn("subdir", result.output)
        
        asyncio.run(run_test())
    
    def test_large_output_truncation(self):
        """测试大输出截断"""
        async def run_test():
            # 生成大量输出（超过30000字符）
            params = {
                "command": "python3 -c 'print(\"x\" * 35000)'",
                "description": "大输出测试"
            }
            
            result = await self.bash_tool.execute(params, self.context)
            
            # 检查输出是否被截断
            self.assertLessEqual(len(result.output), 30100)  # 允许截断消息的额外长度
            if len(result.output) >= 30000:
                self.assertIn("输出因长度限制被截断", result.output)
        
        asyncio.run(run_test())
    
    def test_command_validation(self):
        """测试命令验证"""
        # 测试_validate_command方法
        with self.assertRaises(ValueError):
            self.bash_tool._validate_command("rm -rf /")
        
        with self.assertRaises(ValueError):
            self.bash_tool._validate_command("format")
        
        # 正常命令应该不抛出异常
        try:
            self.bash_tool._validate_command("echo hello")
            self.bash_tool._validate_command("ls -la")
        except ValueError:
            self.fail("正常命令不应该被阻止")
    
    def test_tool_to_dict(self):
        """测试工具转换为字典"""
        tool_dict = self.bash_tool.to_dict()
        
        self.assertEqual(tool_dict["name"], "bash")
        self.assertIn("description", tool_dict)
        self.assertIn("parameters", tool_dict)
        
        # 验证参数结构
        params = tool_dict["parameters"]
        self.assertIn("command", params["properties"])
        self.assertIn("timeout", params["properties"])
        self.assertIn("description", params["properties"])


if __name__ == "__main__":
    unittest.main()
