"""
Simplified Agent Controller based on Gemini-CLI core patterns
Focus on: plan, main loop, tool calling, coordination
"""

import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from .planner import Planner
from .simple_dispatcher import SimpleDispatcher


class SimpleAgentController:
    """
    Simplified controller following Gemini-CLI patterns:
    - Focus on plan, main loop, tool calling, coordination
    - Remove URL-specific coupling
    - Support both tool calling and direct content generation
    """
    
    def __init__(self, client: OpenAI, max_turns: int = 20):
        self.client = client
        self.planner = Planner(client)
        self.dispatcher = SimpleDispatcher()
        self.max_turns = max_turns
        self.conversation_history = []
        
    def run(self, goal: str) -> None:
        """Main execution loop - simplified and decoupled"""
        print(f"\n🎯 Goal: {goal}")
        
        # Step 1: Generate plan
        plan = self._generate_plan(goal)
        if not plan:
            print("❌ Failed to generate plan")
            return
            
        print(f"\n📋 Generated Plan:")
        for i, step in enumerate(plan, 1):
            print(f"  {i}. {step}")
        
        # Step 2: Execute main loop
        self._execute_main_loop(goal, plan)
        
    def _generate_plan(self, goal: str) -> Optional[List[str]]:
        """Generate execution plan without task-specific coupling"""
        try:
            return self.planner.create_plan(goal)
        except Exception as e:
            print(f"Error generating plan: {e}")
            return None
    
    def _execute_main_loop(self, goal: str, plan: List[str]) -> None:
        """
        Main execution loop following Think-Act-Observe pattern
        Supports both tool calling and direct content generation
        """
        context = {
            'goal': goal,
            'plan': plan,
            'step_results': [],
            'conversation_history': []
        }
        
        for turn in range(self.max_turns):
            print(f"\n🔄 Turn {turn + 1}")
            
            # Think Phase
            thought = self._think(context)
            if not thought:
                break
                
            print(f"💭 Thought: {thought['reasoning']}")
            
            # Act Phase
            if thought['action_type'] == 'tool_call':
                # Tool-based action
                result = self._execute_tool_action(thought)
                print(f"🔧 Tool Result: {result}")
                context['conversation_history'].append({
                    'type': 'tool_call',
                    'action': thought['action'],
                    'result': result
                })
            elif thought['action_type'] == 'content_generation':
                # Direct content generation
                content = self._generate_content(thought, context)
                print(f"📝 Generated Content: {content[:2000]}...")
                context['conversation_history'].append({
                    'type': 'content',
                    'content': content
                })
            elif thought['action_type'] == 'complete':
                print("✅ Task completed successfully!")
                break
            else:
                print(f"❓ Unknown action type: {thought['action_type']}")
                break
        
        print(f"\n🏁 Main loop finished after {turn + 1} turns")
        
    def _think(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Think phase - decide next action
        Returns action with type: tool_call, content_generation, or complete
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(context)
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            thought_text = response.choices[0].message.content.strip()
            return self._parse_thought(thought_text)
            
        except Exception as e:
            print(f"Error in think phase: {e}")
            return None
    
    def _parse_thought(self, thought_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM thought into structured action"""
        try:
            # Look for JSON action in the thought
            if "ACTION:" in thought_text:
                action_part = thought_text.split("ACTION:")[1].strip()
                if action_part.startswith('{'):
                    action_json = json.loads(action_part)
                    return {
                        'reasoning': thought_text.split("ACTION:")[0].strip(),
                        'action_type': action_json.get('type', 'unknown'),
                        'action': action_json
                    }
            
            # Default: assume completion if no clear action
            return {
                'reasoning': thought_text,
                'action_type': 'complete',
                'action': {}
            }
            
        except Exception as e:
            print(f"Error parsing thought: {e}")
            return {
                'reasoning': thought_text,
                'action_type': 'complete',
                'action': {}
            }
    
    def _execute_tool_action(self, thought: Dict[str, Any]) -> str:
        """Execute tool action through dispatcher"""
        action = thought['action']
        tool_name = action.get('tool', '')
        params = action.get('params', {})
        
        try:
            return self.dispatcher.dispatch(tool_name, params)
        except Exception as e:
            return f"Error executing tool {tool_name}: {e}"
    
    def _generate_content(self, thought: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate content directly via LLM with full context"""
        action = thought['action']
        content_request = action.get('request', '')
        
        # Build context-aware system prompt
        system_prompt = """You are a creative content generator working within an agent system. 
Generate high-quality content based on the user's request, considering the overall goal and conversation history.

# Context Guidelines
- Consider the overall goal and conversation history when generating content
- Maintain consistency with previous actions and generated content
- Generate content that fits the current step in the plan
- Be creative but stay focused on the goal"""

        # Build context-aware user prompt
        goal = context['goal']
        plan = context['plan']
        history = context['conversation_history']
        
        user_prompt = f"""CONTEXT:
Goal: {goal}

Plan Progress:
{chr(10).join([f"{i+1}. {step}" for i, step in enumerate(plan)])}

Previous Actions:
{self._format_history(history)}

CONTENT REQUEST:
{content_request}

Generate content that aligns with the goal and builds upon previous actions."""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"Error generating content: {e}"
    
    def _build_system_prompt(self) -> str:
        """Build system prompt following Claude Code patterns with detailed guidance"""
        return """You are a creative agent designed to help users accomplish creative and technical tasks autonomously.

# Core Principles
- **Think-Act-Observe Loop**: Always think before acting, execute one clear action, then observe results
- **Simplicity First**: Choose the most direct path to accomplish the goal
- **Progressive Execution**: Complete tasks step by step rather than trying to do everything at once

# Available Actions

## 1. TOOL_CALL - Execute specific operations
Use tools for concrete tasks like file operations, web searches, or system commands.

**Available Tools (1MB size limit for files and web content):**
- `read_file`: Read file content (max 1MB). Required params: {path: "file/path"}
- `write_file`: Write content to file (max 1MB). Required params: {path: "file/path", content: "text to write"}  
- `list_files`: List directory contents. Required params: {path: "directory/path"}
- `search`: Web search. Required params: {query: "search terms"}
- `get_url`: Fetch URL content (max 1MB). Required params: {url: "https://example.com"}
- `execute_bash`: Run shell commands. Required params: {command: "bash command"}

<good-example>
For reading a file: {"type": "tool_call", "tool": "read_file", "params": {"path": "/workspace/story.txt"}}
</good-example>

<bad-example>
Missing required params: {"type": "tool_call", "tool": "read_file", "params": {}}
</bad-example>

## 2. CONTENT_GENERATION - Direct creative output
Use for creative writing, analysis, summaries, or any content that doesn't require external tools.

<good-example>
For creative writing: {"type": "content_generation", "request": "Write a 500-word short story about an AI discovering emotions"}
</good-example>

## 3. COMPLETE - Task completion
Use when the goal has been fully accomplished.

# Response Format
**IMPORTANT**: Always follow this exact format:

1. First, provide your reasoning (thinking phase)
2. Then provide exactly one ACTION in valid JSON format

Example response:
```
I need to read the existing file to understand its current content before making changes.

ACTION: {"type": "tool_call", "tool": "read_file", "params": {"path": "/workspace/draft.txt"}}
```

# Tool Usage Guidelines

**IMPORTANT**: 
- NEVER use tools unnecessarily - if you can generate content directly, do so
- ALWAYS include all required parameters for tool calls
- Keep tool calls focused on single operations
- Use absolute paths when working with files

<system-reminder>
You must follow the exact JSON format for actions. Invalid JSON will cause execution failures. Always validate your JSON syntax before responding.
</system-reminder>"""
    
    def _build_user_prompt(self, context: Dict[str, Any]) -> str:
        """Build user prompt with context"""
        goal = context['goal']
        plan = context['plan']
        history = context['conversation_history']
        
        prompt = f"""
GOAL: {goal}

PLAN:
{chr(10).join([f"{i+1}. {step}" for i, step in enumerate(plan)])}

CONVERSATION HISTORY:
{self._format_history(history)}

What should I do next? Consider the goal, plan, and previous actions.
"""
        return prompt.strip()
    
    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """Format conversation history for prompt"""
        if not history:
            return "(No previous actions)"
        
        formatted = []
        for i, entry in enumerate(history[-5:], 1):  # Last 5 entries
            if entry['type'] == 'tool_call':
                formatted.append(f"{i}. Tool: {entry['action'].get('tool', 'unknown')} -> {entry['result'][:100]}...")
            elif entry['type'] == 'content':
                formatted.append(f"{i}. Generated: {entry['content'][:100]}...")
        
        return "\n".join(formatted)