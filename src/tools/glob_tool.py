from .base_tool import BaseTool
import glob
import os

class GlobTool(BaseTool):
    """文件模式匹配工具"""
    
    def __init__(self):
        super().__init__()
        self.name = "glob_tool"
        self.description = "使用glob模式匹配文件路径"
    
    def execute(self, pattern: str, root_dir: str = None) -> list:
        """
        执行glob模式匹配
        
        Args:
            pattern: glob模式，如 "*.py" 或 "**/*.txt"
            root_dir: 搜索的根目录，默认为当前目录
            
        Returns:
            匹配的文件路径列表
        """
        try:
            if root_dir:
                search_path = os.path.join(root_dir, pattern)
            else:
                search_path = pattern
            
            matches = glob.glob(search_path, recursive=True)
            return matches
        except Exception as e:
            return [f"错误: {str(e)}"]