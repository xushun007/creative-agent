"""通用编码问题解决Agent - 基于ReAct策略"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
from datetime import datetime

from tools import get_global_registry, ToolContext, ToolResult


logger = logging.getLogger(__name__)


@dataclass
class Message:
    """消息类"""
    role: str  # user, assistant, system, tool
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Agent配置"""
    max_turns: int = 10
    max_tokens: int = 4000
    temperature: float = 0.1
    model: str = "deepseek-chat"
    system_prompt_path: str = "prompt/ctv-claude-code-system-prompt-zh.txt"
    enable_streaming: bool = True
    working_directory: str = "./workspace"


class LLMService:
    """LLM服务接口"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = None
        self._setup_client()
    
    def _setup_client(self):
        """设置OpenAI兼容客户端"""
        try:
            from openai import OpenAI
            import os
            
            # 支持多种API配置
            api_key = os.getenv("OPENAI_API_KEY", "dummy-key")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            logger.info(f"LLM client initialized with base_url: {base_url}")
        except ImportError:
            logger.error("OpenAI library not installed. Please install: pip install openai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise
    
    async def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天完成 - 返回文本内容"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise
    
    async def chat_completion_with_tools(self, messages: List[Dict[str, str]], **kwargs):
        """聊天完成 - 返回完整响应对象，支持工具调用"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"LLM completion with tools failed: {e}")
            raise
    
    async def chat_completion_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """流式聊天完成"""
        try:
            stream = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
                **kwargs
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            raise


class ReActEngine:
    """ReAct推理引擎"""
    
    def __init__(self, llm_service: LLMService, tool_registry):
        self.llm_service = llm_service
        self.tool_registry = tool_registry
        self.thought_pattern = re.compile(r'思考[:：]\s*(.*?)(?=\n行动[:：]|\n观察[:：]|$)', re.DOTALL | re.IGNORECASE)
        self.action_pattern = re.compile(r'行动[:：]\s*(.*?)(?=\n观察[:：]|\n思考[:：]|$)', re.DOTALL | re.IGNORECASE)
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析ReAct响应"""
        result = {
            "thought": "",
            "action": None,
            "final_answer": ""
        }
        
        # 提取思考
        thought_match = self.thought_pattern.search(response)
        if thought_match:
            result["thought"] = thought_match.group(1).strip()
        
        # 提取行动
        action_match = self.action_pattern.search(response)
        if action_match:
            action_text = action_match.group(1).strip()
            result["action"] = self._parse_action(action_text)
        
        # 如果没有行动，则认为是最终答案
        if not result["action"]:
            result["final_answer"] = response.strip()
        
        return result
    
    def _parse_action(self, action_text: str) -> Optional[Dict[str, Any]]:
        """解析行动指令"""
        try:
            # 尝试解析JSON格式的工具调用
            if action_text.startswith('{') and action_text.endswith('}'):
                return json.loads(action_text)
            
            # 尝试解析简单格式: tool_name(param1=value1, param2=value2)
            match = re.match(r'(\w+)\((.*?)\)', action_text)
            if match:
                tool_name = match.group(1)
                params_str = match.group(2)
                
                params = {}
                if params_str:
                    for param in params_str.split(','):
                        if '=' in param:
                            key, value = param.split('=', 1)
                            params[key.strip()] = value.strip().strip('"\'')
                
                return {
                    "tool": tool_name,
                    "parameters": params
                }
            
            return None
        except Exception as e:
            logger.warning(f"Failed to parse action: {action_text}, error: {e}")
            return None
    
    async def reason_and_act(self, messages: List[Message], context: ToolContext) -> Dict[str, Any]:
        """执行推理和行动循环"""
        # 构建对话历史
        chat_messages = []
        for msg in messages:
            chat_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        logger.info(f"chat_messages: {chat_messages}")

        # 获取LLM响应
        response = await self.llm_service.chat_completion(chat_messages)

        logger.info(f"response: {response}")
        
        # 解析响应
        parsed = self._parse_response(response)
        
        # 如果有行动，执行工具
        if parsed["action"]:
            tool_result = await self._execute_action(parsed["action"], context)
            parsed["observation"] = tool_result
        
        return parsed
    
    async def _execute_action(self, action: Dict[str, Any], context: ToolContext) -> str:
        """执行行动"""
        try:
            tool_name = action.get("tool")
            parameters = action.get("parameters", {})
            
            if not tool_name:
                return "错误：未指定工具名称"
            
            # 执行工具
            result = await self.tool_registry.execute_tool(tool_name, parameters, context)
            
            if result:
                return f"执行成功：{result.content}"
            else:
                return f"执行失败：工具 {tool_name} 不可用或执行出错"
                
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return f"执行出错：{str(e)}"


class MessageProcessor:
    """消息处理器"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            # 加载基础系统提示词
            with open(self.config.system_prompt_path, 'r', encoding='utf-8') as f:
                base_prompt = f.read()
            
            # 加载工具描述JSON文件
            # tools_file = "prompt/ctv-tools.txt"
            # try:
            #     with open(tools_file, 'r', encoding='utf-8') as f:
            #         tools_json = f.read()
                
            #     # 直接将JSON内容添加到系统提示词中
            #     full_prompt = base_prompt + "\n\n# 可用工具\n\n以下是可用的工具列表（JSON格式）：\n\n```json\n" + tools_json + "\n```\n\n# 工具调用格式\n\n当你需要使用工具时，请使用以下格式：\n\n思考：[你的分析和推理]\n\n行动：{\"tool\": \"工具名称\", \"parameters\": {\"参数名\": \"参数值\"}}\n\n然后等待观察结果，再决定下一步行动或给出最终答案。\n\n示例：\n思考：用户想要查看当前目录的文件，我需要使用list工具。\n\n行动：{\"tool\": \"list\", \"parameters\": {\"path\": \"/absolute/path/to/directory\"}}"
                
            #     return full_prompt
                 
            # except Exception as e:
            #     logger.warning(f"Failed to load tools file {tools_file}: {e}")
            #     return base_prompt
            return base_prompt    
                
        except Exception as e:
            logger.warning(f"Failed to load system prompt: {e}")
            return "你是一个专业的编程助手，帮助用户解决编程问题。"
    
    def process_user_input(self, user_input: str, conversation_history: List[Message]) -> List[Message]:
        """处理用户输入，构建消息列表"""
        messages = []
        
        # 添加系统提示词（仅在对话开始时）
        if not conversation_history:
            messages.append(Message(role="system", content=self.system_prompt))
        
        # 添加历史对话
        messages.extend(conversation_history)
        
        # 添加用户消息
        messages.append(Message(role="user", content=user_input))
        
        return messages


