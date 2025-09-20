import asyncio
import uuid
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from .base_tool import BaseTool, ToolContext, ToolResult


@dataclass
class AgentConfig:
    """代理配置"""
    name: str
    description: str
    mode: str = "secondary"
    tools: Dict[str, bool] = field(default_factory=dict)
    model_id: Optional[str] = None
    provider_id: Optional[str] = None


@dataclass
class TaskSession:
    """任务会话"""
    id: str
    description: str
    agent: str
    status: str = "running"  # running, completed, failed, aborted
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskManager:
    """任务管理器 - 单例模式"""
    _instance = None
    _sessions: Dict[str, TaskSession] = {}
    _agents: List[AgentConfig] = []
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register_agent(self, agent: AgentConfig):
        """注册代理"""
        # 避免重复注册
        for existing in self._agents:
            if existing.name == agent.name:
                return
        self._agents.append(agent)
    
    def get_agents(self) -> List[AgentConfig]:
        """获取所有非主要代理"""
        return [agent for agent in self._agents if agent.mode != "primary"]
    
    def get_agent(self, name: str) -> Optional[AgentConfig]:
        """根据名称获取代理"""
        for agent in self._agents:
            if agent.name == name:
                return agent
        return None
    
    def create_session(self, parent_session_id: str, description: str, agent_name: str) -> TaskSession:
        """创建任务会话"""
        session_id = f"task_{uuid.uuid4().hex[:8]}"
        session = TaskSession(
            id=session_id,
            description=description,
            agent=agent_name
        )
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[TaskSession]:
        """获取会话"""
        return self._sessions.get(session_id)
    
    def abort_session(self, session_id: str):
        """中止会话"""
        session = self._sessions.get(session_id)
        if session:
            session.status = "aborted"


