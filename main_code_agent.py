#!/usr/bin/env python3
"""CodeAgent命令行入口"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from agent.code_agent import CodeAgent, AgentConfig


def setup_logging(level=logging.INFO):
    """设置日志"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


async def main():
    """主函数"""
    setup_logging()
    
    print("🤖 CodeAgent - 通用编程助手")
    print("输入 'quit' 或 'exit' 退出，输入 'clear' 清空历史")
    print("=" * 50)
    
    # 初始化Agent
    current_dir = os.getcwd()
    workspace_dir = os.path.join(current_dir, "workspace")
    
    config = AgentConfig(
        max_turns=10,
        model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
        working_directory=workspace_dir
    )
    
    agent = CodeAgent(config)
    
    while True:
        try:
            # 获取用户输入
            user_input = input("\n👤 ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['quit', 'exit']:
                print("👋 再见！")
                break
                
            if user_input.lower() == 'clear':
                agent.clear_history()
                print("🧹 历史记录已清空")
                continue
                
            if user_input.lower() == 'stats':
                stats = agent.get_statistics()
                print(f"📊 统计信息：{stats}")
                continue
            
            # 处理查询
            print("🤖 思考中...")
            response = await agent.process_query(user_input)
            print(f"\n🤖 {response}")
            
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 错误：{e}")
            logging.error(f"Main loop error: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception as e:
        print(f"❌ 启动失败：{e}")
        sys.exit(1)
