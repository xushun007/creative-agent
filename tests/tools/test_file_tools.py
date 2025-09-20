#!/usr/bin/env python3
"""ReadTool 和 WriteTool 单元测试"""

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
    from tools.file_tools import ReadTool, WriteTool
    from tools.base_tool import ToolContext
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.file_tools import ReadTool, WriteTool
    from tools.base_tool import ToolContext


class TestFileTools(unittest.TestCase):
    """文件工具测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.read_tool = ReadTool()
        self.write_tool = WriteTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
        
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
    
    def tearDown(self):
        """测试后清理"""
        os.chdir(self.original_cwd)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_read_tool_basic_properties(self):
        """测试ReadTool基本属性"""
        self.assertEqual(self.read_tool.name, "read")
        self.assertGreater(len(self.read_tool.description), 0)
        self.assertIn("文件系统", self.read_tool.description)
    
    def test_write_tool_basic_properties(self):
        """测试WriteTool基本属性"""
        self.assertEqual(self.write_tool.name, "write")
        self.assertGreater(len(self.write_tool.description), 0)
        self.assertIn("文件系统", self.write_tool.description)
    
    def test_read_tool_parameters_schema(self):
        """测试ReadTool参数模式"""
        schema = self.read_tool.get_parameters_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("filePath", schema["properties"])
        self.assertIn("offset", schema["properties"])
        self.assertIn("limit", schema["properties"])
        self.assertIn("filePath", schema["required"])
        
        # 验证参数限制
        self.assertEqual(schema["properties"]["offset"]["minimum"], 0)
        self.assertEqual(schema["properties"]["limit"]["minimum"], 1)
        self.assertEqual(schema["properties"]["limit"]["maximum"], 10000)
    
    def test_write_tool_parameters_schema(self):
        """测试WriteTool参数模式"""
        schema = self.write_tool.get_parameters_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("filePath", schema["properties"])
        self.assertIn("content", schema["properties"])
        self.assertEqual(set(schema["required"]), {"filePath", "content"})
    
    def test_write_and_read_simple_file(self):
        """测试写入和读取简单文件"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "test.txt")
            test_content = "Hello, World!\nThis is a test file.\nLine 3"
            
            # 写入文件
            write_result = await self.write_tool.execute({
                "filePath": test_file,
                "content": test_content
            }, self.context)
            
            self.assertIn("成功创建文件", write_result.output)
            self.assertEqual(write_result.metadata["file_exists"], False)
            self.assertEqual(write_result.metadata["line_count"], 3)
            
            # 读取文件
            read_result = await self.read_tool.execute({
                "filePath": test_file
            }, self.context)
            
            self.assertIn("<file>", read_result.output)
            self.assertIn("Hello, World!", read_result.output)
            self.assertIn("This is a test file.", read_result.output)
            self.assertIn("Line 3", read_result.output)
            self.assertEqual(read_result.metadata["total_lines"], 3)
        
        asyncio.run(run_test())
    
    def test_read_nonexistent_file(self):
        """测试读取不存在的文件"""
        async def run_test():
            nonexistent_file = os.path.join(self.test_dir, "nonexistent.txt")
            
            result = await self.read_tool.execute({
                "filePath": nonexistent_file
            }, self.context)
            
            self.assertIn("文件未找到", result.output)
            self.assertEqual(result.metadata["error"], "file_not_found")
        
        asyncio.run(run_test())
    
    def test_read_with_suggestions(self):
        """测试读取不存在文件时的建议"""
        async def run_test():
            # 创建一些相似的文件
            similar_file = os.path.join(self.test_dir, "similar_test.txt")
            with open(similar_file, 'w') as f:
                f.write("similar content")
            
            # 尝试读取不存在但相似的文件
            nonexistent_file = os.path.join(self.test_dir, "test.txt")
            
            result = await self.read_tool.execute({
                "filePath": nonexistent_file
            }, self.context)
            
            self.assertIn("您是否指的是", result.output)
            self.assertGreater(len(result.metadata["suggestions"]), 0)
        
        asyncio.run(run_test())
    
    def test_read_empty_file(self):
        """测试读取空文件"""
        async def run_test():
            empty_file = os.path.join(self.test_dir, "empty.txt")
            
            # 创建空文件
            await self.write_tool.execute({
                "filePath": empty_file,
                "content": ""
            }, self.context)
            
            # 读取空文件
            result = await self.read_tool.execute({
                "filePath": empty_file
            }, self.context)
            
            self.assertIn("(文件为空)", result.output)
            self.assertEqual(result.metadata["total_lines"], 0)
        
        asyncio.run(run_test())
    
    def test_read_with_offset_and_limit(self):
        """测试使用偏移和限制读取文件"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "multiline.txt")
            lines = [f"Line {i+1}" for i in range(10)]
            content = "\n".join(lines)
            
            # 写入多行文件
            await self.write_tool.execute({
                "filePath": test_file,
                "content": content
            }, self.context)
            
            # 使用偏移和限制读取
            result = await self.read_tool.execute({
                "filePath": test_file,
                "offset": 2,
                "limit": 3
            }, self.context)
            
            self.assertIn("Line 3", result.output)
            self.assertIn("Line 4", result.output)
            self.assertIn("Line 5", result.output)
            self.assertNotIn("Line 1", result.output)
            self.assertNotIn("Line 6", result.output)
            self.assertEqual(result.metadata["lines_read"], 3)
            self.assertEqual(result.metadata["offset"], 2)
        
        asyncio.run(run_test())
    
    def test_read_long_lines_truncation(self):
        """测试长行截断"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "long_line.txt")
            long_line = "x" * 2500  # 超过2000字符的行
            
            await self.write_tool.execute({
                "filePath": test_file,
                "content": long_line
            }, self.context)
            
            result = await self.read_tool.execute({
                "filePath": test_file
            }, self.context)
            
            self.assertIn("...", result.output)  # 截断标记
            # 检查输出中的行长度不超过限制
            lines = result.output.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('<') and not line.startswith('('):  # 只检查内容行，排除标签和提示
                    self.assertLessEqual(len(line), 2010)  # 允许一些格式字符
        
        asyncio.run(run_test())
    
    def test_write_overwrite_existing_file(self):
        """测试覆盖现有文件"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "overwrite.txt")
            
            # 首次写入
            await self.write_tool.execute({
                "filePath": test_file,
                "content": "Original content"
            }, self.context)
            
            # 覆盖写入
            result = await self.write_tool.execute({
                "filePath": test_file,
                "content": "New content"
            }, self.context)
            
            self.assertIn("成功覆盖文件", result.output)
            self.assertEqual(result.metadata["file_exists"], True)
            
            # 验证内容已更改
            read_result = await self.read_tool.execute({
                "filePath": test_file
            }, self.context)
            
            self.assertIn("New content", read_result.output)
            self.assertNotIn("Original content", read_result.output)
        
        asyncio.run(run_test())
    
    def test_write_create_directory(self):
        """测试创建目录"""
        async def run_test():
            nested_file = os.path.join(self.test_dir, "subdir", "nested.txt")
            
            result = await self.write_tool.execute({
                "filePath": nested_file,
                "content": "Nested file content"
            }, self.context)
            
            self.assertIn("成功创建文件", result.output)
            self.assertTrue(os.path.exists(nested_file))
            self.assertTrue(os.path.isdir(os.path.dirname(nested_file)))
        
        asyncio.run(run_test())
    
    def test_read_binary_file_detection(self):
        """测试二进制文件检测"""
        async def run_test():
            binary_file = os.path.join(self.test_dir, "binary.bin")
            
            # 创建包含二进制数据的文件
            with open(binary_file, 'wb') as f:
                f.write(b'\x00\x01\x02\x03\xff\xfe\xfd')
            
            result = await self.read_tool.execute({
                "filePath": binary_file
            }, self.context)
            
            self.assertIn("无法读取二进制文件", result.output)
            self.assertEqual(result.metadata["error"], "binary_file")
        
        asyncio.run(run_test())
    
    def test_read_image_file_detection(self):
        """测试图像文件检测"""
        async def run_test():
            image_file = os.path.join(self.test_dir, "test.jpg")
            
            # 创建一个假的图像文件（只是扩展名）
            with open(image_file, 'w') as f:
                f.write("fake image content")
            
            result = await self.read_tool.execute({
                "filePath": image_file
            }, self.context)
            
            self.assertIn("图像文件", result.output)
            self.assertEqual(result.metadata["error"], "image_file")
            self.assertEqual(result.metadata["image_type"], "JPEG")
        
        asyncio.run(run_test())
    
    def test_unicode_content(self):
        """测试Unicode内容"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "unicode.txt")
            unicode_content = "Hello 世界! 🌍\n测试中文内容\nEmoji: 😀🎉"
            
            # 写入Unicode内容
            write_result = await self.write_tool.execute({
                "filePath": test_file,
                "content": unicode_content
            }, self.context)
            
            self.assertIn("成功创建文件", write_result.output)
            
            # 读取Unicode内容
            read_result = await self.read_tool.execute({
                "filePath": test_file
            }, self.context)
            
            self.assertIn("世界", read_result.output)
            self.assertIn("测试中文", read_result.output)
            self.assertIn("🌍", read_result.output)
            self.assertIn("😀", read_result.output)
        
        asyncio.run(run_test())
    
    def test_file_statistics(self):
        """测试文件统计信息"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "stats.txt")
            content = "Line 1\nLine 2\nLine 3\n"
            
            write_result = await self.write_tool.execute({
                "filePath": test_file,
                "content": content
            }, self.context)
            
            # 验证写入统计
            self.assertEqual(write_result.metadata["line_count"], 4)  # 包括最后的空行
            self.assertGreater(write_result.metadata["file_size"], 0)
            
            # 验证读取统计
            read_result = await self.read_tool.execute({
                "filePath": test_file
            }, self.context)
            
            self.assertEqual(read_result.metadata["total_lines"], 3)  # 实际读取到的行数
            self.assertEqual(read_result.metadata["lines_read"], 3)
        
        asyncio.run(run_test())
    
    def test_tools_to_dict(self):
        """测试工具转换为字典"""
        read_dict = self.read_tool.to_dict()
        write_dict = self.write_tool.to_dict()
        
        # 验证ReadTool字典
        self.assertEqual(read_dict["name"], "read")
        self.assertIn("description", read_dict)
        self.assertIn("parameters", read_dict)
        
        # 验证WriteTool字典
        self.assertEqual(write_dict["name"], "write")
        self.assertIn("description", write_dict)
        self.assertIn("parameters", write_dict)
        
        # 验证参数结构
        read_params = read_dict["parameters"]
        write_params = write_dict["parameters"]
        
        self.assertIn("filePath", read_params["properties"])
        self.assertIn("filePath", write_params["properties"])
        self.assertIn("content", write_params["properties"])


if __name__ == "__main__":
    unittest.main()
