from .base_tool import BaseTool
from typing import List, Dict, Any
import json
import os

class TodoTool(BaseTool):
    """待办事项管理工具"""
    
    def __init__(self, todo_file: str = "todos.json"):
        super().__init__()
        self.name = "todo_tool"
        self.description = "管理待办事项列表"
        self.todo_file = todo_file
        self.todos = self._load_todos()
    
    def _load_todos(self) -> List[Dict[str, Any]]:
        """从文件加载待办事项"""
        if os.path.exists(self.todo_file):
            try:
                with open(self.todo_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_todos(self):
        """保存待办事项到文件"""
        with open(self.todo_file, 'w', encoding='utf-8') as f:
            json.dump(self.todos, f, ensure_ascii=False, indent=2)
    
    def add_todo(self, title: str, description: str = "", priority: str = "medium") -> str:
        """添加新的待办事项"""
        todo = {
            "id": len(self.todos) + 1,
            "title": title,
            "description": description,
            "priority": priority,
            "status": "pending",
            "created_at": self._get_timestamp()
        }
        self.todos.append(todo)
        self._save_todos()
        return f"已添加待办事项: {title}"
    
    def complete_todo(self, todo_id: int) -> str:
        """标记待办事项为完成"""
        for todo in self.todos:
            if todo["id"] == todo_id:
                todo["status"] = "completed"
                todo["completed_at"] = self._get_timestamp()
                self._save_todos()
                return f"已完成待办事项: {todo['title']}"
        return f"未找到ID为 {todo_id} 的待办事项"
    
    def list_todos(self, status: str = "all") -> List[Dict[str, Any]]:
        """列出待办事项"""
        if status == "all":
            return self.todos
        return [todo for todo in self.todos if todo["status"] == status]
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()