#!/usr/bin/env python3
"""MultiEditTool 单元测试"""

import unittest
import asyncio
import os
import tempfile
import shutil

# 添加项目根目录到路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from tools.multi_edit_tool import MultiEditTool
    from tools.base_tool import ToolContext
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.multi_edit_tool import MultiEditTool
    from tools.base_tool import ToolContext


class TestMultiEditTool(unittest.TestCase):
    """MultiEditTool 测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.multi_edit_tool = MultiEditTool()
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
        self.assertEqual(self.multi_edit_tool.name, "multiedit")
        self.assertGreater(len(self.multi_edit_tool.description), 0)
        self.assertIn("多重编辑", self.multi_edit_tool.description)
    
    def test_parameters_schema(self):
        """测试参数模式"""
        schema = self.multi_edit_tool.get_parameters_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("filePath", schema["properties"])
        self.assertIn("edits", schema["properties"])
        
        # 检查edits数组的结构
        edits_schema = schema["properties"]["edits"]
        self.assertEqual(edits_schema["type"], "array")
        self.assertEqual(edits_schema["minItems"], 1)
        
        # 检查编辑项的结构
        edit_item_schema = edits_schema["items"]
        self.assertIn("oldString", edit_item_schema["properties"])
        self.assertIn("newString", edit_item_schema["properties"])
        self.assertIn("replaceAll", edit_item_schema["properties"])
        
        required = set(schema["required"])
        self.assertEqual(required, {"filePath", "edits"})
    
    def test_single_edit_operation(self):
        """测试单个编辑操作"""
        async def run_test():
            # 创建测试文件
            test_file = os.path.join(self.test_dir, "single_edit.py")
            content = """def hello():
    print("Hello, World!")
    return True"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            # 执行单个编辑
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [
                    {
                        "oldString": "Hello, World!",
                        "newString": "Hello, Python!"
                    }
                ]
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "multiedit")
            self.assertEqual(result.metadata["total_edits"], 1)
            self.assertEqual(result.metadata["successful_edits"], 1)
            
            # 验证文件内容
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("Hello, Python!", new_content)
            self.assertNotIn("Hello, World!", new_content)
        
        asyncio.run(run_test())
    
    def test_multiple_edit_operations(self):
        """测试多个编辑操作"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "multiple_edits.py")
            content = """def calculate(a, b):
    result = a + b
    print(f"Result: {result}")
    return result

def process():
    value = 42
    return value"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            # 执行多个编辑操作
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [
                    {
                        "oldString": "a + b",
                        "newString": "a * b"
                    },
                    {
                        "oldString": "Result:",
                        "newString": "Product:"
                    },
                    {
                        "oldString": "value = 42",
                        "newString": "value = 100"
                    }
                ]
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "multiedit")
            self.assertEqual(result.metadata["total_edits"], 3)
            self.assertEqual(result.metadata["successful_edits"], 3)
            
            # 验证文件内容
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("a * b", new_content)
            self.assertIn("Product:", new_content)
            self.assertIn("value = 100", new_content)
            self.assertNotIn("a + b", new_content)
            self.assertNotIn("Result:", new_content)
            self.assertNotIn("value = 42", new_content)
        
        asyncio.run(run_test())
    
    def test_sequential_edits_with_dependencies(self):
        """测试有依赖关系的连续编辑"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "sequential.py")
            content = """class OldClass:
    def old_method(self):
        return "old_result\""""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            # 先重命名类，再重命名方法
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [
                    {
                        "oldString": "OldClass",
                        "newString": "NewClass"
                    },
                    {
                        "oldString": "old_method",
                        "newString": "new_method"
                    },
                    {
                        "oldString": "old_result",
                        "newString": "new_result"
                    }
                ]
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "multiedit")
            self.assertEqual(result.metadata["successful_edits"], 3)
            
            # 验证文件内容
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("NewClass", new_content)
            self.assertIn("new_method", new_content)
            self.assertIn("new_result", new_content)
            self.assertNotIn("OldClass", new_content)
            self.assertNotIn("old_method", new_content)
            self.assertNotIn("old_result", new_content)
        
        asyncio.run(run_test())
    
    def test_replace_all_in_multiple_edits(self):
        """测试在多个编辑中使用 replaceAll"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "replace_all_multi.py")
            content = """def test():
    var = "old"
    print(var)
    var_copy = var
    return var

