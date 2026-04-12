"""Skill 执行器 - 执行 Skill 并生成提示词"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import fnmatch

from .models import Skill, SkillSource
from .registry import SkillRegistry


class SkillExecutor:
    """Skill 执行器"""

    def __init__(self, registry: SkillRegistry):
        self._registry = registry
        # 条件激活的技能（带 paths 字段）
        self._conditional_skills: Dict[str, Skill] = {}
        # 已激活的条件技能
        self._activated_conditionals: set = set()

    def render(
        self,
        skill_id: str,
        arguments: str,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        渲染 Skill 提示词

        Args:
            skill_id: 技能 ID
            arguments: 用户参数
            context: 执行上下文

        Returns:
            渲染后的提示词，不存在则返回 None
        """
        skill = self._registry.get(skill_id)
        if not skill:
            return None

        return skill.render(arguments, context)

    def execute(
        self,
        skill_id: str,
        arguments: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行 Skill

        Args:
            skill_id: 技能 ID
            arguments: 用户参数
            context: 执行上下文

        Returns:
            执行结果 {"prompt": str, "skill": SkillInfo, ...}
        """
        skill = self._registry.get(skill_id)
        if not skill:
            return {
                "success": False,
                "error": f"Skill not found: {skill_id}"
            }

        # 渲染提示词
        prompt = skill.render(arguments, context)

        # 添加到上下文
        result = {
            "success": True,
            "skill_id": skill_id,
            "skill": skill.info,
            "prompt": prompt,
            "allowed_tools": skill.info.allowed_tools,
            "base_dir": skill.base_dir,
        }

        return result

    def check_conditional_activation(
        self,
        file_paths: List[str],
        cwd: Optional[Path] = None
    ) -> List[str]:
        """
        检查并激活条件 Skills

        当操作的文件匹配 skill.paths 时激活技能

        Args:
            file_paths: 文件路径列表
            cwd: 当前工作目录

        Returns:
            激活的技能 ID 列表
        """
        if cwd is None:
            cwd = Path.cwd()

        activated = []

        # 遍历所有技能，找到条件激活的
        for skill_id, skill in self._registry._skills.items():
            # 跳过已激活的
            if skill_id in self._activated_conditionals:
                continue

            # 跳过没有 paths 的
            if not skill.info.paths:
                continue

            # 检查路径匹配
            if self._matches_paths(file_paths, skill.info.paths, cwd):
                self._activated_conditionals.add(skill_id)
                activated.append(skill_id)

        return activated

    def _matches_paths(
        self,
        file_paths: List[str],
        patterns: List[str],
        cwd: Path
    ) -> bool:
        """检查文件路径是否匹配模式"""
        # 简化实现：使用 fnmatch 进行匹配
        # 生产环境可使用 ignore 库支持 gitignore 风格
        for file_path in file_paths:
            # 转换为相对路径
            try:
                rel_path = str(Path(file_path).relative_to(cwd))
            except ValueError:
                rel_path = file_path

            # 尝试匹配每个模式
            for pattern in patterns:
                # 处理 ** 通配符
                if '**' in pattern:
                    # 简化：转换为 fnmatch 模式
                    fn_pattern = pattern.replace('**', '*')
                else:
                    fn_pattern = pattern

                if fnmatch.fnmatch(rel_path, fn_pattern):
                    return True

                # 也尝试匹配文件名
                filename = Path(file_path).name
                if fnmatch.fnmatch(filename, fn_pattern):
                    return True

        return False

    def get_conditional_skills(self) -> List[Skill]:
        """获取所有条件激活的 Skills"""
        return [
            s for s in self._registry._skills.values()
            if s.info.paths and s.info.id not in self._activated_conditionals
        ]

    def get_activated_conditionals(self) -> List[str]:
        """获取已激活的条件 Skills ID"""
        return list(self._activated_conditionals)

    def reset_conditionals(self) -> None:
        """重置条件技能激活状态"""
        self._activated_conditionals.clear()


# 会话级别的执行器管理
_executor: Optional[SkillExecutor] = None


def get_executor(registry: Optional[SkillRegistry] = None) -> SkillExecutor:
    """获取 Skill 执行器"""
    global _executor
    if _executor is None:
        if registry is None:
            from .registry import get_global_registry
            registry = get_global_registry()
        _executor = SkillExecutor(registry)
    return _executor


def reset_executor() -> None:
    """重置执行器"""
    global _executor
    _executor = None