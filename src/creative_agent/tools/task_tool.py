"""TaskTool - 启动子代理处理复杂任务"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple

from .base_tool import BaseTool, ToolContext, ToolResult
from .task_manager import TaskManager
from creative_agent.core.agents import AgentRegistry

try:
    from creative_agent.utils.logger import logger
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
        
        # 跟踪活跃的子代理会话（用于中断）
        # key 使用 TaskManager 生成的 task_session_id（例如 task_1234abcd），确保与返回给调用方的 ID 一致。
        self._active_subagents: Dict[str, Any] = {}  # {task_session_id: sub_session}
        
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
            available = [a.name for a in self.agent_registry.list_agents(mode="subagent")]
            return ToolResult(
                title=f"未知的子代理类型: {subagent_type}",
                output=f"子代理类型 '{subagent_type}' 不存在。可用的子代理: {', '.join(available)}",
                metadata={
                    "error": "unknown_subagent_type",
                    "requested_type": subagent_type,
                    "available_types": available,
                }
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
            result_text, summary = await self._execute_subagent(
                agent=agent,
                task_prompt=task_prompt,
                parent_context=context,
                context_files=context_files,
                sub_session_id=sub_session.id,  # task_session_id
                parent_session_id=context.session_id
            )
            runtime_session_id = None
            session_record = self.task_manager.get_session(sub_session.id)
            if session_record:
                runtime_session_id = session_record.metadata.get("runtime_session_id")

            output = self._append_task_metadata(
                result_text,
                task_session_id=sub_session.id,
                runtime_session_id=runtime_session_id,
            )
            
            # 4. 更新会话状态
            self.task_manager.update_session_status(
                sub_session.id,
                status="completed",
                result=result_text
            )
            
            logger.info(f"TaskTool: 子代理 '{subagent_type}' 完成任务: {description}")
            
            return ToolResult(
                title=f"子代理任务完成: {description}",
                output=output,
                metadata={
                    "session_id": sub_session.id,
                    "runtime_session_id": runtime_session_id,
                    "subagent_type": subagent_type,
                    "status": "completed",
                    "summary": summary,
                }
            )
            
        except asyncio.CancelledError:
            # 联动取消子代理（无需显式调用）
            await self.cancel_subagent(sub_session.id)
            raise
            
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
        sub_session_id: str,
        parent_session_id: str
    ) -> tuple[str, List[Dict[str, Any]]]:
        """执行子代理（创建独立 Session）
        
        Args:
            agent: Agent 配置信息（from AgentRegistry）
            task_prompt: 任务提示
            parent_context: 父上下文
            context_files: 上下文文件列表
            sub_session_id: 子会话ID
            parent_session_id: 父会话ID（用于注册中断处理）
            
        Returns:
            (子代理返回文本, 工具执行摘要列表)
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
            sub_session_id,
            parent_session_id
        )
        return result
    
    async def _execute_real_session(
        self,
        agent: 'AgentInfo',
        task_prompt: str,
        parent_context: ToolContext,
        sub_session_id: str,
        parent_session_id: str
    ) -> tuple[str, List[Dict[str, Any]]]:
        """执行真实的子代理 Session（使用 AgentRegistry）
        
        Args:
            agent: Agent 配置信息
            task_prompt: 任务提示
            parent_context: 父上下文
            sub_session_id: 子会话ID
            parent_session_id: 父会话ID
            
        Returns:
            (子代理返回文本, 工具执行摘要列表)
        """
        from creative_agent.core.session import Session
        from creative_agent.core.config import Config
        from creative_agent.core.protocol import Op
        
        # 1. 获取或创建基础配置
        parent_cfg = None
        if parent_context.extra and isinstance(parent_context.extra, dict):
            parent_cfg = parent_context.extra.get("config")

        if self.main_config:
            base_model = self.main_config.model
            base_cwd = self.main_config.cwd
        elif parent_cfg:
            # 来自主 Session 的配置（通过 ToolContext.extra 传入）
            base_model = parent_cfg.model
            base_cwd = parent_cfg.cwd
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

        # 便于排查：打印 task_session_id <-> runtime_session_id 映射
        logger.info(
            "子代理 Session 已创建: "
            f"task_session_id={sub_session_id}, runtime_session_id={sub_session.session_id}, "
            f"agent={agent.name}, parent_session_id={parent_context.session_id}"
        )
        
        # 注册到活跃子代理列表（用于中断）- 使用 task_session_id 作为 key
        self._active_subagents[sub_session_id] = sub_session
        # 记录 runtime session id，便于诊断
        record = self.task_manager.get_session(sub_session_id)
        if record:
            record.metadata["runtime_session_id"] = sub_session.session_id
        
        abort_event = None
        if parent_context.extra and isinstance(parent_context.extra, dict):
            abort_event = parent_context.extra.get("abort_event")

        cancel_task = None
        if abort_event:
            async def _watch_abort():
                await abort_event.wait()
                await self.cancel_subagent(sub_session_id)
            cancel_task = asyncio.create_task(_watch_abort())

        try:
            # 4. 启动 Session
            await sub_session.start()
            logger.debug(f"子代理 Session 已启动: {sub_session.session_id}, parent={sub_session.parent_session_id}")
            
            # 5. 提交任务
            task_op = Op.user_input(text=task_prompt, cwd=sub_config.cwd)
            await sub_session.submit_operation(task_op)
            logger.debug(f"任务已提交到子代理")
            
            # 6. 等待任务完成（监听事件）
            result_text, summary = await self._wait_for_subagent_completion(
                sub_session=sub_session,
                parent_context=parent_context,
                task_session_id=sub_session_id,
            )
            
            return result_text, summary
            
        finally:
            if cancel_task:
                cancel_task.cancel()
                try:
                    await cancel_task
                except asyncio.CancelledError:
                    pass
            # 7. 停止并清理 Session（确保资源释放）
            try:
                await sub_session.stop()
                await sub_session.cleanup()
                logger.info(f"子代理 Session 已清理: {agent.name}")
            except Exception as e:
                logger.error(f"清理子代理 Session 失败: {e}")
            finally:
                # 从活跃列表中移除
                self._active_subagents.pop(sub_session_id, None)
    
    async def _wait_for_subagent_completion(
        self,
        sub_session,
        parent_context: ToolContext,
        task_session_id: str,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """等待子代理任务完成
        
        Args:
            sub_session: 子代理 Session
            
        Returns:
            (子代理返回文本, 工具执行摘要列表)
        """
        # 启动 submission 处理协程
        process_task = asyncio.create_task(sub_session.process_submissions())
        
        result_text = ""
        tool_steps: Dict[str, Dict[str, Any]] = {}
        last_summary_key = ""
        current_event: Optional[Dict[str, Any]] = None

        parent_event_handler = None
        if parent_context.extra and isinstance(parent_context.extra, dict):
            parent_event_handler = parent_context.extra.get("event_handler")

        async def _emit_progress():
            nonlocal last_summary_key
            if not parent_event_handler:
                return
            summary = sorted(
                [
                    {
                        "id": item.get("id"),
                        "tool": item.get("tool"),
                        "state": item.get("state"),
                    }
                    for item in tool_steps.values()
                ],
                key=lambda item: item.get("id", ""),
            )
            summary_key = "|".join(
                f"{item.get('id')}:{item.get('state', {}).get('status')}:{item.get('state', {}).get('title', '')}"
                for item in summary
            )
            if summary_key == last_summary_key:
                return
            last_summary_key = summary_key
            from creative_agent.core.protocol import EventMsg
            await parent_event_handler.emit(
                parent_context.message_id,
                EventMsg("task_progress", {
                    "task_session_id": task_session_id,
                    "summary": summary,
                    "current": current_event,
                })
            )
        
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
                        
                        # 子代理工具执行进度
                        elif event.msg.type == "tool_execution_begin":
                            data = event.msg.data
                            call_id = data.get("call_id")
                            tool_name = data.get("tool_name")
                            args = data.get("arguments", {}) if isinstance(data.get("arguments", {}), dict) else {}
                            if call_id and tool_name:
                                title = self._summarize_tool_title(tool_name, args)
                                tool_steps[call_id] = {
                                    "id": call_id,
                                    "tool": tool_name,
                                    "args": args,
                                    "state": {"status": "running"},
                                }
                                if title:
                                    tool_steps[call_id]["state"]["title"] = title
                                current_event = {
                                    "id": call_id,
                                    "tool": tool_name,
                                    "state": tool_steps[call_id]["state"],
                                }
                                await _emit_progress()
                        elif event.msg.type == "tool_execution_end":
                            data = event.msg.data
                            call_id = data.get("call_id")
                            tool_name = data.get("tool_name")
                            success = data.get("success", False)
                            title_from_tool = data.get("title")
                            if call_id and tool_name:
                                args = tool_steps.get(call_id, {}).get("args", {})
                                param_title = self._summarize_tool_title(tool_name, args)
                                tool_steps[call_id] = {
                                    "id": call_id,
                                    "tool": tool_name,
                                    "args": args,
                                    "state": {"status": "completed" if success else "failed"},
                                }
                                if title_from_tool:
                                    merged = self._merge_titles(title_from_tool, param_title)
                                    tool_steps[call_id]["state"]["title"] = self._shorten_title(merged)
                                elif param_title:
                                    tool_steps[call_id]["state"]["title"] = param_title
                                current_event = {
                                    "id": call_id,
                                    "tool": tool_name,
                                    "state": tool_steps[call_id]["state"],
                                }
                                await _emit_progress()
                        
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
        
        summary = sorted(
            [
                {
                    "id": item.get("id"),
                    "tool": item.get("tool"),
                    "state": item.get("state"),
                }
                for item in tool_steps.values()
            ],
            key=lambda item: item.get("id", ""),
        )
        return result_text or "子代理完成任务，但未返回结果。", summary
    
    async def cancel_subagent(self, session_id: str) -> bool:
        """取消正在运行的子代理
        
        Args:
            session_id: 子代理会话ID
            
        Returns:
            是否成功取消
        """
        # session_id 以 task_session_id 为准（execute 返回的 metadata["session_id"]）
        if session_id not in self._active_subagents:
            logger.warning(f"尝试取消不存在的子代理: {session_id}")
            return False
        
        sub_session = self._active_subagents[session_id]
        
        try:
            logger.info(f"正在取消子代理: {session_id}")
            
            # 停止会话
            await sub_session.stop()
            
            # 清理资源
            await sub_session.cleanup()
            
            # 更新任务管理器中的状态
            self.task_manager.update_session_status(
                session_id,
                status="cancelled",
                error="用户取消任务"
            )
            
            logger.info(f"子代理已取消: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消子代理失败: {e}")
            return False
        finally:
            # 从活跃列表中移除
            self._active_subagents.pop(session_id, None)
    
    def get_active_subagents(self) -> List[str]:
        """获取所有活跃的子代理会话ID列表
        
        Returns:
            活跃的会话ID列表
        """
        return list(self._active_subagents.keys())

    def _append_task_metadata(
        self,
        output: str,
        task_session_id: str,
        runtime_session_id: Optional[str] = None,
    ) -> str:
        """在输出末尾追加结构化的 task metadata"""
        if "<task_metadata>" in output:
            return output
        lines = [
            "<task_metadata>",
            f"session_id: {task_session_id}",
        ]
        if runtime_session_id:
            lines.append(f"runtime_session_id: {runtime_session_id}")
        lines.append("</task_metadata>")
        return output.rstrip() + "\n\n" + "\n".join(lines)

    def _summarize_tool_title(self, tool_name: str, args: Dict[str, Any]) -> str:
        """生成简短的工具执行标题，用于进度摘要"""
        def _pick(*keys: str) -> Optional[str]:
            for key in keys:
                val = args.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            return None

        candidate = _pick(
            "filePath",
            "path",
            "command",
            "url",
            "pattern",
            "query",
            "description",
        )
        return self._shorten_title(candidate) if candidate else ""

    def _shorten_title(self, value: str, max_len: int = 80) -> str:
        if not value:
            return ""
        if len(value) <= max_len:
            return value
        return "..." + value[-(max_len - 3):]

    def _merge_titles(self, primary: str, secondary: Optional[str]) -> str:
        if not primary:
            return secondary or ""
        if not secondary:
            return primary
        if secondary in primary or primary in secondary:
            return primary if len(primary) <= len(secondary) else secondary
        return f"{primary} @ {secondary}"
    
    def is_subagent_active(self, session_id: str) -> bool:
        """检查子代理是否活跃
        
        Args:
            session_id: 子代理会话ID
            
        Returns:
            是否活跃
        """
        return session_id in self._active_subagents
    