def another():
    temp = "temporary"
    print(temp)
    return temp"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [
                    {
                        "oldString": "var",
                        "newString": "variable",
                        "replaceAll": True
                    },
                    {
                        "oldString": "temp",
                        "newString": "temporary_value",
                        "replaceAll": True
                    }
                ]
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "multiedit")
            self.assertEqual(result.metadata["successful_edits"], 2)
            
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            # 检查所有 "var" 都被替换（但不影响 "variable"）
            self.assertNotIn(" var ", new_content)
            self.assertNotIn("var=", new_content)
            self.assertNotIn("var_", new_content)
            self.assertIn("variable", new_content)
            
            # 检查所有 "temp" 都被替换
            self.assertNotIn(" temp ", new_content)
            self.assertNotIn("temp=", new_content)
            self.assertIn("temporary_value", new_content)
        
        asyncio.run(run_test())
    
    def test_create_new_file_with_multiple_edits(self):
        """测试创建新文件并进行多次编辑"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "new_multi_edit.py")
            
            # 创建文件并进行编辑
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [
                    {
                        "oldString": "",
                        "newString": """# Template file
def placeholder():
    return "placeholder_value"

class PlaceholderClass:
    pass"""
                    },
                    {
                        "oldString": "placeholder",
                        "newString": "actual",
                        "replaceAll": True
                    },
                    {
                        "oldString": "PlaceholderClass",
                        "newString": "ActualClass"
                    }
                ]
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "multiedit")
            self.assertEqual(result.metadata["successful_edits"], 3)
            
            # 验证文件创建和内容
            self.assertTrue(os.path.exists(test_file))
            
            with open(test_file, 'r') as f:
                content = f.read()
            
            self.assertIn("def actual()", content)
            self.assertIn("actual_value", content)
            self.assertIn("ActualClass", content)
            self.assertNotIn("placeholder", content)
            self.assertNotIn("PlaceholderClass", content)
        
        asyncio.run(run_test())
    
    def test_failed_edit_stops_processing(self):
        """测试失败的编辑停止处理"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "fail_test.py")
            content = """def hello():
    print("Hello!")"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            # 第二个编辑会失败（字符串不存在）
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [
                    {
                        "oldString": "Hello!",
                        "newString": "Hello, World!"
                    },
                    {
                        "oldString": "nonexistent_string",
                        "newString": "replacement"
                    },
                    {
                        "oldString": "def hello",
                        "newString": "def greeting"
                    }
                ]
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "multiedit_failed")
            self.assertEqual(result.metadata["failed_edit_index"], 1)
            self.assertEqual(result.metadata["completed_edits"], 1)
            self.assertEqual(result.metadata["total_edits"], 3)
            
            # 验证只有第一个编辑被应用
            with open(test_file, 'r') as f:
                content = f.read()
            
            self.assertIn("Hello, World!", content)  # 第一个编辑成功
            self.assertIn("def hello", content)      # 第三个编辑未执行
        
        asyncio.run(run_test())
    
    def test_multiline_edits(self):
        """测试多行编辑"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "multiline.py")
            content = """def process_data():
    # Step 1: Load
    data = load_file()
    
    # Step 2: Process
    result = process(data)
    
    # Step 3: Save
    save_file(result)
    return result"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [
                    {
                        "oldString": """# Step 1: Load
    data = load_file()""",
                        "newString": """# Step 1: Load with validation
    data = load_and_validate_file()"""
                    },
                    {
                        "oldString": """# Step 2: Process
    result = process(data)""",
                        "newString": """# Step 2: Enhanced processing
    result = enhanced_process(data)
    result = validate_result(result)"""
                    }
                ]
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "multiedit")
            self.assertEqual(result.metadata["successful_edits"], 2)
            
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("load_and_validate_file", new_content)
            self.assertIn("enhanced_process", new_content)
            self.assertIn("validate_result", new_content)
        
        asyncio.run(run_test())
    
    def test_empty_edits_error(self):
        """测试空编辑数组错误"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "test.py")
            with open(test_file, 'w') as f:
                f.write("content")
            
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": []
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "missing_edits")
            self.assertIn("不能为空", result.output)
        
        asyncio.run(run_test())
    
    def test_missing_file_path_error(self):
        """测试缺少文件路径错误"""
        async def run_test():
            result = await self.multi_edit_tool.execute({
                "edits": [{"oldString": "old", "newString": "new"}]
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "missing_file_path")
            self.assertIn("filePath 参数是必需的", result.output)
        
        asyncio.run(run_test())
    
    def test_invalid_edit_format_error(self):
        """测试无效编辑格式错误"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "test.py")
            with open(test_file, 'w') as f:
                f.write("content")
            
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": ["invalid_edit"]
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "invalid_edit_format")
            self.assertEqual(result.metadata["edit_index"], 0)
            self.assertIn("必须是一个对象", result.output)
        
        asyncio.run(run_test())
    
    def test_missing_edit_fields_error(self):
        """测试缺少编辑字段错误"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "test.py")
            with open(test_file, 'w') as f:
                f.write("content")
            
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [{"oldString": "old"}]  # 缺少 newString
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "missing_edit_fields")
            self.assertEqual(result.metadata["edit_index"], 0)
            self.assertIn("必须包含 oldString 和 newString", result.output)
        
        asyncio.run(run_test())
    
    def test_identical_strings_error(self):
        """测试相同字符串错误"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "test.py")
            with open(test_file, 'w') as f:
                f.write("content")
            
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [{"oldString": "same", "newString": "same"}]
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "identical_strings")
            self.assertEqual(result.metadata["edit_index"], 0)
            self.assertIn("必须不同", result.output)
        
        asyncio.run(run_test())
    
    def test_file_not_found_propagation(self):
        """测试文件未找到错误传播"""
        async def run_test():
            nonexistent_file = os.path.join(self.test_dir, "nonexistent.py")
            
            result = await self.multi_edit_tool.execute({
                "filePath": nonexistent_file,
                "edits": [{"oldString": "old", "newString": "new"}]
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "multiedit_failed")
            self.assertEqual(result.metadata["failed_edit_index"], 0)
            self.assertEqual(result.metadata["completed_edits"], 0)
        
        asyncio.run(run_test())
    
    def test_complex_code_refactoring(self):
        """测试复杂代码重构"""
        async def run_test():
            test_file = os.path.join(self.test_dir, "refactor.py")
            content = """class DataProcessor:
    def __init__(self):
        self.data = []
    
    def load_data(self, file_path):
        with open(file_path) as f:
            self.data = f.read().split('\\n')
    
    def process_data(self):
        processed = []
        for item in self.data:
            if item.strip():
                processed.append(item.upper())
        return processed
    
    def save_results(self, results, output_path):
        with open(output_path, 'w') as f:
            f.write('\\n'.join(results))"""
            
            with open(test_file, 'w') as f:
                f.write(content)
            
            # 重构：改名、添加功能、优化代码
            result = await self.multi_edit_tool.execute({
                "filePath": test_file,
                "edits": [
                    {
                        "oldString": "class DataProcessor:",
                        "newString": "class EnhancedDataProcessor:"
                    },
                    {
                        "oldString": "def load_data(self, file_path):",
                        "newString": "def load_data(self, file_path, encoding='utf-8'):"
                    },
                    {
                        "oldString": "with open(file_path) as f:",
                        "newString": "with open(file_path, encoding=encoding) as f:"
                    },
                    {
                        "oldString": "def process_data(self):",
                        "newString": "def process_data(self, transform_func=None):"
                    },
                    {
                        "oldString": """processed = []
        for item in self.data:
            if item.strip():
                processed.append(item.upper())
        return processed""",
                        "newString": """processed = []
        for item in self.data:
            if item.strip():
                result = item.upper() if not transform_func else transform_func(item)
                processed.append(result)
        return processed"""
                    }
                ]
            }, self.context)
            
            self.assertEqual(result.metadata["action"], "multiedit")
            self.assertEqual(result.metadata["successful_edits"], 5)
            
            with open(test_file, 'r') as f:
                new_content = f.read()
            
            self.assertIn("EnhancedDataProcessor", new_content)
            self.assertIn("encoding='utf-8'", new_content)
            self.assertIn("transform_func=None", new_content)
            self.assertIn("transform_func(item)", new_content)
        
        asyncio.run(run_test())
    
    def test_tool_to_dict(self):
        """测试工具转换为字典"""
        tool_dict = self.multi_edit_tool.to_dict()
        
        self.assertEqual(tool_dict["name"], "multiedit")
        self.assertIn("description", tool_dict)
        self.assertIn("parameters", tool_dict)
        
        params = tool_dict["parameters"]
        self.assertIn("filePath", params["properties"])
        self.assertIn("edits", params["properties"])
        
        edits_schema = params["properties"]["edits"]
        self.assertEqual(edits_schema["type"], "array")
        self.assertIn("items", edits_schema)


if __name__ == "__main__":
    unittest.main()
