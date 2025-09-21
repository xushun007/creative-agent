"""Codex会话管理"""

import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
import uuid
from datetime import datetime

from .protocol import (
    Submission, Event, EventMsg, Op, AskForApproval, SandboxPolicy,
    TokenUsage
)
from .config import Config
from .model_client import ModelClient


class Session:
    """Codex会话"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session_id = str(uuid.uuid4())
        self.model_client = ModelClient(config)
        
        # 集成工具注册系统
        from tools.registry import get_global_registry
        self.tool_registry = get_global_registry()
        
        # 队列
        self.submission_queue = asyncio.Queue()
        self.event_queue = asyncio.Queue()
        
        # 会话状态
        self.is_active = False
        self.current_task_id: Optional[str] = None
        self.approval_pending: Dict[str, Submission] = {}
        
        # Token统计
        self.total_token_usage = TokenUsage()
        
        # 初始化系统消息
        self._setup_system_messages()
    
    def _setup_system_messages(self):
        """设置系统消息"""
        # 从prompt文件读取基础系统提示词
        try:
            prompt_file = Path(__file__).parent.parent / "prompt" / "ctv-claude-code-system-prompt-zh.txt"
            with open(prompt_file, 'r', encoding='utf-8') as f:
                system_prompt = f.read()
        except FileNotFoundError:
            # 如果文件不存在，使用配置中的基础指令作为回退
            system_prompt = self.config.base_instructions
        
        # 添加用户自定义指令
        if self.config.user_instructions:
            system_prompt += f"\n\n用户指令:\n{self.config.user_instructions}"
        
        # 动态获取可用工具信息
        available_tools = self.tool_registry.get_tools_dict(enabled_only=True)
        tools_info = "\n".join([f"{i+1}. {tool['name']} - {tool['description']}" 
                               for i, tool in enumerate(available_tools)])
        
        # 添加环境信息和工具列表
        system_prompt += f"""

## 当前环境信息

当前工作目录: {self.config.cwd}
批准策略: {self.config.approval_policy}  
沙箱策略: {self.config.sandbox_policy}

## 可用工具

你可以使用以下工具:
{tools_info}

