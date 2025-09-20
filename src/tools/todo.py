from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json
from .base_tool import BaseTool, ToolContext, ToolResult


@dataclass
class TodoInfo:
    """待办事项信息"""
    content: str  # 任务的简要描述
    status: str   # 当前状态: pending, in_progress, completed, cancelled
    id: str       # 唯一标识符
    priority: Optional[str] = "medium"  # 优先级: high, medium, low


class TodoState:
    """全局待办事项状态管理"""
    _instance = None
    _todos: Dict[str, List[TodoInfo]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_todos(self, session_id: str) -> List[TodoInfo]:
        """获取指定会话的待办事项"""
        return self._todos.get(session_id, [])
    
    def set_todos(self, session_id: str, todos: List[TodoInfo]):
        """设置指定会话的待办事项"""
        self._todos[session_id] = todos


class TodoWriteTool(BaseTool[Dict[str, List[Dict[str, str]]]]):
    """待办事项写入工具"""
    
    def __init__(self):
        description = """使用此工具为您的当前编码会话创建和管理一个结构化的任务列表。这能帮助您跟踪进度、组织复杂任务，并向用户展示工作的周密性。
它还能帮助用户了解任务的进展以及他们请求的总体进度。

## 何时使用此工具

在以下场景中主动使用此工具：

1.  **复杂的多步骤任务** - 当一项任务需要3个或更多不同的步骤或操作时。
2.  **不简单且复杂的任务** - 需要仔细规划或多个操作的任务。
3.  **用户明确要求待办事项列表** - 当用户直接要求您使用待办事项列表时。
4.  **用户提供多个任务** - 当用户提供一个待办事项清单时（无论是编号的还是用逗号分隔的）。
5.  **收到新指令后** - 立即将用户需求捕获为待办事项。可以根据新信息随时编辑待办事项列表。
6.  **完成一项任务后** - 将其标记为完成，并添加任何新的后续任务。
7.  **当您开始处理一项新任务时** - 将该待办事项标记为 `in_progress`（进行中）。理想情况下，您一次只应有一个待办事项处于 `in_progress` 状态。在开始新任务前，请先完成现有任务。

## 何时不应使用此工具

在以下情况中，请不要使用此工具：

1.  只有一个单一、直接的任务。
2.  任务非常琐碎，跟踪它没有组织上的好处。
3.  任务可以在少于3个简单步骤内完成。
4.  任务纯粹是对话性或信息性的。

请注意，如果只有一个琐碎的任务要做，您不应该使用此工具。在这种情况下，最好直接执行该任务。

## 使用待办事项列表的示例

<example>
User: 我想在应用程序设置中添加一个暗黑模式切换开关。完成后请确保运行测试和构建！
Assistant: 我来帮您在应用程序设置中添加暗黑模式切换开关。让我创建一个待办事项列表来跟踪这次实现。
*创建包含以下项目的待办事项列表：*

1.  在“设置”页面中创建暗黑模式切换组件
2.  添加暗黑模式的状态管理（context/store）
3.  为暗黑主题实现 CSS-in-JS 样式
4.  更新现有组件以支持主题切换
5.  运行测试和构建流程，解决出现的任何失败或错误
    *开始处理第一个任务*

<reasoning>
**原因：**
助手使用待办事项列表是因为：

1.  添加暗黑模式是一个多步骤的功能，需要UI、状态管理和样式更改。
2.  用户明确要求之后要运行测试和构建。
3.  助手推断出测试和构建需要成功，因此将“确保测试和构建成功”作为最后一项任务。
</reasoning>
</example>

User: 我需要为我的电商网站实现这些功能：用户注册、产品目录、购物车和结账流程。
Assistant: 我来帮您实现这些功能。首先，让我们把所有功能添加到待办事项列表中。
*创建一个待办事项列表，根据项目架构将每个功能分解为具体任务*
Assistant: 让我们从用户注册开始。这将涉及创建数据库模型、API端点以及与您现有认证系统集成的前端表单。

<reasoning>
**原因：**
助手使用待办事项列表是因为：

1.  用户以逗号分隔的列表形式提供了多个要实现的复杂功能。
2.  待办事项列表有助于将这些大型功能组织成可管理的任务。
3.  这种方法可以跟踪整个实现过程的进度。
</reasoning>
</example>

## 不使用待办事项列表的示例

<example>
User: 如何用 Python 打印 'Hello World'？
Assistant: 在 Python 中，您可以用这行简单的代码打印 "Hello World"：

```python
print("Hello World")
```

执行时，这将在控制台输出 "Hello World" 这段文本。

<reasoning>
**原因：**
助手没有使用待办事项列表，因为这是一个单一、琐碎的任务，一步即可完成。对于如此直接的请求，无需跟踪多个任务或步骤。
</reasoning>
</example>

<example>
User: `git status` 命令是做什么的？
Assistant: `git status` 命令显示您工作目录和暂存区的当前状态。它会列出哪些更改已被暂存，哪些尚未暂存，以及哪些文件未被 Git 跟踪。这是在进行提交前了解仓库当前状态的一个基本命令。

<reasoning>
**原因：**
助手没有使用待办事项列表，因为这是一个信息性请求，没有实际的编码任务需要完成。用户只是在寻求解释，而不是要求助手执行多个步骤或任务。
</reasoning>
</example>


## 任务状态与管理

1.  **任务状态**：使用这些状态来跟踪进度：
      - `pending`：任务尚未开始
      - `in_progress`：当前正在处理（一次限制为一个任务）
      - `completed`：任务成功完成
      - `cancelled`：任务不再需要

2.  **任务管理**：
      - 在工作时实时更新任务状态。
      - 完成任务后立即将其标记为完成（不要批量完成）。
      - 任何时候只保持一个任务处于 `in_progress` 状态。
      - 在开始新任务前先完成当前任务。
      - 取消变得无关紧要的任务。

3.  **任务分解**：
      - 创建具体、可操作的项目。
      - 将复杂的任务分解为更小、可管理的步骤。
      - 使用清晰、描述性的任务名称。

如有疑问，就使用此工具。主动进行任务管理能表现出您的专注度，并确保您成功完成所有需求。"""
        
        super().__init__("todowrite", description)
        self.state = TodoState()
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "更新的待办事项列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "任务的简要描述"
                            },
                            "status": {
                                "type": "string",
                                "description": "任务的当前状态: pending, in_progress, completed, cancelled"
                            },
                            "id": {
                                "type": "string", 
                                "description": "待办事项的唯一标识符"
                            },
                            "priority": {
                                "type": "string",
                                "description": "任务的优先级: high, medium, low",
                                "default": "medium"
                            }
                        },
                        "required": ["content", "status", "id"]
                    }
                }
            },
            "required": ["todos"]
        }
    
    async def execute(self, params: Dict[str, List[Dict[str, str]]], context: ToolContext) -> ToolResult:
        """执行待办事项写入"""
        todos_data = params["todos"]
        todos = [TodoInfo(**todo_data) for todo_data in todos_data]
        
        self.state.set_todos(context.session_id, todos)
        
        active_count = len([t for t in todos if t.status != "completed"])
        
        return ToolResult(
            title=f"{active_count} todos",
            output=json.dumps([asdict(todo) for todo in todos], indent=2, ensure_ascii=False),
            metadata={"todos": [asdict(todo) for todo in todos]}
        )


