"""优化后的Turn架构演示"""

import asyncio
import logging
from agent.code_agent import LLMService, AgentConfig
from agent.turn_based_agent import TurnBasedAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def demo_optimized_turn():
    """演示优化后的Turn架构"""
    
    print("=== 优化后的Turn架构演示 ===")
    print("特点:")
    print("1. 使用OpenAI SDK工具调用格式")
    print("2. 集成现有工具系统")
    print("3. 使用提供的系统提示词")
    print("4. 支持自动工具调用")
    print()
    
    # 创建配置
    config = AgentConfig(
        max_turns=5,
        model="deepseek-chat",
        system_prompt_path="prompt/ctv-claude-code-system-prompt-zh.txt"
    )
    
    # 创建LLM服务
    llm_service = LLMService(config)
    
    # 创建Turn-based Agent
    agent = TurnBasedAgent(llm_service, config)
    
    print("输入 'quit' 退出，输入 'clear' 清空对话历史，输入 'tools' 查看可用工具")
    print()
    
    session_id = "optimized_demo"
    
    while True:
        try:
            user_input = input("用户: ").strip()
            
            if user_input.lower() == 'quit':
                break
            elif user_input.lower() == 'clear':
                agent.clear_conversation(session_id)
                print("对话历史已清空")
                continue
            elif user_input.lower() == 'tools':
                # 显示可用工具
                tools = agent.tool_executor.get_available_tools()
                print(f"\n可用工具 ({len(tools)} 个):")
                for tool in tools[:5]:  # 只显示前5个工具
                    print(f"- {tool['name']}: {tool['description'][:100]}...")
                print()
                continue
            elif not user_input:
                continue
            
            print("处理中...")
            
            # 使用单次Turn处理（展示工具自动调用）
            response = await agent.process_user_input(user_input, session_id)
            
            print(f"助手: {response}")
            print()
            
            # 显示Turn详情
            conversation = agent.get_conversation(session_id)
            if conversation and conversation.turns:
                last_turn = conversation.turns[-1]
                print(f"[Turn详情]")
                print(f"- 执行时间: {last_turn.duration_ms}ms")
                print(f"- 思考数量: {len(last_turn.thoughts)}")
                print(f"- 工具调用数量: {len(last_turn.tool_calls)}")
                
                if last_turn.thoughts:
                    print(f"- 思考内容: {last_turn.thoughts[0].description[:50]}...")
                
                if last_turn.has_tool_calls():
                    successful_calls = sum(1 for resp in last_turn.tool_responses if resp.success)
                    print(f"- 成功调用: {successful_calls}/{len(last_turn.tool_calls)}")
                    
                    # 显示工具调用详情
                    for i, tool_call in enumerate(last_turn.tool_calls[:3]):  # 只显示前3个
                        response = last_turn.tool_responses[i] if i < len(last_turn.tool_responses) else None
                        status = "成功" if response and response.success else "失败"
                        print(f"  - {tool_call.name}: {status}")
            
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\n用户中断，退出...")
            break
        except Exception as e:
            print(f"发生错误: {e}")
            logger.error(f"Demo异常: {e}")


async def test_tool_integration():
    """测试工具集成"""
    
    print("=== 工具集成测试 ===")
    
    config = AgentConfig()
    llm_service = LLMService(config)
    agent = TurnBasedAgent(llm_service, config)
    
    test_cases = [
        {
            "name": "文件操作测试",
            "query": "帮我查看当前目录下有哪些Python文件",
            "expected_tools": ["list", "glob"]
        },
        {
            "name": "代码分析测试", 
            "query": "分析agent目录下的Python代码结构",
            "expected_tools": ["list", "read", "grep"]
        },
        {
            "name": "简单对话测试",
            "query": "你好，请介绍一下你自己",
            "expected_tools": []
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- 测试 {i}: {test_case['name']} ---")
        print(f"查询: {test_case['query']}")
        
        try:
            response = await agent.process_user_input(test_case['query'], f"test_{i}")
            print(f"响应: {response[:200]}..." if len(response) > 200 else f"响应: {response}")
            
            # 检查工具调用
            conversation = agent.get_conversation(f"test_{i}")
            if conversation and conversation.turns:
                last_turn = conversation.turns[-1]
                
                if last_turn.has_tool_calls():
                    called_tools = [call.name for call in last_turn.tool_calls]
                    print(f"调用的工具: {called_tools}")
                    
                    # 检查是否符合预期
                    if test_case['expected_tools']:
                        expected_found = any(tool in called_tools for tool in test_case['expected_tools'])
                        print(f"符合预期: {'是' if expected_found else '否'}")
                else:
                    print("未调用工具")
                    print(f"符合预期: {'是' if not test_case['expected_tools'] else '否'}")
            
        except Exception as e:
            print(f"测试失败: {e}")


async def show_system_prompt():
    """显示系统提示词"""
    
    print("=== 系统提示词展示 ===")
    
    config = AgentConfig(system_prompt_path="prompt/ctv-claude-code-system-prompt-zh.txt")
    llm_service = LLMService(config)
    agent = TurnBasedAgent(llm_service, config)
    
    system_prompt = agent._load_system_prompt()
    
    print("系统提示词长度:", len(system_prompt))
    print()
    print("前500个字符:")
    print(system_prompt[:500] + "...")
    print()
    print("工具相关部分:")
    
    # 提取工具相关部分
    if "# 可用工具" in system_prompt:
        tools_section = system_prompt.split("# 可用工具")[1]
        if "# 工具使用说明" in tools_section:
            tools_section = tools_section.split("# 工具使用说明")[0]
        
        lines = tools_section.split('\n')[:20]  # 只显示前20行
        for line in lines:
            print(line)
        print("...")


if __name__ == "__main__":
    print("选择演示模式:")
    print("1. 交互式Turn演示")
    print("2. 工具集成测试")
    print("3. 系统提示词展示")
    
    choice = input("请选择 (1/2/3): ").strip()
    
    if choice == "1":
        asyncio.run(demo_optimized_turn())
    elif choice == "2":
        asyncio.run(test_tool_integration())
    elif choice == "3":
        asyncio.run(show_system_prompt())
    else:
        print("无效选择")
