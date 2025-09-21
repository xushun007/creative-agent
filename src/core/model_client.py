"""AI模型客户端"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncIterator
import json
from dataclasses import dataclass
from pathlib import Path

from openai import AsyncOpenAI
from .protocol import TokenUsage
from .config import Config
from utils.logger import logger


@dataclass
class Message:
    """聊天消息"""
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    tool_calls: List[Dict[str, Any]]
    token_usage: TokenUsage
    finish_reason: str


class ModelClient:
    """AI模型客户端"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.api_base
        )
        self.conversation_history: List[Message] = []
    
    def add_system_message(self, content: str):
        """添加系统消息"""
        self.conversation_history.append(Message("system", content))
    
    def add_user_message(self, content: str):
        """添加用户消息"""
        self.conversation_history.append(Message("user", content))
    
    def add_assistant_message(self, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None):
        """添加助手消息"""
        self.conversation_history.append(Message("assistant", content, tool_calls))
    
    def add_tool_message(self, tool_call_id: str, content: str):
        """添加工具调用结果消息"""
        self.conversation_history.append(Message("tool", content, tool_call_id=tool_call_id))
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """获取工具模式定义 - 从工具注册系统动态获取"""
        from tools.registry import get_global_registry
        
        registry = get_global_registry()
        tools_dict = registry.get_tools_dict(enabled_only=True)
        
        # 转换为OpenAI API需要的格式
        openai_tools = []
        for tool in tools_dict:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            }
            openai_tools.append(openai_tool)
        
        return openai_tools
    
    async def chat_completion(self, stream: bool = False) -> ChatResponse:
        """发送聊天完成请求"""
        messages = []
        for msg in self.conversation_history:
            message_dict = {
                "role": msg.role,
                "content": msg.content
            }
            
            # 添加工具调用信息
            if msg.tool_calls:
                message_dict["tool_calls"] = msg.tool_calls
            
            # 添加工具调用ID（仅用于tool角色）
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
            
            messages.append(message_dict)

        logger.debug(f"发送消息到模型: {messages}")
        
        try:
            if stream:
                return await self._stream_completion(messages)
            else:
                return await self._non_stream_completion(messages)
        except Exception as e:
            raise Exception(f"模型请求失败: {str(e)}")
    
    async def _non_stream_completion(self, messages: List[Dict[str, Any]]) -> ChatResponse:
        """非流式完成"""
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=self.get_tools_schema(),
            tool_choice="auto",
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature
        )
        
        choice = response.choices[0]
        message = choice.message
        
        # 提取工具调用
        tool_calls = []
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        
        # 构建token使用情况
        usage = response.usage
        token_usage = TokenUsage(
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens
        )

        logger.debug(f"模型响应内容: {message.content}")
        logger.debug(f"工具调用: {tool_calls}")
        logger.debug(f"Token使用情况: {token_usage}")
        logger.debug(f"完成原因: {choice.finish_reason}")
        
        return ChatResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            token_usage=token_usage,
            finish_reason=choice.finish_reason
        )
    
    async def _stream_completion(self, messages: List[Dict[str, Any]]) -> ChatResponse:
        """流式完成"""
        content = ""
        tool_calls = []
        
        stream = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=self.get_tools_schema(),
            tool_choice="auto",
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content:
                    content += delta.content
                if delta.tool_calls:
                    # 处理工具调用增量
                    for tc in delta.tool_calls:
                        if tc.id:
                            tool_calls.append({
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            })
        
        # 注意：流式模式下无法获得准确的token使用情况
        token_usage = TokenUsage()
        
        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            token_usage=token_usage,
            finish_reason="stop"
        )
    
    async def stream_completion_events(self, messages: List[Dict[str, Any]]) -> AsyncIterator[str]:
        """流式完成事件生成器"""
        stream = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=self.get_tools_schema(),
            tool_choice="auto",
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
