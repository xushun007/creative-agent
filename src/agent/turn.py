"""Turn类 - 代表一次与LLM的交互"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import json
import logging
from agent.code_agent import LLMService
from tools.base_tool import ToolContext, ToolResult
from tools.registry import ToolRegistry, get_global_registry

# logger = logging.getLogger(__name__)
from utils.logger import logger


@dataclass
class ThoughtResult:
    """思考结果"""
    subject: str  # 思考主题
    description: str  # 思考内容


@dataclass
class ToolCallRequest:
    """工具调用请求 - 基于OpenAI工具调用格式"""
    call_id: str
    name: str
    args: Dict[str, Any]
    
    def __str__(self) -> str:
        return f"ToolCall({self.name}, {self.args})"
    
    @classmethod
    def from_openai_tool_call(cls, tool_call) -> 'ToolCallRequest':
        """从OpenAI工具调用对象创建请求"""
        return cls(
            call_id=tool_call.id,
            name=tool_call.function.name,
            args=json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
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
class TurnResult:
    """Turn执行结果"""
    # 文本内容
    text_content: str = ""
    
    # 思考内容
    thoughts: List[ThoughtResult] = field(default_factory=list)
    
    # 工具调用
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    tool_responses: List[ToolCallResponse] = field(default_factory=list)
    
    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: Optional[int] = None
    
    def has_tool_calls(self) -> bool:
        """是否包含工具调用"""
        return len(self.tool_calls) > 0
    
    def has_successful_tool_calls(self) -> bool:
        """是否有成功的工具调用"""
        return any(resp.success for resp in self.tool_responses)
    
    def get_tool_results_text(self) -> str:
        """获取工具执行结果的文本表示"""
        if not self.tool_responses:
            return ""
        
        results = []
        for resp in self.tool_responses:
            if resp.success:
                results.append(f"工具执行成功: {resp.result}")
            else:
                results.append(f"工具执行失败: {resp.error}")
        
        return "\n".join(results)


class ToolExecutor:
    """工具执行器 - 负责执行工具调用，使用现有的工具系统"""
    
    def __init__(self, tool_registry: ToolRegistry = None):
        self.tool_registry = tool_registry or get_global_registry()
    
    async def execute_tool_call(self, tool_call: ToolCallRequest, context: ToolContext) -> ToolCallResponse:
        """执行单个工具调用"""
        try:
            logger.info(f"执行工具调用: {tool_call}")
            
            # 使用现有工具系统执行工具
            tool_result = await self.tool_registry.execute_tool(
                tool_call.name, 
                tool_call.args, 
                context
            )
            logger.info(f"tool_result: {tool_result}")
            
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
    
    async def execute_tool_calls(self, tool_calls: List[ToolCallRequest], context: ToolContext) -> List[ToolCallResponse]:
        """执行多个工具调用"""
        responses = []
        
        for tool_call in tool_calls:
            response = await self.execute_tool_call(tool_call, context)
            responses.append(response)
            
            # 如果有工具执行失败，记录警告但继续执行其他工具
            if not response.success:
                logger.warning(f"工具调用失败，但继续执行其他工具: {response.error}")
        
        return responses
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表，用于构建系统提示词"""
        return self.tool_registry.get_tools_dict(enabled_only=True)


class Turn:
    """Turn类 - 代表一次与LLM的交互"""
    
    def __init__(self, llm_service: LLMService, tool_executor: Optional[ToolExecutor] = None):
        self.llm_service = llm_service
        self.tool_executor = tool_executor or ToolExecutor()
    
    def _parse_openai_response(self, response) -> TurnResult:
        """解析OpenAI SDK响应对象"""
        result = TurnResult()
        
        if not response or not response.choices:
            return result
        
        choice = response.choices[0]
        message = choice.message
        
        # 提取文本内容
        if message.content:
            result.text_content = message.content
        
        # 提取推理内容（DeepSeek等模型特有）
        if hasattr(message, 'reasoning_content') and message.reasoning_content:
            result.thoughts.append(ThoughtResult(
                subject="推理",
                description=message.reasoning_content
            ))
        
        # 提取工具调用
        if message.tool_calls:
            for tool_call in message.tool_calls:
                try:
                    tool_request = ToolCallRequest.from_openai_tool_call(tool_call)
                    result.tool_calls.append(tool_request)
                except Exception as e:
                    logger.warning(f"解析工具调用失败: {e}")
        
        return result
    
    
    def _build_tool_definitions(self) -> List[Dict[str, Any]]:
        """构建工具定义，用于OpenAI API调用"""
        available_tools = self.tool_executor.get_available_tools()
        
        openai_tools = []
        for tool in available_tools:
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
    
    async def execute(self, messages: List[Dict[str, str]], context: Optional[ToolContext] = None) -> TurnResult:
        """执行一次Turn交互"""
        start_time = datetime.now()
        
        try:
            # 1. 构建工具定义
            tools = self._build_tool_definitions()
            
            # 2. 调用LLM获取响应，包含工具定义
            logger.info("开始LLM调用")
            
            # 使用OpenAI SDK格式调用
            kwargs = {}
            if tools:
                kwargs['tools'] = tools
                kwargs['tool_choice'] = 'auto'  # 让模型自动决定是否调用工具


            logger.info(f"messages: {messages[1:]}")
            llm_response = await self.llm_service.chat_completion_with_tools(messages, **kwargs)
            logger.info(f"llm_response: {llm_response}")

            logger.info(f"LLM响应收到，包含工具调用: {bool(llm_response.choices[0].message.tool_calls if llm_response.choices else False)}")
            
            # 3. 解析LLM响应
            result = self._parse_openai_response(llm_response)
            logger.info(f"result: {result}")
            
            # 4. 执行工具调用（如果有）
            if result.has_tool_calls() and context:
                logger.info(f"执行 {len(result.tool_calls)} 个工具调用")
                tool_responses = await self.tool_executor.execute_tool_calls(
                    result.tool_calls, 
                    context
                )
                result.tool_responses = tool_responses
                logger.info(f"tool_responses result 0: {tool_responses[0].result}")
                logger.info(f"tool_responses: {tool_responses}")
            
            # 5. 计算执行时间
            end_time = datetime.now()
            result.duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            logger.info(f"Turn执行完成，耗时: {result.duration_ms}ms")
            return result
            
        except Exception as e:
            logger.error(f"Turn执行异常: {e}")
            # 返回错误结果
            end_time = datetime.now()
            return TurnResult(
                text_content=f"执行出错: {str(e)}",
                duration_ms=int((end_time - start_time).total_seconds() * 1000)
            )
    
    def format_result_for_conversation(self, result: TurnResult) -> str:
        """将Turn结果格式化为对话内容"""
        parts = []
        
        # 添加思考内容
        for thought in result.thoughts:
            parts.append(f"思考: {thought.description}")
        
        # 添加工具调用信息
        if result.has_tool_calls():
            for i, tool_call in enumerate(result.tool_calls):
                parts.append(f"行动: {tool_call}")
                if i < len(result.tool_responses):
                    response = result.tool_responses[i]
                    if response.success:
                        parts.append(f"观察: {response.result}")
                    else:
                        parts.append(f"观察: 执行失败 - {response.error}")
        
        # 添加文本内容
        if result.text_content:
            parts.append(result.text_content)
        
        return '\n\n'.join(parts) if parts else "无响应内容"
