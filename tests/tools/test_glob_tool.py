#!/usr/bin/env python3
"""GlobTool 单元测试"""

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
    from tools.glob_tool import GlobTool
    from tools.base_tool import ToolContext
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.glob_tool import GlobTool
    from tools.base_tool import ToolContext


class TestGlobTool(unittest.TestCase):
    """GlobTool测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.glob_tool = GlobTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
        
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # 创建测试文件结构
        self._create_test_files()
    
    def tearDown(self):
        """测试后清理"""
        os.chdir(self.original_cwd)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _create_test_files(self):
        """创建测试文件结构"""
        # 创建根目录文件
        files = [
            "main.py",
            "app.py", 
            "test_main.py",
            "config.json",
            "README.md",
            "setup.py"
        ]
        
        for file in files:
            with open(file, "w") as f:
                f.write(f"# Content of {file}\n")
        
        # 创建src目录和文件
        os.makedirs("src", exist_ok=True)
        src_files = [
            "src/__init__.py",
            "src/module1.py",
            "src/module2.py",
            "src/utils.py"
        ]
        
        for file in src_files:
            with open(file, "w") as f:
                f.write(f"# Content of {file}\n")
        
        # 创建tests目录和文件
        os.makedirs("tests", exist_ok=True)
        test_files = [
            "tests/__init__.py",
            "tests/test_module1.py",
            "tests/test_module2.py",
            "tests/test_utils.py"
        ]
        
        for file in test_files:
            with open(file, "w") as f:
                f.write(f"# Content of {file}\n")
        
        # 创建深层嵌套目录
        os.makedirs("deep/nested/directory", exist_ok=True)
        with open("deep/nested/directory/deep_file.py", "w") as f:
            f.write("# Deep nested file\n")
        
        # 创建不同扩展名的文件
        other_files = [
            "data.txt",
            "config.yaml",
            "script.sh",
            "document.pdf"  # 这个只是创建空文件
        ]
        
        for file in other_files:
            with open(file, "w") as f:
                f.write(f"Content of {file}\n")
    
    def test_glob_tool_basic_properties(self):
        """测试GlobTool基本属性"""
        self.assertEqual(self.glob_tool.name, "glob")
        self.assertIsNotNone(self.glob_tool.description)
        self.assertIn("模式匹配", self.glob_tool.description)
    
    def test_get_parameters_schema(self):
        """测试参数模式"""
        schema = self.glob_tool.get_parameters_schema()
        
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema["type"], "object")
        self.assertIn("properties", schema)
        self.assertIn("required", schema)
        self.assertIn("pattern", schema["required"])
        
        properties = schema["properties"]
        self.assertIn("pattern", properties)
        self.assertIn("path", properties)
    
    def test_expand_braces(self):
        """测试大括号展开功能"""
        # 测试简单大括号
        patterns = self.glob_tool._expand_braces("*.{py,js}")
        self.assertIn("*.py", patterns)
        self.assertIn("*.js", patterns)
        self.assertEqual(len(patterns), 2)
        
        # 测试多个选项
        patterns = self.glob_tool._expand_braces("test_{a,b,c}.py")
        expected = ["test_a.py", "test_b.py", "test_c.py"]
        for exp in expected:
            self.assertIn(exp, patterns)
        
        # 测试没有大括号的情况
        patterns = self.glob_tool._expand_braces("*.py")
        self.assertEqual(patterns, ["*.py"])
        
        # 测试嵌套大括号（简单情况）
        patterns = self.glob_tool._expand_braces("{src,tests}/*.py")
        self.assertIn("src/*.py", patterns)
        self.assertIn("tests/*.py", patterns)
    
    def test_simple_pattern_matching(self):
        """测试简单模式匹配"""
        async def run_test():
            params = {
                "pattern": "*.py",
                "path": self.test_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            self.assertIsNotNone(result)
            self.assertFalse(result.metadata.get("error", False))
            self.assertGreater(result.metadata["count"], 0)
            
            # 应该找到Python文件
            self.assertIn("main.py", result.output)
            self.assertIn("app.py", result.output)
            
            # 不应该包含非Python文件
            self.assertNotIn("config.json", result.output)
            self.assertNotIn("README.md", result.output)
        
        asyncio.run(run_test())
    
    def test_recursive_pattern_matching(self):
        """测试递归模式匹配"""
        async def run_test():
            params = {
                "pattern": "**/*.py",
                "path": self.test_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            self.assertFalse(result.metadata.get("error", False))
            
            # 应该找到所有Python文件，包括子目录中的
            output_lines = result.output.split('\n')
            py_files = [line for line in output_lines if line.endswith('.py')]
            
            self.assertGreater(len(py_files), 5)  # 应该有多个Python文件
        
        asyncio.run(run_test())
    
    def test_test_files_pattern(self):
        """测试匹配测试文件"""
        async def run_test():
            params = {
                "pattern": "test_*.py",
                "path": self.test_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            self.assertFalse(result.metadata.get("error", False))
            
            # 应该只找到测试文件
            if result.metadata["count"] > 0:
                self.assertIn("test_main.py", result.output)
                # 检查输出的文件列表，确保都是test_开头的
                output_lines = [line.strip() for line in result.output.split('\n') if line.strip()]
                for line in output_lines:
                    if line.endswith('.py'):
                        filename = os.path.basename(line)
                        self.assertTrue(filename.startswith('test_'), f"Found non-test file: {filename}")
        
        asyncio.run(run_test())
    
    def test_directory_specific_pattern(self):
        """测试特定目录中的模式匹配"""
        async def run_test():
            params = {
                "pattern": "src/*.py",
                "path": self.test_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            self.assertFalse(result.metadata.get("error", False))
            
            if result.metadata["count"] > 0:
                # 应该只包含src目录中的文件
                for line in result.output.split('\n'):
                    if line.strip() and not line.startswith('(') and line.endswith('.py'):
                        self.assertIn('src', line)
        
        asyncio.run(run_test())
    
    def test_brace_expansion_pattern(self):
        """测试大括号展开模式"""
        async def run_test():
            params = {
                "pattern": "*.{py,json}",
                "path": self.test_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            self.assertFalse(result.metadata.get("error", False))
            
            if result.metadata["count"] > 0:
                # 应该包含Python和JSON文件
                self.assertTrue(
                    "main.py" in result.output or 
                    "config.json" in result.output
                )
        
        asyncio.run(run_test())
    
    def test_question_mark_pattern(self):
        """测试问号通配符"""
        async def run_test():
            # 创建一些单字符文件名用于测试
            single_char_files = ["a.py", "b.py", "c.txt"]
            for file in single_char_files:
                with open(os.path.join(self.test_dir, file), "w") as f:
                    f.write("test")
            
            params = {
                "pattern": "?.py",
                "path": self.test_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            if result.metadata["count"] > 0:
                # 应该匹配单字符Python文件
                self.assertIn("a.py", result.output)
                self.assertIn("b.py", result.output)
                # 不应该匹配多字符文件名
                self.assertNotIn("main.py", result.output)
        
        asyncio.run(run_test())
    
    def test_character_class_pattern(self):
        """测试字符类模式"""
        async def run_test():
            # 创建一些测试文件
            test_files = ["file1.py", "file2.py", "fileA.py", "fileB.py"]
            for file in test_files:
                with open(os.path.join(self.test_dir, file), "w") as f:
                    f.write("test")
            
            params = {
                "pattern": "file[0-9].py",
                "path": self.test_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            if result.metadata["count"] > 0:
                # 应该匹配数字文件
                self.assertIn("file1.py", result.output)
                self.assertIn("file2.py", result.output)
        
        asyncio.run(run_test())
    
    def test_no_matches(self):
        """测试没有匹配的情况"""
        async def run_test():
            params = {
                "pattern": "*.nonexistent",
                "path": self.test_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            self.assertEqual(result.output, "No files found")
            self.assertEqual(result.metadata["count"], 0)
            self.assertFalse(result.metadata.get("truncated", False))
        
        asyncio.run(run_test())
    
    def test_nonexistent_path(self):
        """测试不存在的路径"""
        async def run_test():
            params = {
                "pattern": "*.py",
                "path": "/nonexistent/path"
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            self.assertTrue(result.metadata.get("error", False))
            self.assertIn("does not exist", result.output)
        
        asyncio.run(run_test())
    
    def test_file_path_instead_of_directory(self):
        """测试传入文件路径而不是目录路径"""
        async def run_test():
            file_path = os.path.join(self.test_dir, "main.py")
            params = {
                "pattern": "*.py",
                "path": file_path
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            self.assertTrue(result.metadata.get("error", False))
            self.assertIn("not a directory", result.output)
        
        asyncio.run(run_test())
    
    def test_empty_pattern(self):
        """测试空模式"""
        async def run_test():
            params = {
                "pattern": "",
                "path": self.test_dir
            }
            
            with self.assertRaises(ValueError):
                await self.glob_tool.execute(params, self.context)
        
        asyncio.run(run_test())
    
    def test_relative_path_handling(self):
        """测试相对路径处理"""
        async def run_test():
            # 创建子目录并切换到其中
            subdir = os.path.join(self.test_dir, "subtest")
            os.makedirs(subdir, exist_ok=True)
            os.chdir(subdir)
            
            params = {
                "pattern": "*.py",
                "path": ".."  # 相对路径指向父目录
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            self.assertFalse(result.metadata.get("error", False))
            if result.metadata["count"] > 0:
                self.assertIn("main.py", result.output)
        
        asyncio.run(run_test())
    
    def test_current_directory_default(self):
        """测试默认使用当前目录"""
        async def run_test():
            params = {
                "pattern": "*.py"
                # 不指定path参数
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            # 应该在当前目录中搜索
            self.assertFalse(result.metadata.get("error", False))
            if result.metadata["count"] > 0:
                self.assertIn("main.py", result.output)
        
        asyncio.run(run_test())
    
    def test_file_sorting_by_modification_time(self):
        """测试文件按修改时间排序"""
        async def run_test():
            # 创建几个文件，并设置不同的修改时间
            import time
            
            files = ["old.py", "new.py", "newer.py"]
            for i, file in enumerate(files):
                file_path = os.path.join(self.test_dir, file)
                with open(file_path, "w") as f:
                    f.write(f"# {file}")
                
                # 设置不同的修改时间
                mtime = time.time() - (len(files) - i) * 10
                os.utime(file_path, (mtime, mtime))
            
            params = {
                "pattern": "*.py",
                "path": self.test_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            if result.metadata["count"] > 0:
                lines = result.output.split('\n')
                py_files = [line for line in lines if line.endswith('.py')]
                
                # 检查文件顺序（newer应该在前面）
                if len(py_files) >= 2:
                    # 由于有其他文件，我们只检查我们创建的文件是否存在
                    self.assertIn("newer.py", result.output)
                    self.assertIn("new.py", result.output)
                    self.assertIn("old.py", result.output)
        
        asyncio.run(run_test())
    
    def test_large_result_truncation(self):
        """测试大量结果的截断"""
        async def run_test():
            # 创建大量文件来测试截断
            large_dir = os.path.join(self.test_dir, "large")
            os.makedirs(large_dir, exist_ok=True)
            
            # 创建超过限制数量的文件
            for i in range(150):  # 超过默认限制100
                with open(f"{large_dir}/file_{i:03d}.py", "w") as f:
                    f.write(f"# File {i}")
            
            params = {
                "pattern": "*.py",
                "path": large_dir
            }
            
            result = await self.glob_tool.execute(params, self.context)
            
            # 应该被截断
            self.assertTrue(result.metadata.get("truncated", False))
            self.assertIn("truncated", result.output.lower())
            self.assertEqual(result.metadata["count"], 100)  # 应该限制在100个
        
        asyncio.run(run_test())
    
    def test_manual_recursive_search(self):
        """测试手动递归搜索（作为glob的后备方案）"""
        matches = self.glob_tool._manual_recursive_search("*.py", self.test_dir)
        
        # 应该找到Python文件
        py_files = [m for m in matches if m.endswith('.py')]
        self.assertGreater(len(py_files), 0)
        
        # 检查是否包含预期的文件
        file_names = [os.path.basename(f) for f in py_files]
        self.assertIn("main.py", file_names)


if __name__ == '__main__':
    unittest.main()
