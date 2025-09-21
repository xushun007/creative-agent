"""统一事件处理器 - 简洁的事件发送和管理机制"""

import asyncio
from typing import Optional
from .protocol import Event, EventMsg


class EventHandler:
    """统一事件处理器 - 负责所有事件的发送和管理"""
    
    def __init__(self):
        self.event_queue = asyncio.Queue()
    
    async def emit(self, submission_id: str, event_msg: EventMsg):
        """发送事件 - 统一的事件发送接口"""
        event = Event(
            id=submission_id,
            msg=event_msg
        )
        await self.event_queue.put(event)
    
    async def get_next_event(self) -> Optional[Event]:
        """获取下一个事件"""
        try:
            return await asyncio.wait_for(self.event_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None
    
    # 便捷方法 - 常用事件的快捷发送
    async def emit_task_started(self, submission_id: str):
        """发送任务开始事件"""
        await self.emit(submission_id, EventMsg.task_started())
    
    async def emit_task_complete(self, submission_id: str, message: str = None):
        """发送任务完成事件"""
        await self.emit(submission_id, EventMsg.task_complete(message))
    
    async def emit_user_message(self, submission_id: str, message: str):
        """发送用户消息事件"""
        await self.emit(submission_id, EventMsg.user_message(message))
    
    async def emit_agent_message(self, submission_id: str, message: str):
        """发送代理消息事件"""
        await self.emit(submission_id, EventMsg.agent_message(message))
    
    async def emit_tool_start(self, submission_id: str, tool_name: str, call_id: str, arguments: dict):
        """发送工具执行开始事件"""
        await self.emit(submission_id, EventMsg("tool_execution_begin", {
            "tool_name": tool_name,
            "call_id": call_id,
            "arguments": arguments
        }))
    
    async def emit_tool_end(self, submission_id: str, tool_name: str, call_id: str, 
                           success: bool, result: str = None, error: str = None):
        """发送工具执行结束事件"""
        await self.emit(submission_id, EventMsg("tool_execution_end", {
            "tool_name": tool_name,
            "call_id": call_id,
            "success": success,
            "result": result,
            "error": error
        }))
    
    async def emit_error(self, submission_id: str, message: str):
        """发送错误事件"""
        await self.emit(submission_id, EventMsg.error(message))
