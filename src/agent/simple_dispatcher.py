"""
Simplified Tool Dispatcher
Removes URL-specific coupling and focuses on clean tool orchestration
"""

import logging
from typing import Dict, Any, Optional

from tools.un_file_system import FileSystem
from tools.un_web import WebTools
from tools.un_bash import BashTools


class SimpleDispatcher:
    """
    Simplified dispatcher focusing on clean tool orchestration
    No hardcoded logic for specific task types
    """
    
    def __init__(self, max_file_size: int = 1024 * 1024):  # 1MB default
        # Initialize tool instances with 1MB limits
        self.file_system = FileSystem(max_file_size=max_file_size)
        self.web = WebTools(max_content_size=max_file_size)
        self.bash = BashTools()
        self.max_file_size = max_file_size
        
        self.tools = {
            'read_file': self.file_system,
            'write_file': self.file_system,
            'list_files': self.file_system,
            'search': self.web,
            'get_url': self.web,
            'execute_bash': self.bash
        }
    
    def dispatch(self, tool_name: str, params: Dict[str, Any]) -> str:
        """
        Dispatch tool call - clean and simple
        Returns tool result as string
        """
        if tool_name not in self.tools:
            return f"Error: Unknown tool '{tool_name}'. Available tools: {list(self.tools.keys())}"
        
        try:
            tool = self.tools[tool_name]
            
            # Map tool names to method calls
            if tool_name == 'read_file':
                return self.file_system.read_file(params.get('path', ''))
            elif tool_name == 'write_file':
                return self.file_system.write_file(params.get('path', ''), params.get('content', ''))
            elif tool_name == 'list_files':
                return self.file_system.list_files(params.get('path', '.'))
            elif tool_name == 'search':
                return self.web.search(params.get('query', ''))
            elif tool_name == 'get_url':
                return self.web.get_url(params.get('url', ''))
            elif tool_name == 'execute_bash':
                return self.bash.execute_bash(params.get('command', ''))
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