class TodoReadTool(BaseTool[Dict[str, Any]]):
    """待办事项读取工具"""
    
    def __init__(self):
        description = """使用此工具读取会话的当前待办事项列表。应该主动且频繁地使用此工具，以确保您了解当前任务列表的状态。您应该尽可能经常使用此工具，特别是在以下情况下：
- 在对话开始时查看待处理的事项
- 在开始新任务之前确定工作优先级
- 当用户询问以前的任务或计划时
- 当您不确定下一步要做什么时
- 完成任务后更新您对剩余工作的理解
- 每隔几条消息后确保您在正确的轨道上

用法：
- 此工具不接受参数。所以输入留空。不要包含虚拟对象、占位符字符串或"input"或"empty"等键。留空即可
- 返回带有状态、优先级和内容的待办事项列表
- 使用此信息跟踪进度并规划下一步
- 如果尚不存在待办事项，将返回空列表"""
        
        super().__init__("todoread", description)
        self.state = TodoState()
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行待办事项读取"""
        todos = self.state.get_todos(context.session_id)
        active_count = len([t for t in todos if t.status != "completed"])
        
        return ToolResult(
            title=f"{active_count} todos",
            output=json.dumps([asdict(todo) for todo in todos], indent=2, ensure_ascii=False),
            metadata={"todos": [asdict(todo) for todo in todos]}
        )
