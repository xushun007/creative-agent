"""TaskTool - 启动子代理处理复杂任务"""

import asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path

from .base_tool import BaseTool, ToolContext, ToolResult
from .task_manager import TaskManager, SubagentConfig
from .task_prompts import get_subagent_prompt
from core.agents import AgentRegistry

try:
    from utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TaskTool(BaseTool[Dict[str, Any]]):
    """任务工具 - 启动子代理处理复杂的多步骤任务"""
    
    def __init__(self, main_config=None):
        """初始化任务工具
        
        Args:
            main_config: 主 Session 的配置，用于创建子 Session
        """
        self.main_config = main_config
        self.task_manager = TaskManager()
        self.agent_registry = AgentRegistry.get_instance()
        
        # 构建工具描述（使用 AgentRegistry 的子代理）
        subagents = self.agent_registry.list_agents(mode="subagent")
        subagents_desc = "\n".join([
            f"- {agent.name}: {agent.description}"
            for agent in subagents
        ])
        
        description = f"""启动子代理以自主处理复杂的多步骤任务。

可用的子代理类型及其用途：
{subagents_desc}

使用 Task 工具时，您必须指定 subagent_type 参数来选择要使用的子代理类型。

何时使用 Task 工具：
- 需要制定技术方案或实施计划时，使用 plan 子代理
- 需要完成复杂的多步骤编程任务时，使用 general 子代理
- 需要快速探索和理解代码库结构时，使用 explore 子代理

何时不使用 Task 工具：
- 简单的文件读取或搜索，直接使用 read/grep 工具更快
- 单一明确的操作，不需要多步骤推理
- 可以直接完成的任务

使用说明：
1. 子代理在独立的会话中运行，与主代理完全隔离
2. 子代理完成后会返回单个结果消息
3. 在 task_prompt 中明确说明任务目标和期望输出
4. 子代理无法与你直接对话，所以提示要详细完整
5. 可以通过 context_files 参数传递相关文件路径给子代理"""
        
        super().__init__("task", description)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        subagents = self.agent_registry.list_agents(mode="subagent")
        subagent_names = [agent.name for agent in subagents]
        
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "任务的简短描述（3-5个词），用于日志和跟踪"
                },
                "task_prompt": {
                    "type": "string",
                    "description": "传递给子代理的详细任务描述。需要明确说明期望子代理做什么，以及期望的输出格式。"
                },
                "subagent_type": {
                    "type": "string",
                    "enum": subagent_names,
                    "description": f"子代理类型，可选值：{', '.join(subagent_names)}"
                },
                "context_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选。需要传递给子代理的文件路径列表。子代理启动时会自动读取这些文件。"
                }
            },
            "required": ["description", "task_prompt", "subagent_type"]
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行任务调度
        
        Args:
            params: 工具参数
                - description: 任务描述
                - task_prompt: 任务提示
                - subagent_type: 子代理类型
                - context_files: 可选的上下文文件列表
            context: 工具执行上下文
            
        Returns:
            工具执行结果
        """
        description = params["description"]
        task_prompt = params["task_prompt"]
        subagent_type = params["subagent_type"]
        context_files = params.get("context_files", [])
        
        # 从 AgentRegistry 获取子代理配置
        agent = self.agent_registry.get(subagent_type)
        if not agent:
            return ToolResult(
                title=f"未知的子代理类型: {subagent_type}",
                output=f"子代理类型 '{subagent_type}' 不存在。可用的子代理: {', '.join([a.name for a in self.agent_registry.list_agents(mode='subagent')])}",
                metadata={"error": "unknown_subagent_type"}
            )
        
        # 验证是 subagent
        if agent.mode != "subagent":
            return ToolResult(
                title=f"错误的代理类型: {subagent_type}",
                output=f"代理 '{subagent_type}' 的模式是 '{agent.mode}'，只能使用 'subagent' 类型的代理。",
                metadata={"error": "invalid_agent_mode"}
            )
        
        logger.info(f"TaskTool: 启动子代理 '{subagent_type}' 处理任务: {description}")
        
        # 1. 创建子代理会话记录
        sub_session = self.task_manager.create_session(
            parent_session_id=context.session_id,
            subagent_type=subagent_type,
            task_description=description
        )
        
        try:
            # 2. 执行子代理（使用 AgentInfo）
            result = await self._execute_subagent(
                agent=agent,
                task_prompt=task_prompt,
                parent_context=context,
                context_files=context_files,
                sub_session_id=sub_session.id
            )
            
            # 4. 更新会话状态
            self.task_manager.update_session_status(
                sub_session.id,
                status="completed",
                result=result
            )
            
            logger.info(f"TaskTool: 子代理 '{subagent_type}' 完成任务: {description}")
            
            return ToolResult(
                title=f"子代理任务完成: {description}",
                output=result,
                metadata={
                    "session_id": sub_session.id,
                    "subagent_type": subagent_type,
                    "status": "completed"
                }
            )
            
        except asyncio.TimeoutError:
            # 超时处理
            self.task_manager.update_session_status(
                sub_session.id,
                status="timeout",
                error="子代理执行超时"
            )
            
            logger.warning(f"TaskTool: 子代理 '{subagent_type}' 执行超时: {description}")
            
            return ToolResult(
                title=f"子代理任务超时: {description}",
                output="子代理执行超时，可能任务过于复杂或遇到了问题。",
                metadata={
                    "session_id": sub_session.id,
                    "subagent_type": subagent_type,
                    "status": "timeout"
                }
            )
            
        except Exception as e:
            # 错误处理
            error_msg = str(e)
            self.task_manager.update_session_status(
                sub_session.id,
                status="failed",
                error=error_msg
            )
            
            logger.error(f"TaskTool: 子代理 '{subagent_type}' 执行失败: {error_msg}")
            
            return ToolResult(
                title=f"子代理任务失败: {description}",
                output=f"子代理执行失败: {error_msg}",
                metadata={
                    "session_id": sub_session.id,
                    "subagent_type": subagent_type,
                    "status": "failed",
                    "error": error_msg
                }
            )
    
    async def _execute_subagent(
        self,
        agent: 'AgentInfo',
        task_prompt: str,
        parent_context: ToolContext,
        context_files: List[str],
        sub_session_id: str
    ) -> str:
        """执行子代理（创建独立 Session）
        
        Args:
            agent: Agent 配置信息（from AgentRegistry）
            task_prompt: 任务提示
            parent_context: 父上下文
            context_files: 上下文文件列表
            sub_session_id: 子会话ID
            
        Returns:
            子代理返回的结果
        """
        # 准备任务提示（可能包含上下文文件）
        full_prompt = task_prompt
        if context_files:
            files_str = "\n".join([f"- {f}" for f in context_files])
            full_prompt = f"{task_prompt}\n\n相关文件:\n{files_str}\n\n请使用 read 工具读取这些文件。"
        
        # 执行真实 Session
        result = await self._execute_real_session(
            agent,
            full_prompt,
            parent_context,
            sub_session_id
        )
        return result
    
    async def _execute_real_session(
        self,
        agent: 'AgentInfo',
        task_prompt: str,
        parent_context: ToolContext,
        sub_session_id: str
    ) -> str:
        """执行真实的子代理 Session（使用 AgentRegistry）
        
        Args:
            agent: Agent 配置信息
            task_prompt: 任务提示
            parent_context: 父上下文
            sub_session_id: 子会话ID
            
        Returns:
            子代理返回的结果
        """
        from core.session import Session
        from core.config import Config
        from core.protocol import Op
        
        # 1. 获取或创建基础配置
        if self.main_config:
            base_model = self.main_config.model
            base_cwd = self.main_config.cwd
        else:
            # 使用默认配置
            default_config = Config()
            base_model = default_config.model
            base_cwd = default_config.cwd
        
        # 2. 创建子代理专用配置
        # 注意：agent 的配置会在 Session 初始化时应用
        sub_config = Config(
            model=agent.model_override or base_model,
            cwd=base_cwd,
            max_turns=agent.max_turns,
            # 禁用记忆和压缩以确保完全隔离
            enable_memory=False,
            enable_hooks=False,
            enable_compaction=False,
        )
        
        logger.info(f"创建子代理 Session: {agent.name}, model={sub_config.model}, max_turns={sub_config.max_turns}")
        
        # 3. 创建独立 Session（传入 parent_session_id 和 agent_name）
        # Session 会根据 agent 自动创建过滤的工具注册表
        logger.debug(f"子代理允许的工具: {agent.allowed_tools}")
        
        sub_session = Session(
            config=sub_config,
            parent_session_id=parent_context.session_id,  # ← 传入父 session_id
            agent_name=agent.name  # ← 传入 agent 名称
        )
        
        # 4. 启动 Session
        await sub_session.start()
        logger.debug(f"子代理 Session 已启动: {sub_session.session_id}, parent={sub_session.parent_session_id}")
        
        # 5. 提交任务
        task_op = Op.user_input(text=task_prompt, cwd=sub_config.cwd)
        await sub_session.submit_operation(task_op)
        logger.debug(f"任务已提交到子代理")
        
        # 6. 等待任务完成（监听事件）
        result = await self._wait_for_subagent_completion(sub_session)
        
        # 7. 停止 Session
        await sub_session.stop()
        logger.info(f"子代理 Session 已完成: {agent.name}")
        
        return result
    
    async def _wait_for_subagent_completion(self, sub_session) -> str:
        """等待子代理任务完成
        
        Args:
            sub_session: 子代理 Session
            
        Returns:
            子代理返回的最终消息
        """
        # 启动 submission 处理协程
        process_task = asyncio.create_task(sub_session.process_submissions())
        
        result_text = ""
        
        try:
            # 监听事件直到任务完成
            while sub_session.is_active:
                try:
                    event = await asyncio.wait_for(
                        sub_session.get_next_event(), 
                        timeout=0.5
                    )
                    
                    if event:
                        logger.debug(f"收到事件: {event.msg.type}")
                        
                        # 检查是否是任务完成事件
                        if event.msg.type == "task_complete":
                            result_text = event.msg.data.get("last_agent_message", "")
                            logger.info(f"子代理任务完成")
                            break
                        
                        # 检查是否是代理消息
                        elif event.msg.type == "agent_message":
                            # 收集代理消息作为候选结果
                            result_text = event.msg.data.get("message", "")
                        
                        # 检查是否是错误事件
                        elif event.msg.type == "error":
                            error_msg = event.msg.data.get("message", "Unknown error")
                            raise Exception(f"子代理执行错误: {error_msg}")
                            
                except asyncio.TimeoutError:
                    # 继续等待
                    continue
                    
        except Exception as e:
            logger.error(f"等待子代理完成时出错: {e}")
            raise
        finally:
            # 取消处理任务
            process_task.cancel()
            try:
                await process_task
            except asyncio.CancelledError:
                pass
        
        # 如果没有收到明确的完成消息，从对话历史获取最后的 assistant 消息
        if not result_text and sub_session.model_client:
            for msg in reversed(sub_session.model_client.conversation_history):
                if msg.role == "assistant" and msg.content:
                    result_text = msg.content
                    break
        
        return result_text or "子代理完成任务，但未返回结果。"
    
