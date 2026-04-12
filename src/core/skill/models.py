"""Skill 数据结构定义"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class SkillSource(str, Enum):
    """Skill 来源"""
    BUNDLED = "bundled"
    USER = "user"
    PROJECT = "project"


@dataclass
class SkillInfo:
    """Skill 元数据"""
    id: str
    name: str
    description: str = ""
    argument_hint: Optional[str] = None
    when_to_use: Optional[str] = None
    allowed_tools: List[str] = field(default_factory=list)
    user_invocable: bool = True
    source: SkillSource = SkillSource.PROJECT
    paths: Optional[List[str]] = None
    version: Optional[str] = None
    model: Optional[str] = None
    disable_model_invocation: bool = False


@dataclass
class Skill:
    """完整 Skill 定义"""
    info: SkillInfo
    prompt_template: str
    base_dir: Optional[str] = None
    hooks: Optional[Dict[str, Any]] = None
    file_path: Optional[Path] = None

    def render(self, arguments: str, context: Dict[str, Any]) -> str:
        """渲染提示词，替换参数变量"""
        result = self.prompt_template

        # 替换 ${ARGUMENTS}
        result = result.replace("${ARGUMENTS}", arguments)

        # 替换位置参数 ${1}, ${2}, ...
        if arguments:
            args_list = arguments.split()
            for i, arg in enumerate(args_list, start=1):
                result = result.replace(f"${{{i}}}", arg)

        # 替换命名参数 ${name}
        if context.get("named_args"):
            for name, value in context["named_args"].items():
                result = result.replace(f"${{{name}}}", value)

        # 替换 Skill 目录变量（主名 + 兼容别名）
        if self.base_dir:
            result = result.replace("${CTV_SKILL_DIR}", self.base_dir)
            result = result.replace("${CLAUDE_SKILL_DIR}", self.base_dir)

        # 替换 ${CLAUDE_SESSION_ID}
        if context.get("session_id"):
            result = result.replace(
                "${CLAUDE_SESSION_ID}",
                context["session_id"]
            )

        return result
