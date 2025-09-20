#!/usr/bin/env python3
"""WebFetchTool 和 WebSearchTool 单元测试"""

import unittest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
import aiohttp

# 添加项目根目录到路径
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from tools.web_tools import WebFetchTool, WebSearchTool
    from tools.base_tool import ToolContext
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.web_tools import WebFetchTool, WebSearchTool
    from tools.base_tool import ToolContext


class TestWebFetchTool(unittest.TestCase):
    """WebFetchTool 测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.web_fetch_tool = WebFetchTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
    
    def test_tool_basic_properties(self):
        """测试工具基本属性"""
        self.assertEqual(self.web_fetch_tool.name, "webfetch")
        self.assertGreater(len(self.web_fetch_tool.description), 0)
        self.assertIn("网页获取", self.web_fetch_tool.description)
        self.assertIn("URL", self.web_fetch_tool.description)
    
    def test_parameters_schema(self):
        """测试参数模式"""
        schema = self.web_fetch_tool.get_parameters_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("url", schema["properties"])
        self.assertIn("format", schema["properties"])
        self.assertIn("timeout", schema["properties"])
        
        # 验证格式枚举
        format_enum = schema["properties"]["format"]["enum"]
        self.assertEqual(set(format_enum), {"text", "markdown", "html"})
        
        required = set(schema["required"])
        self.assertEqual(required, {"url", "format"})
    
    def test_validate_url(self):
        """测试 URL 验证"""
        tool = self.web_fetch_tool
        
        # 有效的 HTTPS URL
        self.assertEqual(
            tool._validate_url("https://example.com"),
            "https://example.com"
        )
        
        # HTTP URL 应该升级为 HTTPS
        self.assertEqual(
            tool._validate_url("http://example.com"),
            "https://example.com"
        )
        
        # 无效的 URL
        with self.assertRaises(ValueError):
            tool._validate_url("invalid-url")
        
        with self.assertRaises(ValueError):
            tool._validate_url("ftp://example.com")
    
    def test_extract_text_from_html(self):
        """测试 HTML 文本提取"""
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Main Title</h1>
                <p>This is a paragraph.</p>
                <script>console.log('ignored');</script>
                <style>.test { color: red; }</style>
                <div>Another text block.</div>
            </body>
        </html>
        """
        
        text = self.web_fetch_tool._extract_text_from_html(html)
        
        self.assertIn("Main Title", text)
        self.assertIn("This is a paragraph.", text)
        self.assertIn("Another text block.", text)
        self.assertNotIn("console.log", text)
        self.assertNotIn("color: red", text)
    
    def test_convert_html_to_markdown(self):
        """测试 HTML 到 Markdown 转换"""
        html = """
        <h1>Main Title</h1>
        <p>This is a <strong>bold</strong> paragraph with a <a href="https://example.com">link</a>.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        """
        
        markdown = self.web_fetch_tool._convert_html_to_markdown(html)
        
        self.assertIn("# Main Title", markdown)
        self.assertIn("**bold**", markdown)
        self.assertIn("[link](https://example.com)", markdown)
        self.assertIn("* Item 1", markdown)
        self.assertIn("* Item 2", markdown)
    
    def test_cache_functionality(self):
        """测试缓存功能"""
        tool = self.web_fetch_tool
        url = "https://example.com"
        content = "<html><body>Test</body></html>"
        
        # 设置缓存
        tool._set_cache(url, content)
        
        # 获取缓存
        cached_content = tool._get_from_cache(url)
        self.assertEqual(cached_content, content)
        
        # 测试缓存过期
        # 修改缓存时间戳使其过期
        tool._cache[url] = (content, time.time() - tool.CACHE_DURATION - 1)
        cached_content = tool._get_from_cache(url)
        self.assertIsNone(cached_content)
    
    def test_cache_cleanup(self):
        """测试缓存清理"""
        tool = self.web_fetch_tool
        
        # 添加过期的缓存项
        old_time = time.time() - tool.CACHE_DURATION - 1
        tool._cache["old_url"] = ("old_content", old_time)
        tool._cache["new_url"] = ("new_content", time.time())
        
        # 清理缓存
        tool._clean_cache()
        
        self.assertNotIn("old_url", tool._cache)
        self.assertIn("new_url", tool._cache)
    
    @patch('aiohttp.ClientSession.get')
    def test_fetch_content_success(self, mock_get):
        """测试成功获取内容"""
        async def run_test():
            # Mock 响应
            mock_response = AsyncMock()
            mock_response.ok = True
            mock_response.status = 200
            mock_response.headers = {
                'content-type': 'text/html; charset=utf-8',
                'content-length': '100'
            }
            mock_response.read.return_value = b'<html><body>Test</body></html>'
            
            mock_get.return_value.__aenter__.return_value = mock_response
            
            content, content_type = await self.web_fetch_tool._fetch_content(
                "https://example.com", 30
            )
            
            self.assertEqual(content, '<html><body>Test</body></html>')
            self.assertEqual(content_type, 'text/html; charset=utf-8')
        
        asyncio.run(run_test())
    
    @patch('aiohttp.ClientSession.get')
    def test_fetch_content_error(self, mock_get):
        """测试获取内容错误"""
        async def run_test():
            # Mock 错误响应
            mock_response = AsyncMock()
            mock_response.ok = False
            mock_response.status = 404
            mock_response.request_info = Mock()
            mock_response.history = []
            
            mock_get.return_value.__aenter__.return_value = mock_response
            
            with self.assertRaises(aiohttp.ClientResponseError):
                await self.web_fetch_tool._fetch_content("https://example.com", 30)
        
        asyncio.run(run_test())
    
    def test_invalid_url_error(self):
        """测试无效 URL 错误"""
        async def run_test():
            result = await self.web_fetch_tool.execute({
                "url": "invalid-url",
                "format": "text"
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "validation_error")
            self.assertIn("URL 必须以", result.output)
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.WebFetchTool._fetch_content')
    def test_successful_execution_text_format(self, mock_fetch):
        """测试成功执行 - 文本格式"""
        async def run_test():
            # Mock 获取内容
            mock_fetch.return_value = (
                '<html><body><h1>Test</h1><p>Content</p></body></html>',
                'text/html'
            )
            
            result = await self.web_fetch_tool.execute({
                "url": "https://example.com",
                "format": "text"
            }, self.context)
            
            self.assertIn("Test", result.output)
            self.assertIn("Content", result.output)
            self.assertEqual(result.metadata["format"], "text")
            self.assertEqual(result.metadata["url"], "https://example.com")
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.WebFetchTool._fetch_content')
    def test_successful_execution_markdown_format(self, mock_fetch):
        """测试成功执行 - Markdown 格式"""
        async def run_test():
            mock_fetch.return_value = (
                '<html><body><h1>Test</h1><p>Content</p></body></html>',
                'text/html'
            )
            
            result = await self.web_fetch_tool.execute({
                "url": "https://example.com",
                "format": "markdown"
            }, self.context)
            
            self.assertIn("# Test", result.output)
            self.assertEqual(result.metadata["format"], "markdown")
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.WebFetchTool._fetch_content')
    def test_successful_execution_html_format(self, mock_fetch):
        """测试成功执行 - HTML 格式"""
        async def run_test():
            html_content = '<html><body><h1>Test</h1></body></html>'
            mock_fetch.return_value = (html_content, 'text/html')
            
            result = await self.web_fetch_tool.execute({
                "url": "https://example.com",
                "format": "html"
            }, self.context)
            
            self.assertEqual(result.output, html_content)
            self.assertEqual(result.metadata["format"], "html")
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.WebFetchTool._fetch_content')
    def test_non_html_content(self, mock_fetch):
        """测试非 HTML 内容"""
        async def run_test():
            json_content = '{"key": "value"}'
            mock_fetch.return_value = (json_content, 'application/json')
            
            result = await self.web_fetch_tool.execute({
                "url": "https://api.example.com/data.json",
                "format": "text"
            }, self.context)
            
            self.assertEqual(result.output, json_content)
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.WebFetchTool._fetch_content')
    def test_cache_usage(self, mock_fetch):
        """测试缓存使用"""
        async def run_test():
            html_content = '<html><body>Cached Content</body></html>'
            mock_fetch.return_value = (html_content, 'text/html')
            
            # 第一次调用
            result1 = await self.web_fetch_tool.execute({
                "url": "https://example.com",
                "format": "text"
            }, self.context)
            
            # 第二次调用应该使用缓存
            result2 = await self.web_fetch_tool.execute({
                "url": "https://example.com",
                "format": "text"
            }, self.context)
            
            # 验证只调用了一次 fetch_content
            self.assertEqual(mock_fetch.call_count, 1)
            self.assertTrue(result2.metadata["cached"])
        
        asyncio.run(run_test())
    
    def test_tool_to_dict(self):
        """测试工具转换为字典"""
        tool_dict = self.web_fetch_tool.to_dict()
        
        self.assertEqual(tool_dict["name"], "webfetch")
        self.assertIn("description", tool_dict)
        self.assertIn("parameters", tool_dict)
        
        params = tool_dict["parameters"]
        self.assertIn("url", params["properties"])
        self.assertIn("format", params["properties"])
        self.assertIn("timeout", params["properties"])


class TestWebSearchTool(unittest.TestCase):
    """WebSearchTool 测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.web_search_tool = WebSearchTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
    
    def test_tool_basic_properties(self):
        """测试工具基本属性"""
        self.assertEqual(self.web_search_tool.name, "websearch")
        self.assertGreater(len(self.web_search_tool.description), 0)
        self.assertIn("DuckDuckGo", self.web_search_tool.description)
        self.assertIn("搜索", self.web_search_tool.description)
    
    def test_parameters_schema(self):
        """测试参数模式"""
        schema = self.web_search_tool.get_parameters_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("query", schema["properties"])
        self.assertIn("max_results", schema["properties"])
        self.assertIn("region", schema["properties"])
        self.assertIn("safesearch", schema["properties"])
        self.assertIn("timelimit", schema["properties"])
        
        # 验证枚举值
        safesearch_enum = schema["properties"]["safesearch"]["enum"]
        self.assertEqual(set(safesearch_enum), {"on", "moderate", "off"})
        
        timelimit_enum = schema["properties"]["timelimit"]["enum"]
        self.assertEqual(set(timelimit_enum), {"d", "w", "m", "y"})
        
        required = set(schema["required"])
        self.assertEqual(required, {"query"})
    
    def test_format_search_results(self):
        """测试搜索结果格式化"""
        results = [
            {
                'title': 'Test Result 1',
                'href': 'https://example.com/1',
                'body': 'This is the first test result.'
            },
            {
                'title': 'Test Result 2',
                'href': 'https://example.com/2',
                'body': 'This is the second test result.'
            }
        ]
        
        formatted = self.web_search_tool._format_search_results(results)
        
        self.assertIn("**1. Test Result 1**", formatted)
        self.assertIn("**2. Test Result 2**", formatted)
        self.assertIn("https://example.com/1", formatted)
        self.assertIn("https://example.com/2", formatted)
        self.assertIn("This is the first test result.", formatted)
        self.assertIn("This is the second test result.", formatted)
    
    def test_format_empty_results(self):
        """测试空搜索结果格式化"""
        formatted = self.web_search_tool._format_search_results([])
        self.assertEqual(formatted, "未找到相关搜索结果。")
    
    def test_format_incomplete_results(self):
        """测试不完整搜索结果格式化"""
        results = [
            {
                'href': 'https://example.com',
                # 缺少 title 和 body
            }
        ]
        
        formatted = self.web_search_tool._format_search_results(results)
        
        self.assertIn("**1. 无标题**", formatted)
        self.assertIn("https://example.com", formatted)
        self.assertIn("无描述", formatted)
    
    def test_empty_query_error(self):
        """测试空查询错误"""
        async def run_test():
            result = await self.web_search_tool.execute({
                "query": ""
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "empty_query")
            self.assertIn("不能为空", result.output)
        
        asyncio.run(run_test())
    
    def test_whitespace_only_query_error(self):
        """测试仅空白字符查询错误"""
        async def run_test():
            result = await self.web_search_tool.execute({
                "query": "   \t\n   "
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "empty_query")
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.DDGS')
    def test_successful_search(self, mock_ddgs_class):
        """测试成功搜索"""
        async def run_test():
            # Mock DDGS 实例
            mock_ddgs = Mock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            
            # Mock 搜索结果
            mock_results = [
                {
                    'title': 'Python Programming',
                    'href': 'https://python.org',
                    'body': 'Official Python website'
                },
                {
                    'title': 'Python Tutorial',
                    'href': 'https://docs.python.org/tutorial',
                    'body': 'Learn Python programming'
                }
            ]
            mock_ddgs.text.return_value = mock_results
            
            result = await self.web_search_tool.execute({
                "query": "Python programming",
                "max_results": 10
            }, self.context)
            
            self.assertIn("Python Programming", result.output)
            self.assertIn("Python Tutorial", result.output)
            self.assertIn("https://python.org", result.output)
            self.assertEqual(result.metadata["results_count"], 2)
            self.assertEqual(result.metadata["query"], "Python programming")
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.DDGS')
    def test_no_results_found(self, mock_ddgs_class):
        """测试未找到搜索结果"""
        async def run_test():
            mock_ddgs = Mock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = []
            
            result = await self.web_search_tool.execute({
                "query": "very specific query with no results"
            }, self.context)
            
            self.assertEqual(result.metadata["results_count"], 0)
            self.assertIn("未找到相关搜索结果", result.output)
            self.assertIn("尝试使用不同的关键词", result.output)
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.DDGS')
    def test_search_with_all_parameters(self, mock_ddgs_class):
        """测试使用所有参数的搜索"""
        async def run_test():
            mock_ddgs = Mock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {
                    'title': 'Test Result',
                    'href': 'https://example.com',
                    'body': 'Test description'
                }
            ]
            
            result = await self.web_search_tool.execute({
                "query": "test query",
                "max_results": 5,
                "region": "us-en",
                "safesearch": "on",
                "timelimit": "w"
            }, self.context)
            
            # 验证调用参数
            mock_ddgs.text.assert_called_once_with(
                "test query",
                region="us-en",
                safesearch="on",
                max_results=5,
                timelimit="w"
            )
            
            self.assertEqual(result.metadata["region"], "us-en")
            self.assertEqual(result.metadata["safesearch"], "on")
            self.assertEqual(result.metadata["timelimit"], "w")
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.DDGS')
    def test_search_error_handling(self, mock_ddgs_class):
        """测试搜索错误处理"""
        async def run_test():
            mock_ddgs = Mock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.side_effect = Exception("Network error")
            
            result = await self.web_search_tool.execute({
                "query": "test query"
            }, self.context)
            
            self.assertEqual(result.metadata["error"], "search_error")
            self.assertIn("搜索过程中发生错误", result.output)
            self.assertIn("Network error", result.output)
        
        asyncio.run(run_test())
    
    @patch('tools.web_tools.DDGS')
    def test_raw_results_limit(self, mock_ddgs_class):
        """测试原始结果限制"""
        async def run_test():
            mock_ddgs = Mock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            
            # 创建10个搜索结果
            mock_results = [
                {
                    'title': f'Result {i}',
                    'href': f'https://example.com/{i}',
                    'body': f'Description {i}'
                }
                for i in range(10)
            ]
            mock_ddgs.text.return_value = mock_results
            
            result = await self.web_search_tool.execute({
                "query": "test query"
            }, self.context)
            
            # 原始结果应该限制为前5个
            self.assertEqual(len(result.metadata["raw_results"]), 5)
            self.assertEqual(result.metadata["results_count"], 10)
        
        asyncio.run(run_test())
    
    def test_tool_to_dict(self):
        """测试工具转换为字典"""
        tool_dict = self.web_search_tool.to_dict()
        
        self.assertEqual(tool_dict["name"], "websearch")
        self.assertIn("description", tool_dict)
        self.assertIn("parameters", tool_dict)
        
        params = tool_dict["parameters"]
        self.assertIn("query", params["properties"])
        self.assertIn("max_results", params["properties"])
        self.assertIn("region", params["properties"])
        self.assertIn("safesearch", params["properties"])
        self.assertIn("timelimit", params["properties"])


if __name__ == "__main__":
    unittest.main()
