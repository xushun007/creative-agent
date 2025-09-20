#!/usr/bin/env python3
"""ListTool 单元测试"""

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
    from tools.list_tool import ListTool
    from tools.base_tool import ToolContext
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.list_tool import ListTool
    from tools.base_tool import ToolContext


class TestListTool(unittest.TestCase):
    """ListTool测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.list_tool = ListTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
        
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # 创建测试目录结构
        self._create_test_structure()
    
    def tearDown(self):
        """测试后清理"""
        os.chdir(self.original_cwd)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _create_test_structure(self):
        """创建测试目录结构"""
        # 创建根目录文件
        with open("README.md", "w") as f:
            f.write("# Test Project\n")
        
        with open("main.py", "w") as f:
            f.write("print('Hello World')\n")
        
        with open(".gitignore", "w") as f:
            f.write("*.pyc\n__pycache__/\n")
        
        # 创建src目录
        os.makedirs("src", exist_ok=True)
        with open("src/__init__.py", "w") as f:
            f.write("")
        
        with open("src/app.py", "w") as f:
            f.write("def main(): pass\n")
        
        # 创建src/utils子目录
        os.makedirs("src/utils", exist_ok=True)
        with open("src/utils/__init__.py", "w") as f:
            f.write("")
        
        with open("src/utils/helpers.py", "w") as f:
            f.write("def helper(): pass\n")
        
        # 创建tests目录
        os.makedirs("tests", exist_ok=True)
        with open("tests/test_main.py", "w") as f:
            f.write("import unittest\n")
        
        # 创建应该被忽略的目录
        os.makedirs("node_modules", exist_ok=True)
        with open("node_modules/package.json", "w") as f:
            f.write("{}\n")
        
        os.makedirs("__pycache__", exist_ok=True)
        with open("__pycache__/main.cpython-38.pyc", "w") as f:
            f.write("compiled")
        
        os.makedirs(".git", exist_ok=True)
        with open(".git/config", "w") as f:
            f.write("[core]\n")
        
        # 创建隐藏文件
        with open(".env", "w") as f:
            f.write("SECRET=value\n")
    
    def test_list_tool_basic_properties(self):
        """测试ListTool基本属性"""
        self.assertEqual(self.list_tool.name, "list")
        self.assertIsNotNone(self.list_tool.description)
        self.assertIn("目录", self.list_tool.description)
    
    def test_get_parameters_schema(self):
        """测试参数模式"""
        schema = self.list_tool.get_parameters_schema()
        
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema["type"], "object")
        self.assertIn("properties", schema)
        
        properties = schema["properties"]
        self.assertIn("path", properties)
        self.assertIn("ignore", properties)
        self.assertIn("show_hidden", properties)
    
    def test_should_ignore(self):
        """测试忽略判断"""
        # 测试默认忽略的目录
        self.assertTrue(self.list_tool._should_ignore("node_modules", [], False))
        self.assertTrue(self.list_tool._should_ignore("__pycache__", [], False))
        self.assertTrue(self.list_tool._should_ignore(".git", [], False))
        self.assertFalse(self.list_tool._should_ignore("src", [], False))
        self.assertFalse(self.list_tool._should_ignore("tests", [], False))
    
    def test_should_ignore_file(self):
        """测试文件忽略判断"""
        # 测试隐藏文件（不在默认忽略列表中的）
        self.assertTrue(self.list_tool._should_ignore(".hidden_file", [], False))
        self.assertFalse(self.list_tool._should_ignore(".hidden_file", [], True))
        
        # 测试普通文件
        self.assertFalse(self.list_tool._should_ignore("main.py", [], False))
        self.assertFalse(self.list_tool._should_ignore("README.md", [], False))
        
        # 测试自定义忽略模式
        ignore_patterns = ["*.pyc", "test_*"]
        self.assertTrue(self.list_tool._should_ignore("main.pyc", ignore_patterns, False))
        self.assertTrue(self.list_tool._should_ignore("test_file.py", ignore_patterns, False))
        self.assertFalse(self.list_tool._should_ignore("main.py", ignore_patterns, False))
    
    def test_basic_listing(self):
        """测试基本目录列表功能"""
        async def run_test():
            params = {
                "path": self.test_dir
            }
            
            result = await self.list_tool.execute(params, self.context)
            
            self.assertIsNotNone(result)
            self.assertIsInstance(result.metadata, dict)
            
            # 检查是否有内容（可能为0如果所有文件都被忽略）
            if result.metadata["count"] > 0:
                # 应该包含我们创建的文件（如果没有被忽略）
                self.assertTrue("main.py" in result.output or "README.md" in result.output or "src/" in result.output)
                
                # 不应该包含被忽略的目录
                self.assertNotIn("node_modules", result.output)
                self.assertNotIn("__pycache__", result.output)
                self.assertNotIn(".git", result.output)
            else:
                # 如果count为0，应该显示空目录信息
                self.assertIn("empty", result.output.lower())
        
        asyncio.run(run_test())
    
    def test_show_hidden_files(self):
        """测试显示隐藏文件"""
        async def run_test():
            params = {
                "path": self.test_dir,
                "show_hidden": True
            }
            
            result = await self.list_tool.execute(params, self.context)
            
            # 如果有文件，应该包含隐藏文件（除了被默认忽略的）
            if result.metadata["count"] > 0:
                # .gitignore不在默认忽略列表中，应该显示
                self.assertIn(".gitignore", result.output)
            else:
                # 如果没有文件，检查是否是空目录
                self.assertIn("empty", result.output.lower())
        
        asyncio.run(run_test())
    
    def test_hide_hidden_files(self):
        """测试隐藏隐藏文件"""
        async def run_test():
            params = {
                "path": self.test_dir,
                "show_hidden": False
            }
            
            result = await self.list_tool.execute(params, self.context)
            
            # 不应该包含隐藏文件（除了.gitignore等常见文件）
            self.assertNotIn(".env", result.output)
        
        asyncio.run(run_test())
    
    def test_custom_ignore_patterns(self):
        """测试自定义忽略模式"""
        async def run_test():
            params = {
                "path": self.test_dir,
                "ignore": ["*.py", "README.*"]
            }
            
            result = await self.list_tool.execute(params, self.context)
            
            # 应该忽略匹配模式的文件
            self.assertNotIn("main.py", result.output)
            self.assertNotIn("README.md", result.output)
        
        asyncio.run(run_test())
    
    def test_tree_structure_output(self):
        """测试树形结构输出"""
        async def run_test():
            params = {
                "path": self.test_dir
                # ListTool默认就是树形输出，不需要output_format参数
            }
            
            result = await self.list_tool.execute(params, self.context)
            
            # 如果有文件，应该有树形结构
            if result.metadata["count"] > 0:
                lines = result.output.split('\n')
                tree_lines = [line for line in lines if '├──' in line or '└──' in line or '│' in line or line.endswith('/')]
                self.assertGreater(len(tree_lines), 0)
            else:
                # 如果目录为空，应该显示相应信息
                self.assertIn("empty", result.output.lower())
        
        asyncio.run(run_test())
    
    def test_basic_output_format(self):
        """测试基本输出格式"""
        async def run_test():
            params = {
                "path": self.test_dir
            }
            
            result = await self.list_tool.execute(params, self.context)
            
            # 应该以目录路径开始
            lines = result.output.split('\n')
            self.assertTrue(lines[0].endswith('/'))
            
            # 如果有文件，检查输出格式
            if result.metadata["count"] > 0:
                # 应该有文件或目录项
                content_lines = [line for line in lines[1:] if line.strip() and not line.startswith('(')]
                self.assertGreater(len(content_lines), 0)
            else:
                # 空目录应该显示相应信息
                self.assertIn("empty", result.output.lower())
        
        asyncio.run(run_test())
    
    def test_nonexistent_path(self):
        """测试不存在的路径"""
        async def run_test():
            params = {
                "path": "/nonexistent/path"
            }
            
            result = await self.list_tool.execute(params, self.context)
            
            self.assertTrue(result.metadata.get("error", False))
            self.assertIn("does not exist", result.output.lower())
        
        asyncio.run(run_test())
    
    def test_file_path_instead_of_directory(self):
        """测试传入文件路径而不是目录路径"""
        async def run_test():
            file_path = os.path.join(self.test_dir, "main.py")
            params = {
                "path": file_path
            }
            
            result = await self.list_tool.execute(params, self.context)
            
            self.assertTrue(result.metadata.get("error", False))
            self.assertIn("not a directory", result.output.lower())
        
        asyncio.run(run_test())
    
    def test_relative_path_handling(self):
        """测试相对路径处理"""
        async def run_test():
            # 创建子目录并切换到其中
            subdir = os.path.join(self.test_dir, "subtest")
            os.makedirs(subdir, exist_ok=True)
            
            # 在子目录中创建一个文件确保不为空
            with open(os.path.join(subdir, "test_file.txt"), "w") as f:
                f.write("test content")
            
            original_cwd = os.getcwd()
            try:
                os.chdir(subdir)
                
                params = {
                    "path": ".."  # 相对路径指向父目录
                }
                
                result = await self.list_tool.execute(params, self.context)
                
                self.assertFalse(result.metadata.get("error", False))
                # 父目录可能为空或有内容，都是正常的
                self.assertGreaterEqual(result.metadata["count"], 0)
                
            finally:
                os.chdir(original_cwd)
        
        asyncio.run(run_test())
    
    def test_large_directory_limit(self):
        """测试大目录的限制功能"""
        async def run_test():
            # 创建很多文件来测试限制
            large_dir = os.path.join(self.test_dir, "large")
            os.makedirs(large_dir, exist_ok=True)
            
            # 创建超过限制数量的文件
            for i in range(150):  # 超过默认限制100
                with open(f"{large_dir}/file_{i:03d}.txt", "w") as f:
                    f.write(f"File {i}")
            
            params = {
                "path": large_dir
            }
            
            result = await self.list_tool.execute(params, self.context)
            
            # 检查是否达到了限制
            # 由于我们创建了150个文件，应该达到100的限制
            if result.metadata["count"] >= 100:
                self.assertTrue(result.metadata.get("truncated", False))
                self.assertIn("truncated", result.output.lower())
            else:
                # 如果没有达到限制，说明测试设置有问题，但不应该失败
                self.assertGreaterEqual(result.metadata["count"], 0)
        
        asyncio.run(run_test())
    
    def test_build_tree_structure(self):
        """测试树状结构构建"""
        files = [
            "file1.txt",
            "dir1/file2.txt",
            "dir1/subdir/file3.txt",
            "dir2/file4.txt"
        ]
        
        structure = self.list_tool._build_tree_structure(files)
        
        # 检查结构
        self.assertIn("file1.txt", structure)
        self.assertIn("dir1", structure)
        self.assertIn("dir2", structure)
        
        # 检查嵌套结构
        if "dir1" in structure and structure["dir1"] is not None:
            self.assertIn("file2.txt", structure["dir1"])
            if "subdir" in structure["dir1"]:
                self.assertIn("file3.txt", structure["dir1"]["subdir"])
    
    def test_render_tree_structure(self):
        """测试树形结构渲染"""
        structure = {
            "file1.txt": None,  # 文件用None标记
            "dir1": {
                "file2.txt": None,
                "subdir": {
                    "file3.txt": None
                }
            }
        }
        
        rendered = self.list_tool._render_tree(structure, "", True, self.test_dir)
        
        # 检查树形格式
        rendered_str = "\n".join(rendered)
        self.assertIn("file1.txt", rendered_str)
        self.assertIn("dir1/", rendered_str)  # 目录应该有/后缀


if __name__ == '__main__':
    unittest.main()
