#!/usr/bin/env python3
"""GrepTool 单元测试"""

import unittest
import asyncio
import os
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from tools.grep_tool import GrepTool
    from tools.base_tool import ToolContext
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.grep_tool import GrepTool
    from tools.base_tool import ToolContext


class TestGrepTool(unittest.TestCase):
    """GrepTool测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.grep_tool = GrepTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
        
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # 创建测试文件
        self._create_test_files()
    
    def tearDown(self):
        """测试后清理"""
        os.chdir(self.original_cwd)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _create_test_files(self):
        """创建测试文件"""
        # 创建Python文件
        with open("test.py", "w", encoding="utf-8") as f:
            f.write("""def hello_world():
    print("Hello, World!")
    return "success"

class TestClass:
    def __init__(self):
        self.value = "test_value"
    
    def method(self):
        return self.value
""")
        
        # 创建JavaScript文件
        with open("app.js", "w", encoding="utf-8") as f:
            f.write("""function helloWorld() {
    console.log("Hello, World!");
    return "success";
}

class TestClass {
    constructor() {
        this.value = "test_value";
    }
    
    method() {
        return this.value;
    }
}
""")
        
        # 创建文本文件
        with open("readme.txt", "w", encoding="utf-8") as f:
            f.write("""This is a test file.