请根据用户的需求，使用合适的工具来完成任务。在执行可能有风险的操作时，会根据批准策略询问用户确认。
"""
        
        self.model_client.add_system_message(system_prompt)
    
    async def start(self):
        """启动会话"""
        self.is_active = True
        
        # 发送会话配置事件
        config_event = Event(
            id=self.session_id,
            msg=EventMsg("session_configured", {
                "session_id": self.session_id,
                "model": self.config.model,
                "cwd": str(self.config.cwd)
            })
        )
        await self.event_queue.put(config_event)
    
    async def stop(self):
        """停止会话"""
        self.is_active = False
        
        # 发送会话结束事件
        shutdown_event = Event(
            id=self.session_id,
            msg=EventMsg("shutdown_complete", {})
        )
        await self.event_queue.put(shutdown_event)
    
    async def submit_operation(self, op: Op) -> str:
        """提交操作"""
        submission = Submission.create(op)
        await self.submission_queue.put(submission)
        return submission.id
    
    async def get_next_event(self) -> Optional[Event]:
        """获取下一个事件"""
        try:
            return await asyncio.wait_for(self.event_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None
    
    async def process_submissions(self):
        """处理提交队列"""
        while self.is_active:
            try:
                submission = await asyncio.wait_for(
                    self.submission_queue.get(), timeout=0.1
                )
                await self._handle_submission(submission)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                error_event = Event(
                    id=submission.id if 'submission' in locals() else "unknown",
                    msg=EventMsg.error(f"处理提交时出错: {str(e)}")
                )
                await self.event_queue.put(error_event)
    
    async def _handle_submission(self, submission: Submission):
        """处理单个提交"""
        op = submission.op
        
        if op.type == "user_input":
            await self._handle_user_input(submission)
        elif op.type == "interrupt":
            await self._handle_interrupt(submission)
        elif op.type == "exec_approval":
            await self._handle_exec_approval(submission)
        else:
            error_event = Event(
                id=submission.id,
                msg=EventMsg.error(f"未知操作类型: {op.type}")
            )
            await self.event_queue.put(error_event)
    
    async def _handle_user_input(self, submission: Submission):
        """处理用户输入 - 实现完整的 ReAct 循环"""
        op = submission.op
        
        # 发送任务开始事件
        task_start_event = Event(
            id=submission.id,
            msg=EventMsg.task_started()
        )
        await self.event_queue.put(task_start_event)
        
        # 添加用户消息到对话历史
        if op.items:
            user_text = " ".join(item.text for item in op.items if item.text)
            self.model_client.add_user_message(user_text)
            
            # 发送用户消息事件
            user_msg_event = Event(
                id=submission.id,
                msg=EventMsg.user_message(user_text)
            )
            await self.event_queue.put(user_msg_event)
        
        # ReAct 循环：持续对话直到任务完成
        max_turns = self.config.max_turns  # 防止无限循环
        turn = 0
        last_agent_message = None
        
        while turn < max_turns:
            try:
                # 获取AI响应
                response = await self.model_client.chat_completion()
                
                # 更新token使用统计
                self._update_token_usage(response.token_usage)
                
                # 添加assistant消息到对话历史
                assistant_content = response.content or ""
                self.model_client.add_assistant_message(
                    assistant_content, response.tool_calls
                )
                
                # 发送AI消息事件
                if response.content:
                    last_agent_message = response.content
                    agent_msg_event = Event(
                        id=submission.id,
                        msg=EventMsg.agent_message(response.content)
                    )
                    await self.event_queue.put(agent_msg_event)
                
                # 如果没有工具调用，任务完成
                if not response.tool_calls:
                    break
                
                # 处理工具调用
                await self._handle_tool_calls(submission.id, response.tool_calls)
                
                # 继续下一轮对话
                turn += 1
                
            except Exception as e:
                error_event = Event(
                    id=submission.id,
                    msg=EventMsg.error(f"AI响应失败: {str(e)}")
                )
                await self.event_queue.put(error_event)
                break
        
        # 检查是否达到最大轮次
        if turn >= max_turns:
            warning_event = Event(
                id=submission.id,
                msg=EventMsg.error(f"任务执行达到最大轮次限制 ({max_turns})，可能存在循环")
            )
            await self.event_queue.put(warning_event)
        
        # 发送任务完成事件
        task_complete_event = Event(
            id=submission.id,
            msg=EventMsg.task_complete(last_agent_message or "任务已完成")
        )
        await self.event_queue.put(task_complete_event)
    
    async def _handle_tool_calls(self, submission_id: str, tool_calls: List[Dict[str, Any]]):
        """处理工具调用 - 使用工具注册系统"""
        from tools.base_tool import ToolContext
        import json
        
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            call_id = tool_call["id"]
            
            try:
                # 解析参数
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError as e:
                    error_result = f"参数解析失败: {str(e)}"
                    self.model_client.add_tool_message(call_id, error_result)
                    continue
                
                # 检查是否需要用户批准
                if await self._needs_approval(tool_name, arguments):
                    # 存储待批准的工具调用
                    self.approval_pending[call_id] = {
                        "submission_id": submission_id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "call_id": call_id
                    }
                    await self._request_approval(submission_id, call_id, tool_name, arguments)
                    continue
                
                # 发送工具执行开始事件
                exec_start_event = Event(
                    id=submission_id,
                    msg=EventMsg("tool_execution_begin", {
                        "tool_name": tool_name,
                        "call_id": call_id,
                        "arguments": arguments
                    })
                )
                await self.event_queue.put(exec_start_event)
                
                # 创建工具执行上下文
                context = ToolContext(
                    session_id=self.session_id,
                    message_id=submission_id,
                    agent="Session",
                    call_id=call_id
                )
                
                # 使用工具注册系统执行工具
                result = await self.tool_registry.execute_tool(tool_name, arguments, context)
                
                # 格式化结果并添加到消息历史
                if result:
                    result_text = result.output
                    self.model_client.add_tool_message(call_id, result_text)
                    
                    # 发送工具执行成功事件
                    exec_end_event = Event(
                        id=submission_id,
                        msg=EventMsg("tool_execution_end", {
                            "tool_name": tool_name,
                            "call_id": call_id,
                            "success": True,
                            "result": result_text
                        })
                    )
                else:
                    error_result = "工具执行失败，返回空结果"
                    self.model_client.add_tool_message(call_id, error_result)
                    
                    # 发送工具执行失败事件
                    exec_end_event = Event(
                        id=submission_id,
                        msg=EventMsg("tool_execution_end", {
                            "tool_name": tool_name,
                            "call_id": call_id,
                            "success": False,
                            "error": error_result
                        })
                    )
                
                await self.event_queue.put(exec_end_event)
                
            except Exception as e:
                error_result = f"工具调用处理失败: {str(e)}"
                self.model_client.add_tool_message(call_id, error_result)
                
                # 发送工具执行异常事件
                exec_error_event = Event(
                    id=submission_id,
                    msg=EventMsg("tool_execution_end", {
                        "tool_name": tool_name,
                        "call_id": call_id,
                        "success": False,
                        "error": error_result
                    })
                )
                await self.event_queue.put(exec_error_event)
    
    
    async def _needs_approval(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """检查是否需要用户批准"""
        approval_policy = AskForApproval(self.config.approval_policy)
        
        if approval_policy == AskForApproval.NEVER:
            return False
        elif approval_policy == AskForApproval.ON_REQUEST:
            # 对于某些危险操作总是需要批准
            dangerous_commands = ["rm", "del", "format", "sudo", "chmod"]
            # 适配新的工具名称
            if tool_name in ["execute_command", "bash"]:
                command = arguments.get("command", "")
                return any(cmd in command.lower() for cmd in dangerous_commands)
            elif tool_name in ["write_file", "write"]:
                # 写入系统重要文件需要批准
                file_path = arguments.get("file_path", "")
                system_paths = ["/etc", "/sys", "/proc", "C:\\Windows"]
                return any(path in file_path for path in system_paths)
        elif approval_policy == AskForApproval.UNLESS_TRUSTED:
            # 只有明确安全的操作才不需要批准
            if tool_name in ["read_file", "read"]:
                return False
            return True
        
        return False
    
    async def _request_approval(self, submission_id: str, call_id: str, tool_name: str, arguments: Dict[str, Any]):
        """请求用户批准"""
        if tool_name == "execute_command":
            command = arguments.get("command", "")
            cwd = Path(arguments.get("cwd", self.config.cwd))
            
            approval_event = Event(
                id=submission_id,
                msg=EventMsg.exec_approval_request(
                    call_id, [command], cwd, "需要用户批准执行命令"
                )
            )
        else:
            approval_event = Event(
                id=submission_id,
                msg=EventMsg("approval_request", {
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "reason": f"需要用户批准执行 {tool_name}"
                })
            )
        
        await self.event_queue.put(approval_event)
    
    async def _handle_interrupt(self, submission: Submission):
        """处理中断"""
        self.current_task_id = None
        
        interrupt_event = Event(
            id=submission.id,
            msg=EventMsg("turn_aborted", {"reason": "interrupted"})
        )
        await self.event_queue.put(interrupt_event)
    
    async def _handle_exec_approval(self, submission: Submission):
        """处理执行批准"""
        op = submission.op
        decision = op.decision
        call_id = getattr(op, 'call_id', None)
        
        if not call_id or call_id not in self.approval_pending:
            error_event = Event(
                id=submission.id,
                msg=EventMsg.error("未找到待批准的工具调用")
            )
            await self.event_queue.put(error_event)
            return
        
        pending_call = self.approval_pending[call_id]
        
        if decision in ["approved", "approved_for_session"]:
            # 执行之前被阻止的操作
            try:
                from tools.base_tool import ToolContext
                
                # 创建工具执行上下文
                context = ToolContext(
                    session_id=self.session_id,
                    message_id=submission.id,
                    agent="Session",
                    call_id=call_id
                )
                
                # 使用工具注册系统执行工具
                result = await self.tool_registry.execute_tool(
                    pending_call["tool_name"], 
                    pending_call["arguments"], 
                    context
                )
                
                # 格式化结果并添加到消息历史
                if result:
                    result_text = result.output
                    self.model_client.add_tool_message(call_id, result_text)
                    
                    # 发送批准完成事件
                    approval_complete_event = Event(
                        id=submission.id,
                        msg=EventMsg("approval_complete", {
                            "call_id": call_id,
                            "decision": decision,
                            "result": "已执行",
                            "tool_result": result_text
                        })
                    )
                else:
                    error_result = "批准后工具执行返回空结果"
                    self.model_client.add_tool_message(call_id, error_result)
                    
                    approval_complete_event = Event(
                        id=submission.id,
                        msg=EventMsg("approval_complete", {
                            "call_id": call_id,
                            "decision": decision,
                            "result": "执行失败",
                            "error": error_result
                        })
                    )
                
                await self.event_queue.put(approval_complete_event)
                
            except Exception as e:
                error_result = f"批准后执行失败: {str(e)}"
                self.model_client.add_tool_message(call_id, error_result)
                
                error_event = Event(
                    id=submission.id,
                    msg=EventMsg("approval_complete", {
                        "call_id": call_id,
                        "decision": decision,
                        "result": "执行异常",
                        "error": error_result
                    })
                )
                await self.event_queue.put(error_event)
        else:
            # 拒绝执行
            rejection_result = f"用户拒绝执行工具调用: {pending_call['tool_name']}"
            self.model_client.add_tool_message(call_id, rejection_result)
            
            # 发送拒绝事件
            rejection_event = Event(
                id=submission.id,
                msg=EventMsg("approval_rejected", {
                    "call_id": call_id,
                    "tool_name": pending_call["tool_name"],
                    "reason": "用户拒绝"
                })
            )
            await self.event_queue.put(rejection_event)
        
        # 清理待批准记录
        del self.approval_pending[call_id]
    
    def _update_token_usage(self, usage: TokenUsage):
        """更新token使用统计"""
        self.total_token_usage.input_tokens += usage.input_tokens
        self.total_token_usage.output_tokens += usage.output_tokens
        self.total_token_usage.total_tokens += usage.total_tokens
        
        # 发送token统计事件
        asyncio.create_task(self.event_queue.put(Event(
            id=self.session_id,
            msg=EventMsg.token_count(self.total_token_usage)
        )))
