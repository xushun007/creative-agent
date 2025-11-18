"""AI模型客户端"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncIterator
import json
from dataclasses import dataclass, field
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
    metadata: Dict[str, Any] = field(default_factory=dict)  # 存储额外信息（summary, compacted_at等）
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（包含所有字段和 metadata）"""
        d = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.metadata:
            d.update(self.metadata)
        return d
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Message':
        """从字典反序列化（自动提取 metadata）"""
        metadata = {k: v for k, v in d.items() 
                   if k not in ["role", "content", "tool_calls", "tool_call_id"]}
        return cls(
            role=d.get("role", "user"),
            content=d.get("content", ""),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
            metadata=metadata
        )


@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    tool_calls: List[Dict[str, Any]]
    token_usage: TokenUsage
    finish_reason: str
    reasoning_content: Optional[str] = None  # 推理内容（DeepSeek等模型特有）


class ModelClient:
    """AI模型客户端（集成记忆管理）
    
    设计：
    - 如果提供了 memory_manager，则使用其管理对话历史
    - 否则，使用内部的 conversation_history（回退模式）
    """
    
    def __init__(self, config: Config, tool_registry=None, memory_manager=None):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.api_base
        )
        
        # 记忆管理器（可选）
        self.memory_manager = memory_manager
        
        # 回退：内部对话历史（当没有 memory_manager 时使用）
        self.conversation_history: List[Message] = []
        
        self.tool_registry = tool_registry
        
        self._setup_system_messages()
    
    def add_system_message(self, content: str):
        """添加系统消息"""
        if self.memory_manager:
            from .memory import MemoryMessage
            from datetime import datetime
            # 注意：MemoryManager 已在初始化时添加了系统消息（包含项目文档）
            # 这里只在非 memory_manager 模式下使用
            pass
        self.conversation_history.append(Message("system", content))
    
    def add_user_message(self, content: str):
        """添加用户消息"""
        if self.memory_manager:
            self.memory_manager.add_user_message(content)
        else:
            self.conversation_history.append(Message("user", content))
    
    def add_assistant_message(self, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None):
        """添加助手消息"""
        if self.memory_manager:
            self.memory_manager.add_assistant_message(content, tool_calls)
        else:
            self.conversation_history.append(Message("assistant", content, tool_calls))
    
    def add_tool_message(self, tool_call_id: str, content: str):
        """添加工具调用结果消息"""
        if self.memory_manager:
            self.memory_manager.add_tool_message(content, tool_call_id)
        else:
            self.conversation_history.append(Message("tool", content, tool_call_id=tool_call_id))
    
    def clear_history(self):
        """清空对话历史"""
        if self.memory_manager:
            self.memory_manager.replace_messages([])
        else:
            self.conversation_history.clear()
    
    def get_messages(self) -> List[Message]:
        """获取消息列表（统一接口）"""
        if self.memory_manager:
            # 从 MemoryMessage 转换为 Message
            from datetime import datetime
            return [
                Message(
                    role=msg.role,
                    content=msg.content,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                    metadata=msg.metadata
                )
                for msg in self.memory_manager.messages
            ]
        else:
            return self.conversation_history
    
    def _setup_system_messages(self):
        """设置系统消息 - 内聚在ModelClient中
        
        注意：
        - 如果启用了 memory_manager，系统消息（包括项目文档）已在 MemoryManager 初始化时添加
        - 这里只在非 memory_manager 模式下添加系统消息
        """
        # 如果使用记忆管理器，跳过（MemoryManager 已处理）
        if self.memory_manager:
            logger.debug("使用记忆管理器，跳过 ModelClient 中的系统消息设置")
            return
        
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
        if self.tool_registry:
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
        
        self.add_system_message(system_prompt)
    
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
        # 获取消息（统一接口）
        history = self.get_messages()
        
        messages = []
        for msg in history:
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

        logger.debug(f"发送消息到模型: {len(messages)} 条")
        
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
        
        # 提取推理内容（DeepSeek等模型特有）
        reasoning_content = None
        if hasattr(message, 'reasoning_content') and message.reasoning_content:
            reasoning_content = message.reasoning_content

        # 构建token使用情况
        usage = response.usage
        token_usage = TokenUsage(
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens
        )

        logger.debug(f"模型响应内容: {message.content}")
        logger.debug(f"推理内容: {reasoning_content}")
        logger.debug(f"工具调用: {tool_calls}")
        logger.debug(f"Token使用情况: {token_usage}")
        logger.debug(f"完成原因: {choice.finish_reason}")
        
        return ChatResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            token_usage=token_usage,
            finish_reason=choice.finish_reason,
            reasoning_content=reasoning_content
        )
    
    async def _stream_completion(self, messages: List[Dict[str, Any]]) -> ChatResponse:
        """流式完成"""
        content = ""
        tool_calls = []
        reasoning_content = ""
        
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
                # 处理推理内容增量
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    reasoning_content += delta.reasoning_content
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
            finish_reason="stop",
            reasoning_content=reasoning_content if reasoning_content else None
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