class ResultProcessor:
    """结果处理器"""
    
    @staticmethod
    def format_response(result: Dict[str, Any]) -> str:
        """格式化响应"""
        response_parts = []
        
        if result.get("thought"):
            response_parts.append(f"思考：{result['thought']}")
        
        if result.get("action"):
            action = result["action"]
            response_parts.append(f"行动：使用工具 {action.get('tool', '未知')}")
        
        if result.get("observation"):
            response_parts.append(f"观察：{result['observation']}")
        
        if result.get("final_answer"):
            response_parts.append(result["final_answer"])
        
        return "\n\n".join(response_parts) if response_parts else "无响应内容"


class CodeAgent:
    """通用编码问题解决Agent"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.conversation_history: List[Message] = []
        
        # 确保工作目录存在
        import os
        if not os.path.exists(self.config.working_directory):
            os.makedirs(self.config.working_directory, exist_ok=True)
            logger.info(f"Created working directory: {self.config.working_directory}")
        
        # 初始化组件
        self.tool_registry = get_global_registry()
        self.llm_service = LLMService(self.config)
        self.react_engine = ReActEngine(self.llm_service, self.tool_registry)
        self.message_processor = MessageProcessor(self.config)
        self.result_processor = ResultProcessor()
        
        logger.info("CodeAgent initialized successfully")
    
    async def process_query(self, query: str, **kwargs) -> str:
        """处理用户查询"""
        try:
            # 处理消息
            messages = self.message_processor.process_user_input(query, self.conversation_history)
            
            # 创建工具执行上下文
            import uuid
            context = ToolContext(
                session_id=str(uuid.uuid4()),
                message_id=str(uuid.uuid4()),
                agent="CodeAgent",
                extra=kwargs
            )
            
            # 执行ReAct循环
            turn_count = 0
            while turn_count < self.config.max_turns:
                result = await self.react_engine.reason_and_act(messages, context)
                
                # 如果有最终答案，结束循环
                if result.get("final_answer"):
                    response = self.result_processor.format_response(result)
                    
                    # 更新对话历史
                    self.conversation_history.extend([
                        Message(role="user", content=query),
                        Message(role="assistant", content=response)
                    ])
                    
                    return response
                
                # 如果有观察结果，添加到消息历史继续推理
                if result.get("observation"):
                    messages.append(Message(
                        role="assistant", 
                        content=f"思考：{result.get('thought', '')}\n行动：{result.get('action', {}).get('tool', '')}"
                    ))
                    messages.append(Message(
                        role="tool",
                        content=f"观察：{result['observation']}"
                    ))
                
                turn_count += 1
            
            # 达到最大轮数限制
            response = "抱歉，经过多轮推理仍未找到满意的答案，请尝试重新描述问题或提供更多信息。"
            self.conversation_history.extend([
                Message(role="user", content=query),
                Message(role="assistant", content=response)
            ])
            
            return response
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            error_response = f"处理查询时发生错误：{str(e)}"
            self.conversation_history.extend([
                Message(role="user", content=query),
                Message(role="assistant", content=error_response)
            ])
            return error_response
    
    async def process_query_stream(self, query: str, **kwargs) -> AsyncGenerator[str, None]:
        """流式处理用户查询"""
        try:
            # 这里可以实现流式响应
            # 为简化实现，先调用非流式版本
            response = await self.process_query(query, **kwargs)
            yield response
        except Exception as e:
            yield f"流式处理出错：{str(e)}"
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
        logger.info("Conversation history cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "conversation_turns": len(self.conversation_history),
            "available_tools": len(self.tool_registry.get_tool_ids(enabled_only=True)),
            "config": {
                "max_turns": self.config.max_turns,
                "model": self.config.model,
                "working_directory": self.config.working_directory
            }
        }
