"""
Simplified Tool Dispatcher
Removes URL-specific coupling and focuses on clean tool orchestration
"""

import logging
from typing import Dict, Any, Optional

from tools.file_tools import ReadTool, WriteTool
from tools.list_tool import ListTool
from tools.web_tools import WebFetchTool, WebSearchTool
from tools.bash import BashTool


class SimpleDispatcher:
    """
    Simplified dispatcher focusing on clean tool orchestration
    No hardcoded logic for specific task types
    """
    
    def __init__(self, max_file_size: int = 1024 * 1024):  # 1MB default
        # Initialize tool instances
        self.read_tool = ReadTool()
        self.write_tool = WriteTool()
        self.list_tool = ListTool()
        self.web_fetch_tool = WebFetchTool()
        self.web_search_tool = WebSearchTool()
        self.bash_tool = BashTool()
        self.max_file_size = max_file_size
        
        self.tools = {
            'read_file': 'read_file',
            'write_file': 'write_file',
            'list_files': 'list_files',
            'search': 'search',
            'get_url': 'get_url',
            'execute_bash': 'execute_bash'
        }
    
    def dispatch(self, tool_name: str, params: Dict[str, Any]) -> str:
        """
        Dispatch tool call - clean and simple
        Returns tool result as string
        """
        if tool_name not in self.tools:
            return f"Error: Unknown tool '{tool_name}'. Available tools: {list(self.tools.keys())}"
        
        try:
            # Map tool names to method calls
            if tool_name == 'read_file':
                result = self.read_tool.execute({"filePath": params.get('path', '')}, None)
                return str(result.content) if result.success else f"Error: {result.error}"
            elif tool_name == 'write_file':
                result = self.write_tool.execute({
                    "filePath": params.get('path', ''), 
                    "content": params.get('content', '')
                }, None)
                return str(result.content) if result.success else f"Error: {result.error}"
            elif tool_name == 'list_files':
                result = self.list_tool.execute({"path": params.get('path', '.')}, None)
                return str(result.content) if result.success else f"Error: {result.error}"
            elif tool_name == 'search':
                result = self.web_search_tool.execute({"query": params.get('query', '')}, None)
                return str(result.content) if result.success else f"Error: {result.error}"
            elif tool_name == 'get_url':
                result = self.web_fetch_tool.execute({"url": params.get('url', '')}, None)
                return str(result.content) if result.success else f"Error: {result.error}"
            elif tool_name == 'execute_bash':
                result = self.bash_tool.execute({"command": params.get('command', '')}, None)
                return str(result.content) if result.success else f"Error: {result.error}"
            else:
                return f"Error: Tool method not implemented for '{tool_name}'"
                
        except Exception as e:
            logging.error(f"Tool execution error for {tool_name}: {e}")
            return f"Tool execution failed: {e}"
    
    def get_tool_info(self) -> Dict[str, str]:
        """Get information about available tools with size limits"""
        max_size_mb = self.max_file_size / (1024 * 1024)
        return {
            'read_file': f'Read content from a file (max {max_size_mb:.1f}MB). Params: {{path: string}}',
            'write_file': f'Write content to a file (max {max_size_mb:.1f}MB). Params: {{path: string, content: string}}',
            'list_files': 'List files in a directory. Params: {path: string}',
            'search': 'Search the web. Params: {query: string}',
            'get_url': f'Fetch content from URL (max {max_size_mb:.1f}MB). Params: {{url: string}}',
            'execute_bash': 'Execute bash command. Params: {command: string}'
        }