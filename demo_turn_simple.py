"""Turn类简洁演示程序"""

import asyncio
import logging
from agent.turn import Turn, ToolExecutor
from agent.code_agent import LLMService, AgentConfig, MessageProcessor
from tools.base_tool import ToolContext
import uuid

# 日志已在utils/logger.py中配置，无需重复配置
# logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')

async def demo_turn():
    """演示Turn类基本功能"""
    print("=== Turn类演示 ===\n")
    
    # 1. 初始化组件
    config = AgentConfig(model="deepseek-chat")
    llm_service = LLMService(config)
    tool_executor = ToolExecutor()
    turn = Turn(llm_service, tool_executor)
    
    # 2. 创建上下文
    context = ToolContext(
        session_id=str(uuid.uuid4()),
        message_id=str(uuid.uuid4()),
        agent="TurnDemo"
    )
    
    system_prompt_path = "prompt/ctv-claude-code-system-prompt-zh.txt"
    with open(system_prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    # 3. 测试用例
    test_cases = [
        # {
        #     "name": "纯文本对话",
        #     "messages": [
        #         {"role": "system", "content": MessageProcessor().system_prompt},
        #         {"role": "user", "content": "你好，请简单介绍一下你自己"}
        #     ]
        # },


        # {
        #     "name": "需要工具调用",
        #     "messages": [
        #         {"role": "system", "content": system_prompt},
        #         {"role": "user", "content": "总结 https://minusx.ai/blog/decoding-claude-code 内容，并输出总结结果到 s.txt中"}
        #     ]
        # },

        # {
        #     "name": "需要工具调用",
        #     "messages": [
        #         {"role": "system", "content": system_prompt},
        #         {"role": "user", "content": "实现一个类似于抖音 核心版本的小程序，需要包括以下功能：1. 视频上传 2. 视频播放 3. 视频点赞 4. 视频评论 5. 视频分享。建议使用TodoWrite 管理规划"}
        #     ]
        # },


        {
            "name": "需要工具调用",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "搜索存在大模型调用相关的代码"}
            ]
        },

        # {
        #     "name": "需要工具调用",
        #     "messages": [
        #         {"role": "system", "content": system_prompt},
        #         {"role": "user", "content": "帮我查看当前目录下有哪些文件"}
        #     ]
        # }
    ]
    
    # 4. 执行测试
    for i, test_case in enumerate(test_cases, 1):
        print(f"测试 {i}: {test_case['name']}")
        print("-" * 40)
        
        try:
            # 执行Turn
            result = await turn.execute(test_case['messages'], context)
            
            # 显示结果
            print(f"执行时间: {result.duration_ms}ms")
            print(f"文本内容: {result.text_content[:10000]}...")
            print(f"思考数量: {len(result.thoughts)}")
            print(f"工具调用: {len(result.tool_calls)}")
            
            if result.thoughts:
                print(f"思考示例: {result.thoughts[0].description[:1000]}...")
            
            if result.has_tool_calls():
                print("工具调用详情:")
                for j, tool_call in enumerate(result.tool_calls[:3]):
                    response = result.tool_responses[j] if j < len(result.tool_responses) else None
                    status = "✓" if response and response.success else "✗"
                    print(f"  {status} {tool_call.name}({list(tool_call.args.keys())})")
            
            print(f"完整响应:\n{turn.format_result_for_conversation(result)[:200]}...\n")
            
        except Exception as e:
            print(f"测试失败: {e}\n")

if __name__ == "__main__":
    asyncio.run(demo_turn())
