import unittest
import sys
import os
import asyncio

if __name__ == "__main__":
    # success = run_todo_tests()
    # sys.exit(0 if success else 1)

    from tools.file_tools import ReadTool
    from tools.base_tool import ToolContext
    from tools.grep_tool import GrepTool
    from tools.web_tools import WebFetchTool, WebSearchTool
    from tools import ToolRegistry
    
    async def test_read_tool():
        """测试文件读取工具"""
        tool = ReadTool()
        context = ToolContext(session_id="test_session", message_id="test_msg", agent="test_agent")
        
        try:
            result = await tool.execute({
                "filePath": "/Users/xushun/Devp/learning/llm/agent/creative-agent/tools/file_tools.py",
                "offset": 0,
                "limit": 1000  # 只读取前10行进行测试
            }, context)
            
            print(f"工具执行成功:")
            print(f"标题: {result.title}")
            print(f"输出: {result.output[:200000]}...")  # 只显示前200个字符
            print(f"metadata: {result.metadata}")
            print(f"metadata preview: {result.metadata['preview']}")
            
        except Exception as e:
            print(f"工具执行失败: {e}")

    async def test_grep_tool():
        """测试grep工具"""
        tool = GrepTool()
        context = ToolContext(session_id="test_session", message_id="test_msg", agent="test_agent")
        
        try:
            result = await tool.execute({
                "pattern": "params",
                "path": "/Users/xushun/Devp/learning/llm/agent/creative-agent/tools/grep_tool.py"
            }, context)
            
            print(f"工具执行成功:")
            print(f"标题: {result.title}")
            print(f"输出: {result.output[:200000]}...")  # 只显示前200个字符
            print(f"metadata: {result.metadata}")
        except Exception as e:
            print(f"工具执行失败: {e}")

    async def test_web_fetch_tool():
        """测试web获取工具"""
        tool = WebFetchTool()
        context = ToolContext(session_id="test_session", message_id="test_msg", agent="test_agent")
        
        try:
            result = await tool.execute({
                "url": "https://minusx.ai/blog/decoding-claude-code/#how-to-build-a-claude-code-like-agent-tldr",
                "format": "text"
            }, context)
            print(f"工具执行成功:")
            print(f"标题: {result.title}")
            print(f"输出: {result.output[:200000]}...")  # 只显示前200000个字符
            print(f"metadata: {result.metadata}")
        except Exception as e:
            print(f"工具执行失败: {e}")

    async def test_web_search_tool():
        """测试web搜索工具"""
        tool = WebSearchTool()
        context = ToolContext(session_id="test_session", message_id="test_msg", agent="test_agent")
        
        try:
            result = await tool.execute({
                "query": "ai agent",
                "max_results": 10
            }, context)
            print(f"工具执行成功:")
            print(f"标题: {result.title}")
            print(f"输出: {result.output[:2000]}...") 
            print(f"metadata: {result.metadata}")
        except Exception as e:
            print(f"工具执行失败: {e}")

    async def test_tool_registry():
        """测试工具注册表"""
        registry = ToolRegistry()
        tools = registry.get_tools_dict()
        # 对tools json 格式化输出，保持中文内容
        import json
        print(f"工具注册表: {json.dumps(tools, indent=4, ensure_ascii=False)}")

    async def run_all_tests():
        # await test_read_tool()
        # await test_grep_tool()
        # await test_web_fetch_tool()
        # await test_web_search_tool()
        await test_tool_registry()

    # 运行异步测试
    asyncio.run(run_all_tests())
    # asyncio.run(test_grep_tool())
