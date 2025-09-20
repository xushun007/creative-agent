#!/usr/bin/env python3
"""
Creative Agent System - Main Entry Point

A minimal, modular creative agent system that can autonomously complete 
creative tasks through a think-act-observe loop.
"""

import os
import sys
from openai import OpenAI
from agent.smart_controller import SmartAgentController


def get_openai_client():
    """Initialize OpenAI client with configuration."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        sys.exit(1)
    
    # Support for custom base URL (e.g., for local models or other providers)
    base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        # Test connection
        client.models.list()
        return client
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize OpenAI client: {e}")
        sys.exit(1)


def print_banner():
    """Print system banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    🎨 CREATIVE AGENT SYSTEM                   ║
║                                                              ║
║  A minimal, modular agent for autonomous creative tasks      ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def get_user_goal():
    """Get creative goal from user input."""
    print("\nWhat creative task would you like me to help you with?")
    print("Examples:")
    print("  • Write a short science fiction story about a sentient teapot")
    print("  • Create a haiku collection about seasons")
    print("  • Draft a blog post about sustainable living")
    print("  • Write a product description for a new gadget")
    
    print("\n" + "─" * 60)
    goal = input("🎯 Your Goal: ").strip()
    
    if not goal:
        print("❌ Goal cannot be empty. Please try again.")
        return get_user_goal()
    
    return goal


def main():
    """Main entry point for the Creative Agent System."""
    print_banner()
    
    # Initialize OpenAI client
    print("🔌 Initializing AI client...")
    client = get_openai_client()
    print("✅ AI client initialized successfully")
    
    # Get user goal
    goal = get_user_goal()
    
    # Initialize and run agent
    max_turns = int(os.getenv('MAX_TURNS_PER_STEP', '20'))
    controller = SmartAgentController(client, max_turns_per_step=max_turns)
    
    try:
        controller.run(goal)
    except KeyboardInterrupt:
        print("\n\n⚠️  Execution interrupted by user")
        print("Goodbye! 👋")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()