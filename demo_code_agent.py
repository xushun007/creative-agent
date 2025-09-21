#!/usr/bin/env python3
"""CodeAgent演示脚本"""

import asyncio
import logging
import os
from agent.code_agent import CodeAgent, AgentConfig


async def demo():
    """演示CodeAgent功能"""
    print("🚀 CodeAgent演示")
    print("=" * 40)
    
    # 设置日志级别
    logging.basicConfig(level=logging.WARNING)
    
    # 创建Agent配置
    workspace_dir = os.path.join(os.getcwd(), "workspace")
    config = AgentConfig(
        max_turns=3,  # 限制轮数以便演示
        model="deepseek-chat",
        working_directory=workspace_dir
    )
    
    # 初始化Agent
    agent = CodeAgent(config)
    
    # 测试查询列表
    test_queries = [
        "列出当前目录的文件结构",
        "查找所有Python文件",
        "显示这个项目的统计信息"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 测试 {i}: {query}")
        print("-" * 30)
        
        try:
            # 模拟处理（不调用真实的LLM）
            print("🤖 模拟响应：")
            
            if "列出" in query and "目录" in query:
                print("思考：用户想要查看当前目录结构")
                print("行动：使用list工具列出目录")
                print("观察：成功获取目录结构")
                print("最终答案：当前目录包含以下文件和子目录：...")
                
            elif "查找" in query and "Python" in query:
                print("思考：用户想要查找Python文件")
                print("行动：使用glob工具搜索*.py文件")
                print("观察：找到多个Python文件")
                print("最终答案：找到以下Python文件：...")
                
            elif "统计信息" in query:
                stats = agent.get_statistics()
                print(f"项目统计信息：{stats}")
                
        except Exception as e:
            print(f"❌ 演示出错：{e}")
    
    print("\n✅ 演示完成！")
    print("\n💡 实际使用时，Agent会：")
    print("1. 根据用户问题自动选择合适的工具")
    print("2. 执行ReAct推理循环")
    print("3. 调用真实的LLM进行思考和决策")
    print("4. 返回详细的执行结果")


if __name__ == "__main__":
    asyncio.run(demo())