class TaskTool(BaseTool[Dict[str, Any]]):
    """任务工具 - 启动新代理处理复杂的多步骤任务"""
    
    def __init__(self):
        # 注册一些默认代理
        task_manager = TaskManager()
        
        # 代码审查代理
        task_manager.register_agent(AgentConfig(
            name="code_reviewer",
            description="用于审查代码质量、发现潜在问题和建议改进的代理",
            tools={"read": True, "grep": True, "bash": False}
        ))
        
        # 文件搜索代理
        task_manager.register_agent(AgentConfig(
            name="file_searcher", 
            description="专门用于搜索和分析文件内容的代理",
            tools={"read": True, "grep": True, "glob": True, "bash": False}
        ))
        
        # 测试生成代理
        task_manager.register_agent(AgentConfig(
            name="test_generator",
            description="用于生成单元测试和集成测试的代理",
            tools={"read": True, "write": True, "bash": True}
        ))
        
        # 文档生成代理
        task_manager.register_agent(AgentConfig(
            name="doc_generator",
            description="用于生成和维护项目文档的代理",
            tools={"read": True, "write": True, "grep": True}
        ))
        
        # 重构代理
        task_manager.register_agent(AgentConfig(
            name="refactor_agent",
            description="用于代码重构和优化的代理",
            tools={"read": True, "edit": True, "grep": True, "bash": True}
        ))
        
        agents = task_manager.get_agents()
        agents_description = "\n".join([
            f"- {agent.name}: {agent.description}"
            for agent in agents
        ])
        
        description = f"""启动新代理以自主处理复杂的多步骤任务。

可用的代理类型及其可访问的工具：
{agents_description}

使用 Task 工具时，您必须指定 subagent_type 参数来选择要使用的代理类型。

何时使用 Agent 工具：
- 当您被指示执行自定义斜杠命令时。使用 Agent 工具，将斜杠命令调用作为整个提示。斜杠命令可以接受参数。例如：Task(description="检查文件", prompt="/check-file path/to/file.py")

何时不使用 Agent 工具：
- 如果您想读取特定文件路径，请使用 Read 或 Glob 工具而不是 Agent 工具，以更快地找到匹配项
- 如果您正在搜索特定的类定义，如"class Foo"，请使用 Glob 工具，以更快地找到匹配项
- 如果您正在特定文件或 2-3 个文件集中搜索代码，请使用 Read 工具而不是 Agent 工具，以更快地找到匹配项
- 与上述代理描述无关的其他任务

使用说明：
1. 尽可能同时启动多个代理，以最大化性能；为此，请在单个消息中使用多个工具
2. 代理完成后，它将向您返回单个消息。代理返回的结果对用户不可见。要向用户显示结果，您应该向用户发送包含结果简明摘要的文本消息
3. 每次代理调用都是无状态的。您将无法向代理发送其他消息，代理也无法在其最终报告之外与您通信。因此，您的提示应包含代理自主执行的高度详细的任务描述，并且您应该准确指定代理应在其最终且唯一的消息中向您返回什么信息
4. 代理的输出通常应该被信任
5. 清楚地告诉代理您是期望它编写代码还是只做研究（搜索、文件读取、网络获取等），因为它不知道用户的意图
6. 如果代理描述提到应该主动使用它，那么您应该尽力使用它，而不必让用户首先要求它。运用您的判断"""
        
        super().__init__("task", description)
        self.task_manager = task_manager
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "任务的简短描述（3-5个词）"
                },
                "prompt": {
                    "type": "string",
                    "description": "代理要执行的任务"
                },
                "subagent_type": {
                    "type": "string",
                    "description": "用于此任务的专门代理类型",
                    "enum": [agent.name for agent in self.task_manager.get_agents()]
                }
            },
            "required": ["description", "prompt", "subagent_type"]
        }
    
    async def _simulate_agent_execution(self, agent: AgentConfig, prompt: str, session: TaskSession) -> str:
        """模拟代理执行 - 在实际实现中，这里会调用真正的 AI 代理"""
        # 这是一个模拟实现，实际应用中需要集成真正的 AI 模型
        
        if agent.name == "code_reviewer":
            return f"""代码审查完成。

审查内容：{prompt[:100]}...

发现的问题：
1. 建议添加更多错误处理
2. 可以优化性能
3. 需要添加单元测试

总体评价：代码结构良好，但需要一些改进。"""
        
        elif agent.name == "file_searcher":
            return f"""文件搜索完成。

搜索任务：{prompt[:100]}...

找到的相关文件：
1. src/main.py - 主要逻辑
2. tests/test_main.py - 测试文件
3. docs/README.md - 文档

搜索结果：找到 3 个相关文件，包含目标内容。"""
        
        elif agent.name == "test_generator":
            return f"""测试生成完成。

目标：{prompt[:100]}...

生成的测试：
- 单元测试：5 个测试用例
- 集成测试：2 个测试场景
- 边界条件测试：3 个测试

所有测试已生成并可以运行。"""
        
        elif agent.name == "doc_generator":
            return f"""文档生成完成。

任务：{prompt[:100]}...

生成的文档：
- API 文档
- 使用指南
- 示例代码

文档已更新并符合项目标准。"""
        
        elif agent.name == "refactor_agent":
            return f"""重构完成。

重构任务：{prompt[:100]}...

执行的重构：
1. 提取公共方法
2. 优化数据结构
3. 改进命名约定

重构后代码更清晰，性能提升 15%。"""
        
        else:
            return f"""任务完成。

执行的任务：{prompt[:100]}...

结果：任务已按要求完成。"""
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行任务调度"""
        description = params["description"]
        prompt = params["prompt"]
        subagent_type = params["subagent_type"]
        
        # 获取指定的代理
        agent = self.task_manager.get_agent(subagent_type)
        if not agent:
            return ToolResult(
                title="错误: 未知代理类型",
                output=f"未知的代理类型: {subagent_type} 不是有效的代理类型",
                metadata={
                    "error": "unknown_agent_type",
                    "requested_type": subagent_type,
                    "available_types": [a.name for a in self.task_manager.get_agents()]
                }
            )
        
        # 创建任务会话
        session = self.task_manager.create_session(
            parent_session_id=context.session_id,
            description=description,
            agent_name=agent.name
        )
        
        try:
            # 模拟代理执行
            result_text = await self._simulate_agent_execution(agent, prompt, session)
            
            # 更新会话状态
            session.status = "completed"
            session.messages.append({
                "role": "assistant",
                "content": result_text,
                "timestamp": "2024-01-01T00:00:00Z"  # 在实际实现中使用真实时间戳
            })
            
            # 构建工具摘要（模拟）
            tool_summary = [
                {
                    "id": f"tool_{uuid.uuid4().hex[:8]}",
                    "type": "tool",
                    "name": "simulated_execution",
                    "status": "completed"
                }
            ]
            
            return ToolResult(
                title=description,
                output=result_text,
                metadata={
                    "session_id": session.id,
                    "agent": agent.name,
                    "summary": tool_summary,
                    "status": session.status
                }
            )
            
        except Exception as e:
            # 处理执行错误
            session.status = "failed"
            
            return ToolResult(
                title=f"任务失败: {description}",
                output=f"代理执行失败: {str(e)}",
                metadata={
                    "session_id": session.id,
                    "agent": agent.name,
                    "error": str(e),
                    "status": "failed"
                }
            )
