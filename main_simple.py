"""
Simplified Main Entry Point
Clean architecture following gemini-cli patterns
"""

import os
from openai import OpenAI
from agent.simple_controller import SimpleAgentController


def main():
    """Main entry point with simplified architecture"""
    
    # Initialize OpenAI client with DashScope
    api_key = os.getenv('DASHSCOPE_API_KEY')
    if not api_key:
        print("❌ Error: DASHSCOPE_API_KEY environment variable not set")
        return
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    
    # Initialize simplified controller
    controller = SimpleAgentController(client)
    
    # Get user goal
    print("🤖 Creative Agent - Simplified Architecture")
    print("Enter your creative goal (or 'quit' to exit):")
    
    while True:
        try:
            goal = input("\n> ").strip()
            if goal.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not goal:
                continue
                
            # Execute goal
            controller.run(goal)
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()