"""AgentTurn - 代理回合类，集成事件系统的LLM交互管理"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from .protocol import Event, EventMsg, TokenUsage
from .model_client import ModelClient, ChatResponse
from .event_handler import EventHandler
from tools.base_tool import ToolContext, ToolResult
from tools.registry import ToolRegistry
from utils.logger import logger


@dataclass
class ThoughtResult:
    """思考结果"""
    subject: str  # 思考主题
    description: str  # 思考内容


@dataclass
class ToolCallRequest:
    """工具调用请求"""
    call_id: str
    name: str
    args: Dict[str, Any]
    
    def __str__(self) -> str:
        return f"ToolCall({self.name}, {self.args})"
    
    @classmethod
    def from_openai_tool_call(cls, tool_call) -> 'ToolCallRequest':
        """从OpenAI工具调用对象创建请求"""
        return cls(
            call_id=tool_call["id"],
            name=tool_call["function"]["name"],
            args=json.loads(tool_call["function"]["arguments"]) if tool_call["function"]["arguments"] else {}
        )


@dataclass
class ToolCallResponse:
    """工具调用响应"""
    call_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    tool_result: Optional[ToolResult] = None
    
    def __str__(self) -> str:
        if self.success:
            return f"ToolResponse(success, {self.result})"
        else:
            return f"ToolResponse(error, {self.error})"


@dataclass
class AgentTurnResult:
    """代理回合执行结果"""
    # 基本内容
    text_content: str = ""
    
    # 思考内容
    thoughts: List[ThoughtResult] = field(default_factory=list)
    
    # 工具调用
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    tool_responses: List[ToolCallResponse] = field(default_factory=list)
    
    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: Optional[int] = None
    token_usage: Optional[TokenUsage] = None
    finish_reason: str = ""
    
    def has_tool_calls(self) -> bool:
        """是否包含工具调用"""
        return len(self.tool_calls) > 0
    
    def has_successful_tool_calls(self) -> bool:
        """是否有成功的工具调用"""
        return any(resp.success for resp in self.tool_responses)
    
    def get_summary(self) -> str:
        """获取回合摘要"""
        parts = []
        if self.text_content:
            parts.append(f"文本响应: {len(self.text_content)} 字符")
        if self.thoughts:
            parts.append(f"推理内容: {len(self.thoughts)} 条")
        if self.tool_calls:
            parts.append(f"工具调用: {len(self.tool_calls)} 个")
        if self.token_usage:
            parts.append(f"Token: {self.token_usage.total_tokens}")
        return ", ".join(parts) if parts else "空响应"


class AgentTurn:
    """代理回合 - 管理一次完整的LLM交互，包含事件发送"""
    
    def __init__(self, 
                 model_client: ModelClient,
                 tool_registry: ToolRegistry,
                 event_handler: Optional[EventHandler] = None,
                 session_id: str = "default"):
        self.model_client = model_client
        self.tool_registry = tool_registry
        self.event_handler = event_handler  # 可以为None，不强制要求
        self.session_id = session_id
        
        # 批准机制相关
        self.approval_pending: Dict[str, Dict[str, Any]] = {}
    
    async def execute_turn(self, submission_id: str) -> AgentTurnResult:
        """执行一个完整的代理回合"""
        start_time = datetime.now()
        
        try:
            # 1. 调用LLM获取响应
            logger.info("开始Turn LLM调用")
            llm_response = await self.model_client.chat_completion()
            
            # 2. 解析LLM响应
            result = self._parse_llm_response(llm_response)
            
            # 3. 立即将assistant消息添加到对话历史（在工具调用之前）
            if result.text_content or result.has_tool_calls():
                # 构建tool_calls格式
                tool_calls_for_message = []
                if result.has_tool_calls():
                    tool_calls_for_message = [
                        {
                            "id": tc.call_id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.args)
                            }
                        }
                        for tc in result.tool_calls
                    ]
                
                # 添加assistant消息到对话历史
                self.model_client.add_assistant_message(
                    result.text_content or "", 
                    tool_calls_for_message if tool_calls_for_message else None
                )
            
            # 4. 发送AI消息事件
            if result.text_content and self.event_handler:
                await self.event_handler.emit_agent_message(submission_id, result.text_content)
            
            # 5. 处理工具调用（如果有）
            if result.has_tool_calls():
                await self._handle_tool_calls(submission_id, result)
            
            # 6. 计算执行时间
            end_time = datetime.now()
            result.duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            logger.info(f"AgentTurn执行完成，耗时: {result.duration_ms}ms")
            return result
            
        except Exception as e:
            logger.error(f"AgentTurn执行异常: {e}")
            # 发送错误事件
            if self.event_handler:
                await self.event_handler.emit_error(submission_id, f"回合执行失败: {str(e)}")
            
            # 返回错误结果
            end_time = datetime.now()
            return AgentTurnResult(
                text_content=f"执行出错: {str(e)}",
                duration_ms=int((end_time - start_time).total_seconds() * 1000)
            )
    
    def _parse_llm_response(self, response: ChatResponse) -> AgentTurnResult:
        """解析LLM响应"""
        result = AgentTurnResult()
        
        # 提取文本内容
        result.text_content = response.content or ""
        
        # 提取推理内容（DeepSeek等模型特有）
        # 注意：这里需要从原始响应对象中获取推理内容
        # ChatResponse可能需要扩展以支持推理内容
        if hasattr(response, 'reasoning_content') and response.reasoning_content:
            result.thoughts.append(ThoughtResult(
                subject="推理",
                description=response.reasoning_content
            ))
        
        # 提取工具调用
        if response.tool_calls:
            for tool_call in response.tool_calls:
                try:
                    tool_request = ToolCallRequest.from_openai_tool_call(tool_call)
                    result.tool_calls.append(tool_request)
                except Exception as e:
                    logger.warning(f"解析工具调用失败: {e}")
        
        # 设置元数据
        result.token_usage = response.token_usage
        result.finish_reason = response.finish_reason
        
        return result
    
    async def _handle_tool_calls(self, submission_id: str, result: AgentTurnResult):
        """处理工具调用"""
        for tool_call in result.tool_calls:
            try:
                # 发送工具执行开始事件
                if self.event_handler:
                    await self.event_handler.emit_tool_start(
                        submission_id, tool_call.name, tool_call.call_id, tool_call.args
                    )
                
                # 检查是否需要用户批准
                if await self._needs_approval(tool_call.name, tool_call.args):
                    await self._request_approval(submission_id, tool_call)
                    continue
                
                # 执行工具调用
                response = await self._execute_tool_call(tool_call, submission_id)
                result.tool_responses.append(response)
                
                # 添加工具结果到对话历史
                result_text = response.result if response.success else response.error
                self.model_client.add_tool_message(tool_call.call_id, str(result_text))
                
                # 发送工具执行完成事件
                if self.event_handler:
                    await self.event_handler.emit_tool_end(
                        submission_id, tool_call.name, tool_call.call_id,
                        response.success, 
                        result_text if response.success else None,
                        response.error if not response.success else None
                    )
                
            except Exception as e:
                error_response = ToolCallResponse(
                    call_id=tool_call.call_id,
                    success=False,
                    error=str(e)
                )
                result.tool_responses.append(error_response)
                
                # 添加错误结果到对话历史
                self.model_client.add_tool_message(tool_call.call_id, f"工具调用异常: {str(e)}")
                
                # 发送工具执行异常事件
                if self.event_handler:
                    await self.event_handler.emit_tool_end(
                        submission_id, tool_call.name, tool_call.call_id,
                        False, None, str(e)
                    )
    
    async def _execute_tool_call(self, tool_call: ToolCallRequest, submission_id: str) -> ToolCallResponse:
        """执行单个工具调用"""
        try:
            logger.info(f"执行工具调用: {tool_call}")
            
            # 创建工具执行上下文
            context = ToolContext(
                session_id=self.session_id,
                message_id=submission_id,
                agent="AgentTurn",
                call_id=tool_call.call_id
            )
            
            # 使用工具注册系统执行工具
            tool_result = await self.tool_registry.execute_tool(
                tool_call.name, 
                tool_call.args, 
                context
            )
            
            if tool_result:
                return ToolCallResponse(
                    call_id=tool_call.call_id,
                    success=True,
                    result=tool_result.output,
                    tool_result=tool_result
                )
            else:
                return ToolCallResponse(
                    call_id=tool_call.call_id,
                    success=False,
                    error=f"工具 {tool_call.name} 执行失败或返回空结果"
                )
                
        except Exception as e:
            logger.error(f"工具调用执行异常: {tool_call.name}, 错误: {e}")
            return ToolCallResponse(
                call_id=tool_call.call_id,
                success=False,
                error=str(e)
            )
    
    async def _needs_approval(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """检查是否需要用户批准 - 简化版本，后续可扩展"""
        # 这里可以根据具体需求实现批准逻辑
        # 目前返回False，表示不需要批准
        return False
    
    async def _request_approval(self, submission_id: str, tool_call: ToolCallRequest):
        """请求用户批准 - 预留接口"""
        # 存储待批准的工具调用
        self.approval_pending[tool_call.call_id] = {
            "submission_id": submission_id,
            "tool_name": tool_call.name,
            "arguments": tool_call.args,
            "call_id": tool_call.call_id
        }
        
        # 发送批准请求事件
        if self.event_handler:
            await self.event_handler.emit(submission_id, EventMsg(
                "approval_request", {
                    "call_id": tool_call.call_id,
                    "tool_name": tool_call.name,
                    "arguments": tool_call.args,
                    "reason": f"需要用户批准执行 {tool_call.name}"
                }
            ))
    
    async def handle_approval_response(self, call_id: str, approved: bool) -> bool:
        """处理批准响应"""
        if call_id not in self.approval_pending:
            return False
        
        pending_call = self.approval_pending[call_id]
        
        if approved:
            # 执行之前被阻止的操作
            tool_call = ToolCallRequest(
                call_id=call_id,
                name=pending_call["tool_name"],
                args=pending_call["arguments"]
            )
            
            response = await self._execute_tool_call(tool_call, pending_call["submission_id"])
            
            # 添加结果到对话历史
            result_text = response.result if response.success else response.error
            self.model_client.add_tool_message(call_id, str(result_text))
            
            # 发送批准完成事件
            if self.event_handler:
                await self.event_handler.emit(pending_call["submission_id"], EventMsg(
                    "approval_complete", {
                        "call_id": call_id,
                        "decision": "approved",
                        "result": "已执行" if response.success else "执行失败",
                        "tool_result": result_text
                    }
                ))
        else:
            # 拒绝执行
            rejection_result = f"用户拒绝执行工具调用: {pending_call['tool_name']}"
            self.model_client.add_tool_message(call_id, rejection_result)
            
            # 发送拒绝事件
            if self.event_handler:
                await self.event_handler.emit(pending_call["submission_id"], EventMsg(
                    "approval_rejected", {
                        "call_id": call_id,
                        "tool_name": pending_call["tool_name"],
                        "reason": "用户拒绝"
                    }
                ))
        
        # 清理待批准记录
        del self.approval_pending[call_id]
        return True
    
