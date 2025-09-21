import json
import os
from typing import List
from openai import OpenAI


class Planner:
    def __init__(self, client: OpenAI):
        self.client = client
        # self.model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        self.model = 'deepseek-chat'
        # self.model = 'deepseek-r1'
    
    def create_plan(self, goal: str) -> List[str]:
        """Break down a high-level goal into specific actionable steps."""
        
        prompt = f"""You are a planning assistant. Given a creative goal, break it down into 3-6 specific, actionable steps.

Goal: {goal}

Create a numbered list of concrete steps that describe what needs to be accomplished. Each step should be a high-level task description, not specific tool calls.

Available capabilities include:
- Web content fetching and analysis
- File reading and writing operations  
- Content analysis and summarization
- Text processing and generation

Focus on the logical sequence of tasks needed to accomplish the goal. Use natural language to describe what should be done in each step.

Example format:
1. Gather information about the topic from web sources
2. Analyze the collected information for key points
3. Create a structured summary document
4. Save the results for user review

Return only the numbered list of steps, nothing else."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=5000
        )
        
        plan_text = response.choices[0].message.content.strip()
        
        # Parse the numbered list into individual steps
        steps = []
        for line in plan_text.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('- ')):
                # Remove numbering and clean up
                if line[0].isdigit():
                    step = line.split('.', 1)[1].strip() if '.' in line else line[1:].strip()
                else:
                    step = line[2:].strip()
                steps.append(step)
        
        return steps if steps else [plan_text]
    
    def format_plan_for_display(self, steps: List[str]) -> str:
        """Format the plan for console display."""
        formatted = "📋 PLAN GENERATED:\n"
        for i, step in enumerate(steps, 1):
            formatted += f"  {i}. {step}\n"
        return formatted