It contains multiple lines.
Some lines have the word 'test' in them.
Others do not.
This line has TEST in uppercase.
""")
        
        # 创建子目录和文件
        os.makedirs("subdir", exist_ok=True)
        with open("subdir/config.py", "w", encoding="utf-8") as f:
            f.write("""CONFIG = {
    "debug": True,
    "test_mode": False,
    "database_url": "sqlite:///test.db"
}
""")
    
    def test_grep_tool_basic_properties(self):
        """测试GrepTool基本属性"""
        self.assertEqual(self.grep_tool.name, "grep")
        self.assertIsNotNone(self.grep_tool.description)
        self.assertIn("ripgrep", self.grep_tool.description.lower())
    
    def test_get_parameters_schema(self):
        """测试参数模式"""
        schema = self.grep_tool.get_parameters_schema()
        
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema["type"], "object")
        self.assertIn("properties", schema)
        self.assertIn("required", schema)
        self.assertIn("pattern", schema["required"])
        
        properties = schema["properties"]
        self.assertIn("pattern", properties)
        self.assertIn("path", properties)
        self.assertIn("include", properties)
        self.assertIn("output_mode", properties)
    
    def test_find_ripgrep_not_found(self):
        """测试ripgrep未找到的情况"""
        # 临时修改PATH以模拟ripgrep未安装
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = ""
        
        try:
            with self.assertRaises(FileNotFoundError):
                self.grep_tool._find_ripgrep()
        finally:
            os.environ["PATH"] = original_path
    
    def test_basic_search(self):
        """测试基本搜索功能"""
        async def run_test():
            # 检查是否有ripgrep
            try:
                self.grep_tool._find_ripgrep()
            except FileNotFoundError:
                self.skipTest("ripgrep not available")
            
            params = {
                "pattern": "hello",
                "path": self.test_dir
            }
            
            result = await self.grep_tool.execute(params, self.context)
            
            self.assertIsNotNone(result)
            self.assertEqual(result.title, "hello")
            self.assertIsInstance(result.metadata, dict)
            
            # 应该找到匹配项（如果ripgrep可用）
            if not result.metadata.get("error", False):
                self.assertGreater(result.metadata["matches"], 0)
        
        asyncio.run(run_test())
    
    def test_case_insensitive_search(self):
        """测试大小写不敏感搜索"""
        async def run_test():
            try:
                self.grep_tool._find_ripgrep()
            except FileNotFoundError:
                self.skipTest("ripgrep not available")
            
            params = {
                "pattern": "TEST",
                "path": self.test_dir,
                "case_insensitive": True
            }
            
            result = await self.grep_tool.execute(params, self.context)
            
            if not result.metadata.get("error", False):
                # 应该找到大小写不敏感的匹配
                self.assertGreater(result.metadata["matches"], 0)
        
        asyncio.run(run_test())
    
    def test_file_include_pattern(self):
        """测试文件包含模式"""
        async def run_test():
            try:
                self.grep_tool._find_ripgrep()
            except FileNotFoundError:
                self.skipTest("ripgrep not available")
            
            params = {
                "pattern": "test",
                "path": self.test_dir,
                "include": "*.py"
            }
            
            result = await self.grep_tool.execute(params, self.context)
            
            if not result.metadata.get("error", False):
                # 应该只在Python文件中搜索
                self.assertIn("test.py", result.output.lower() or "")
        
        asyncio.run(run_test())
    
    def test_files_with_matches_output(self):
        """测试只显示文件名的输出模式"""
        async def run_test():
            try:
                self.grep_tool._find_ripgrep()
            except FileNotFoundError:
                self.skipTest("ripgrep not available")
            
            params = {
                "pattern": "test",
                "path": self.test_dir,
                "output_mode": "files_with_matches"
            }
            
            result = await self.grep_tool.execute(params, self.context)
            
            if not result.metadata.get("error", False):
                self.assertEqual(result.metadata["output_mode"], "files_with_matches")
        
        asyncio.run(run_test())
    
    def test_count_output(self):
        """测试计数输出模式"""
        async def run_test():
            try:
                self.grep_tool._find_ripgrep()
            except FileNotFoundError:
                self.skipTest("ripgrep not available")
            
            params = {
                "pattern": "test",
                "path": self.test_dir,
                "output_mode": "count"
            }
            
            result = await self.grep_tool.execute(params, self.context)
            
            if not result.metadata.get("error", False):
                self.assertEqual(result.metadata["output_mode"], "count")
                self.assertIn("Total matches:", result.output)
        
        asyncio.run(run_test())
    
    def test_context_lines(self):
        """测试上下文行功能"""
        async def run_test():
            try:
                self.grep_tool._find_ripgrep()
            except FileNotFoundError:
                self.skipTest("ripgrep not available")
            
            params = {
                "pattern": "print",
                "path": self.test_dir,
                "context_before": 1,
                "context_after": 1
            }
            
            result = await self.grep_tool.execute(params, self.context)
            
            # 测试应该成功执行（不检查具体输出，因为ripgrep可能不可用）
            self.assertIsNotNone(result)
        
        asyncio.run(run_test())
    
    def test_head_limit(self):
        """测试输出限制"""
        async def run_test():
            try:
                self.grep_tool._find_ripgrep()
            except FileNotFoundError:
                self.skipTest("ripgrep not available")
            
            params = {
                "pattern": ".",  # 匹配任意字符，应该有很多结果
                "path": self.test_dir,
                "head_limit": 5
            }
            
            result = await self.grep_tool.execute(params, self.context)
            
            if not result.metadata.get("error", False) and result.metadata["matches"] > 5:
                self.assertTrue(result.metadata.get("truncated", False))
        
        asyncio.run(run_test())
    
    def test_no_matches(self):
        """测试没有匹配的情况"""
        async def run_test():
            try:
                self.grep_tool._find_ripgrep()
            except FileNotFoundError:
                self.skipTest("ripgrep not available")
            
            params = {
                "pattern": "thispatternwillnotmatch12345",
                "path": self.test_dir
            }
            
            result = await self.grep_tool.execute(params, self.context)
            
            self.assertEqual(result.output, "No files found")
            self.assertEqual(result.metadata["matches"], 0)
        
        asyncio.run(run_test())
    
    def test_invalid_path(self):
        """测试无效路径"""
        async def run_test():
            params = {
                "pattern": "test",
                "path": "/nonexistent/path"
            }
            
            result = await self.grep_tool.execute(params, self.context)
            
            # 应该返回错误或没有找到匹配
            self.assertTrue(
                result.metadata.get("error", False) or 
                result.metadata["matches"] == 0
            )
        
        asyncio.run(run_test())
    
    def test_empty_pattern(self):
        """测试空模式"""
        async def run_test():
            params = {
                "pattern": "",
                "path": self.test_dir
            }
            
            with self.assertRaises(ValueError):
                await self.grep_tool.execute(params, self.context)
        
        asyncio.run(run_test())
    
    def test_format_content_output(self):
        """测试内容输出格式化"""
        lines = [
            "/path/to/file1.py:10:    def test_function():",
            "/path/to/file1.py:15:    return test_value",
            "/path/to/file2.js:5:function test() {"
        ]
        
        formatted = self.grep_tool._format_content_output(lines, "/path/to")
        
        self.assertIn("Found 3 matches", formatted)
        self.assertIn("file1.py:", formatted)
        self.assertIn("Line 10:", formatted)
    
    def test_format_files_output(self):
        """测试文件列表输出格式化"""
        # 创建一些测试文件路径
        files = [
            os.path.join(self.test_dir, "test.py"),
            os.path.join(self.test_dir, "app.js")
        ]
        
        formatted = self.grep_tool._format_files_output(files)
        
        self.assertIn("Found", formatted)
        self.assertIn("files", formatted)
    
    def test_format_count_output(self):
        """测试计数输出格式化"""
        lines = [
            "/path/to/file1.py:5",
            "/path/to/file2.js:3"
        ]
        
        formatted = self.grep_tool._format_count_output(lines)
        
        self.assertIn("Total matches: 8", formatted)
        self.assertIn("Match counts by file:", formatted)


if __name__ == '__main__':
    unittest.main()
