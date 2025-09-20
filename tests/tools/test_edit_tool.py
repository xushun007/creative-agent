#!/usr/bin/env python3
"""EditTool 单元测试"""

import unittest
import asyncio
import os
import tempfile
import shutil

# 添加src目录到路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from tools.edit_tool import EditTool
    from tools.base_tool import ToolContext
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.edit_tool import EditTool
    from tools.base_tool import ToolContext


class TestEditTool(unittest.TestCase):
    """EditTool 测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.edit_tool = EditTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
        
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
    
    def tearDown(self):
        """测试后清理"""
        os.chdir(self.original_cwd)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_tool_basic_properties(self):
        """测试工具基本属性"""
        self.assertEqual(self.edit_tool.name, "edit")
        self.assertGreater(len(self.edit_tool.description), 0)
        self.assertIn("字符串替换", self.edit_tool.description)
    
    def test_parameters_schema(self):
        """测试参数模式"""
        schema = self.edit_tool.get_parameters_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("filePath", schema["properties"])
        self.assertIn("oldString", schema["properties"])
        self.assertIn("newString", schema["properties"])
        self.assertIn("replaceAll", schema["properties"])
        
        required = set(schema["required"])
        self.assertEqual(required, {"filePath", "oldString", "newString"})
    
    def test_simple_string_replacement(self):
        """测试简单字符串替换"""
        async def run_test():
            # 创建测试文件
            test_file = os.path.join(self.test_dir, "simple.py")
            content = """def hello():
    print("Hello, World!")
    return True"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            # 执行替换
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": "Hello, World!",
                "newString": "Hello, Python!"
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "edit")
            self.assertIn("diff", result.metadata)
            
            # 验证文件内容
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("Hello, Python!", new_content)
            self.assertNotIn("Hello, World!", new_content)
        
        asyncio.run(run_test())
    
    def test_multiline_replacement(self):
        """测试多行替换"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "multiline.py")
            content = """def calculate(a, b):
    result = a + b
    print(f"Result: {result}")
    return result"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            old_block = """result = a + b
    print(f"Result: {result}")"""
            
            new_block = """result = a * b  # Changed to multiplication
    print(f"Product: {result}")"""
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": old_block,
                "newString": new_block
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "edit")
            
            # 验证替换结果
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("result = a * b", new_content)
            self.assertIn("Product:", new_content)
            self.assertNotIn("Result:", new_content)
        
        asyncio.run(run_test())
    
    def test_line_trimmed_replacement(self):
        """测试行修剪替换（忽略空白）"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "trimmed.py")
            content = """def process():
    if True:
        value = 42
        print(value)"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            # 使用不同缩进的搜索字符串
            old_string = """if True:
value = 42
print(value)"""
            
            new_string = """if True:
    value = 100
    print(f"New value: {value}")"""
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": old_string,
                "newString": new_string
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "edit")
            
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("value = 100", new_content)
            self.assertIn("New value:", new_content)
        
        asyncio.run(run_test())
    
    def test_replace_all_functionality(self):
        """测试 replaceAll 功能"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "replace_all.py")
            content = """def test():
    var = "old"
    print(var)
    return var"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": "var",
                "newString": "variable",
                "replaceAll": True
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "edit")
            self.assertTrue(result.metadata["replace_all"])
            
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            # 所有 "var" 都应该被替换
            self.assertNotIn("var", new_content.replace("variable", ""))
            self.assertEqual(new_content.count("variable"), 3)
        
        asyncio.run(run_test())
    
    def test_create_new_file(self):
        """测试创建新文件（oldString 为空）"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "new_file.py")
            new_content = """# New Python file
def main():
    print("Hello from new file!")

if __name__ == "__main__":
    main()"""
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": "",
                "newString": new_content
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "create")
            self.assertIn("diff", result.metadata)
            
            # 验证文件创建
            self.assertTrue(os.path.exists(test_file))
            
            with open(test_file, 'r') as f:
                file_content = f.read()
            
            self.assertEqual(file_content, new_content)
        
        asyncio.run(run_test())
    
    def test_whitespace_normalized_replacement(self):
        """测试空白标准化替换"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "whitespace.py")
            content = """def   process(   ):
    value    =    42
    print(  value  )"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            # 使用标准化的空白搜索
            old_string = "value = 42"
            new_string = "value = 100"
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": old_string,
                "newString": new_string
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "edit")
            
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("100", new_content)
            self.assertNotIn("42", new_content)
        
        asyncio.run(run_test())
    
    def test_indentation_flexible_replacement(self):
        """测试缩进灵活替换"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "indentation.py")
            content = """class Example:
    def method1(self):
        if True:
            value = 1
            return value
    
    def method2(self):
        value = 2
        return value"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            # 搜索时不考虑具体缩进
            old_string = """if True:
value = 1
return value"""
            
            new_string = """if True:
    result = 10
    return result"""
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": old_string,
                "newString": new_string
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "edit")
            
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("result = 10", new_content)
            self.assertNotIn("value = 1", new_content)
        
        asyncio.run(run_test())
    
    def test_file_not_found_error(self):
        """测试文件不存在错误"""
        async def run_test():
            nonexistent_file = os.path.join(self.test_dir, "nonexistent.py")
            
            result = await self.edit_tool.execute({
                "filePath": nonexistent_file,
                "oldString": "old",
                "newString": "new"
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "file_not_found")
            self.assertIn("文件不存在", result.output)
        
        asyncio.run(run_test())
    
    def test_directory_path_error(self):
        """测试目录路径错误"""
        async def run_test():
            directory_path = os.path.join(self.test_dir, "subdir")
            os.makedirs(directory_path)
            
            result = await self.edit_tool.execute({
                "filePath": directory_path,
                "oldString": "old",
                "newString": "new"
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "path_is_directory")
            self.assertIn("路径是目录", result.output)
        
        asyncio.run(run_test())
    
    def test_identical_strings_error(self):
        """测试相同字符串错误"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "test.py")
            with open(test_file, 'w') as f:
                f.write("test content")
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": "same",
                "newString": "same"
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "identical_strings")
            self.assertIn("必须不同", result.output)
        
        asyncio.run(run_test())
    
    def test_string_not_found_error(self):
        """测试字符串未找到错误"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "test.py")
            content = "def hello():\n    print('Hello')"
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": "nonexistent_string",
                "newString": "replacement"
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "replacement_failed")
            self.assertIn("未找到", result.output)
        
        asyncio.run(run_test())
    
    def test_block_anchor_replacement(self):
        """测试块锚点替换"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "block.py")
            content = """def process_data():
    # Start processing
    data = load_data()
    cleaned = clean_data(data)
    result = analyze(cleaned)
    # End processing
    return result"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            old_block = """# Start processing
    data = load_data()
    cleaned = clean_data(data)
    result = analyze(cleaned)
    # End processing"""
            
            new_block = """# Start enhanced processing
    data = load_data_v2()
    validated = validate_data(data)
    cleaned = clean_data(validated)
    result = analyze_advanced(cleaned)
    # End enhanced processing"""
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": old_block,
                "newString": new_block
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "edit")
            
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("enhanced processing", new_content)
            self.assertIn("load_data_v2", new_content)
            self.assertIn("validate_data", new_content)
        
        asyncio.run(run_test())
    
    def test_diff_generation(self):
        """测试差异生成"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "diff_test.py")
            content = """def old_function():
    return "old result\""""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            result = await self.edit_tool.execute({
                "filePath": test_file,
                "oldString": "old_function",
                "newString": "new_function"
            }, self.context)
            
            diff = result.metadata["diff"]
            self.assertIn("-", diff)  # 删除行标记
            self.assertIn("+", diff)  # 添加行标记
            self.assertIn("old_function", diff)
            self.assertIn("new_function", diff)
        
        asyncio.run(run_test())
    
    def test_tool_to_dict(self):
        """测试工具转换为字典"""
        tool_dict = self.edit_tool.to_dict()
        
        self.assertEqual(tool_dict["name"], "edit")
        self.assertIn("description", tool_dict)
        self.assertIn("parameters", tool_dict)
        
        params = tool_dict["parameters"]
        self.assertIn("filePath", params["properties"])
        self.assertIn("oldString", params["properties"])
        self.assertIn("newString", params["properties"])
        self.assertIn("replaceAll", params["properties"])


if __name__ == "__main__":
    unittest.main()
