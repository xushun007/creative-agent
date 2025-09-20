"""基于Turn的Agent实现"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .turn import Turn, ToolExecutor, TurnResult, ThoughtResult
from tools import get_global_registry, ToolContext

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """消息类"""
    role: str  # user, assistant, system, tool
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """对话会话"""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    turns: List[TurnResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class TurnBasedAgent:
    """基于Turn的Agent"""
    
    def __init__(self, llm_service, config=None):
        self.llm_service = llm_service
        self.config = config
        
        # 初始化工具相关组件
        self.tool_registry = get_global_registry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        
        # 初始化Turn
        self.turn = Turn(llm_service, self.tool_executor)
        
        # 对话管理
        self.conversations: Dict[str, Conversation] = {}
        
        logger.info("TurnBasedAgent初始化完成")
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词，结合工具定义"""
        try:
            # 1. 加载基础系统提示词
            base_prompt = ""
            if self.config and hasattr(self.config, 'system_prompt_path'):
                with open(self.config.system_prompt_path, 'r', encoding='utf-8') as f:
                    base_prompt = f.read()
            
            # 2. 获取可用工具信息
            available_tools = self.tool_executor.get_available_tools()
            
            # 3. 构建工具信息说明
            tools_info = "\n\n# 可用工具\n\n以下是您可以使用的工具列表：\n\n"
            
            for tool in available_tools:
                tools_info += f"## {tool['name']}\n"
                tools_info += f"- **描述**: {tool['description']}\n"
                
                # 添加参数信息
                if tool['parameters'].get('properties'):
                    tools_info += "- **参数**:\n"
                    for param_name, param_info in tool['parameters']['properties'].items():
                        param_type = param_info.get('type', 'unknown')
                        param_desc = param_info.get('description', '无描述')
                        required = param_name in tool['parameters'].get('required', [])
                        required_mark = " (必需)" if required else " (可选)"
                        tools_info += f"  - `{param_name}` ({param_type}){required_mark}: {param_desc}\n"
                
                tools_info += "\n"
            
            # 4. 添加工具使用说明
            usage_instructions = """
# 工具使用说明

当您需要执行具体操作时，系统会自动调用相应的工具。您只需要在思考过程中说明需要做什么，系统会自动选择和调用合适的工具。

例如：
- 当您说"我需要查看当前目录的文件"时，系统会自动调用list工具
- 当您说"我需要读取某个文件的内容"时，系统会自动调用read工具
- 当您说"我需要创建一个文件"时，系统会自动调用write工具

您的主要任务是：
1. 理解用户需求
2. 进行思考和分析
3. 说明需要执行的操作
4. 根据工具执行结果继续分析或给出最终答案
"""
            
            # 5. 组合完整的系统提示词
            full_prompt = base_prompt + tools_info + usage_instructions
            
            return full_prompt
            
        except Exception as e:
            logger.warning(f"加载系统提示词失败: {e}")
            return "你是一个专业的编程助手，帮助用户解决编程问题。"
    
    def _build_messages_for_llm(self, conversation: Conversation, new_user_message: str) -> List[Dict[str, str]]:
        """构建发送给LLM的消息列表"""
        messages = []
        
        # 添加系统提示词
        messages.append({
            "role": "system",
            "content": self._load_system_prompt()
        })
        
        # 添加历史对话
        for msg in conversation.messages[-10:]:  # 只保留最近10条消息避免上下文过长
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # 添加新的用户消息
        messages.append({
            "role": "user",
            "content": new_user_message
        })
        
        return messages
    
    async def process_user_input(self, user_input: str, session_id: str = "default") -> str:
        """处理用户输入并返回响应"""
        try:
            # 获取或创建对话
            if session_id not in self.conversations:
                self.conversations[session_id] = Conversation(session_id=session_id)
            
            conversation = self.conversations[session_id]
            
            # 构建LLM消息
            llm_messages = self._build_messages_for_llm(conversation, user_input)
            
            # 创建工具执行上下文
            import uuid
            context = ToolContext(
                session_id=session_id,
                message_id=str(uuid.uuid4()),
                agent="TurnBasedAgent"
            )
            
            # 执行Turn
            logger.info(f"开始处理用户输入: {user_input}")
            turn_result = await self.turn.execute(llm_messages, context)
            
            # 格式化响应
            response = self.turn.format_result_for_conversation(turn_result)
            
            # 更新对话历史
            conversation.messages.append(Message(role="user", content=user_input))
            conversation.messages.append(Message(role="assistant", content=response))
            conversation.turns.append(turn_result)
            
            logger.info(f"用户输入处理完成，响应长度: {len(response)}")
            return response
            
        except Exception as e:
            logger.error(f"处理用户输入时发生异常: {e}")
            error_response = f"处理请求时发生错误: {str(e)}"
            
            # 记录错误到对话历史
            if session_id in self.conversations:
                self.conversations[session_id].messages.extend([
                    Message(role="user", content=user_input),
                    Message(role="assistant", content=error_response)
                ])
            
            return error_response
    
    async def multi_turn_reasoning(self, user_input: str, session_id: str = "default", max_turns: int = 10) -> str:
        """多轮推理处理 - 持续执行直到得到最终答案"""
        try:
            if session_id not in self.conversations:
                self.conversations[session_id] = Conversation(session_id=session_id)
            
            conversation = self.conversations[session_id]
            
            # 添加初始用户消息
            conversation.messages.append(Message(role="user", content=user_input))
            
            turn_count = 0
            while turn_count < max_turns:
                # 构建当前消息列表
                llm_messages = []
                
                # 系统提示词
                llm_messages.append({
                    "role": "system", 
                    "content": self._load_system_prompt()
                })
                
                # 最近的对话历史
                for msg in conversation.messages[-10:]:
                    llm_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
                
                # 创建工具执行上下文
                import uuid
                context = ToolContext(
                    session_id=session_id,
                    message_id=str(uuid.uuid4()),
                    agent="TurnBasedAgent"
                )
                
                # 执行Turn
                turn_result = await self.turn.execute(llm_messages, context)
                conversation.turns.append(turn_result)
                
                # 检查是否有工具调用
                if turn_result.has_tool_calls():
                    # 添加助手的思考和行动
                    assistant_content_parts = []
                    
                    # 添加思考，这个我觉得有点冗余，先删除
                    # for thought in turn_result.thoughts:
                    #     assistant_content_parts.append(f"思考: {thought.description}")
                    
                    # 添加行动
                    for tool_call in turn_result.tool_calls:
                        assistant_content_parts.append(f"function call: {tool_call}")
                    
                    if assistant_content_parts:
                        conversation.messages.append(Message(
                            role="assistant",
                            content="\n\n".join(assistant_content_parts)
                        ))
                    
                    # 添加工具执行结果
                    if turn_result.tool_responses:
                        tool_results = []
                        for response in turn_result.tool_responses:
                            if response.success:
                                tool_results.append(f"观察: {response.result}")
                            else:
                                tool_results.append(f"观察: 执行失败 - {response.error}")
                        
                        if tool_results:
                            conversation.messages.append(Message(
                                role="user",
                                content="\n".join(tool_results)
                            ))
                    
                    turn_count += 1
                    continue
                
                # 如果没有工具调用，认为是最终答案
                final_response = turn_result.text_content or "无法生成有效响应"
                final_response = final_response + "\n\n请确认最终任务是否已经完成完成，如果是，请返回四个字母 'Done'，不需要有额外的内容 ，否则返回需要继续的原因，在此环节不需要包含工具调用，仅仅做结果的验证"
                conversation.messages.append(Message(
                    role="assistant",
                    content=final_response
                ))

                if not turn_result.has_tool_calls():
                    turn_result = await self.turn.execute(llm_messages, context)
                    conversation.turns.append(turn_result)
                    if turn_result.has_tool_calls():
                        logger.error("最终结果还包含调用，不允许这样！！！")
                        return final_response
                    else:
                        if turn_result.text_content == 'Done':
                            return final_response
                
                #return final_response
            
            # 达到最大轮数限制
            timeout_response = "经过多轮推理仍未找到最终答案，请尝试重新描述问题。"
            conversation.messages.append(Message(
                role="assistant",
                content=timeout_response
            ))
            
            return timeout_response
            
        except Exception as e:
            logger.error(f"多轮推理处理异常: {e}")
            return f"多轮推理处理时发生错误: {str(e)}"
    
    def get_conversation(self, session_id: str) -> Optional[Conversation]:
        """获取指定会话的对话记录"""
        return self.conversations.get(session_id)
    
    def clear_conversation(self, session_id: str):
        """清空指定会话的对话记录"""
        if session_id in self.conversations:
            del self.conversations[session_id]
            logger.info(f"已清空会话 {session_id} 的对话记录")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_messages = sum(len(conv.messages) for conv in self.conversations.values())
        total_turns = sum(len(conv.turns) for conv in self.conversations.values())
        
        return {
            "active_conversations": len(self.conversations),
            "total_messages": total_messages,
            "total_turns": total_turns,
            "available_tools": len(self.tool_registry.get_tool_ids(enabled_only=True))
        }
