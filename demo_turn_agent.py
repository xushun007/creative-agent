"""Turn-based Agent 演示"""

import asyncio
from agent.code_agent import LLMService, AgentConfig
from agent.turn_based_agent import TurnBasedAgent

from utils.logger import logger



async def demo_turn_agent():
    """演示Turn-based Agent的使用"""
    
    # 创建配置
    config = AgentConfig(
        max_turns=5,
        model="deepseek-r1",
        system_prompt_path="prompt/ctv-claude-code-system-prompt-zh.txt"
    )
    
    # 创建LLM服务
    llm_service = LLMService(config)
    
    # 创建Turn-based Agent
    agent = TurnBasedAgent(llm_service, config)
    
    print("=== Turn-based Agent 演示 ===")
    print("输入 'quit' 退出，输入 'clear' 清空对话历史")
    print()
    
    session_id = "demo_session"
    
    while True:
        try:
            user_input = input("用户: ").strip()
            
            if user_input.lower() == 'quit':
                break
            elif user_input.lower() == 'clear':
                agent.clear_conversation(session_id)
                print("对话历史已清空")
                continue
            elif not user_input:
                continue
            
            print("思考中...")
            
            # 使用多轮推理处理
            response = await agent.multi_turn_reasoning(user_input, session_id)
            
            print(f"助手: {response}")
            print()
            
            # 显示统计信息
            stats = agent.get_statistics()
            print(f"[统计] 对话数: {stats['active_conversations']}, "
                  f"消息数: {stats['total_messages']}, "
                  f"Turn数: {stats['total_turns']}")
            print("-" * 50)
            
        except KeyboardInterrupt:
            print("\n用户中断，退出...")
            break
        except Exception as e:
            print(f"发生错误: {e}")
            logger.error(f"Demo异常: {e}")


async def demo_single_turn():
    """演示单次Turn交互"""
    
    config = AgentConfig()
    llm_service = LLMService(config)
    agent = TurnBasedAgent(llm_service, config)
    
    print("=== 单次Turn交互演示 ===")
    
    test_queries = [
        "你好，请介绍一下你自己",
        "帮我查看当前目录下的文件",
        "创建一个简单的Python Hello World程序"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- 测试 {i}: {query} ---")
        
        try:
            response = await agent.process_user_input(query, f"test_session_{i}")
            print(f"响应: {response}")
            
            # 获取对话记录
            conversation = agent.get_conversation(f"test_session_{i}")
            if conversation and conversation.turns:
                last_turn = conversation.turns[-1]
                print(f"Turn详情:")
                print(f"  - 思考数量: {len(last_turn.thoughts)}")
                print(f"  - 工具调用数量: {len(last_turn.tool_calls)}")
                print(f"  - 执行时间: {last_turn.duration_ms}ms")
                
                if last_turn.has_tool_calls():
                    print(f"  - 工具调用成功: {last_turn.has_successful_tool_calls()}")
            
        except Exception as e:
            print(f"测试失败: {e}")


if __name__ == "__main__":
    print("选择演示模式:")
    print("1. 交互式对话")
    print("2. 单次Turn测试")
    
    choice = input("请选择 (1 或 2): ").strip()
    
    if choice == "1":
        asyncio.run(demo_turn_agent())
    elif choice == "2":
        asyncio.run(demo_single_turn())
    else:
        print("无效选择")
