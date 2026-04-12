"""Skill 注册表 - 管理和提供所有可用 Skill"""

import fnmatch
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .loader import get_bundled_skills_dir, load_all_skills, load_skills_from_dir
from .models import Skill, SkillInfo, SkillSource
from .parser import parse_skill_content


class SkillRegistry:
    """Skill 注册表"""

    def __init__(self, cwd: Optional[Path] = None):
        self._skills: Dict[str, Skill] = {}
        self._cwd = cwd or Path.cwd()
        self._bundled_loaded = False

    def register(self, skill: Skill) -> None:
        """注册 Skill"""
        self._skills[skill.info.id] = skill

    def unregister(self, skill_id: str) -> bool:
        """注销 Skill"""
        if skill_id in self._skills:
            del self._skills[skill_id]
            return True
        return False

    def get(self, skill_id: str) -> Optional[Skill]:
        """获取 Skill"""
        return self._skills.get(skill_id)

    def get_info(self, skill_id: str) -> Optional[SkillInfo]:
        """获取 Skill 信息"""
        skill = self.get(skill_id)
        return skill.info if skill else None

    def list(self, enabled_only: bool = False) -> List[SkillInfo]:
        """列出所有 Skill"""
        skills = list(self._skills.values())
        if enabled_only:
            skills = [s for s in skills if s.info.user_invocable]
        return [s.info for s in skills]

    def exists(self, skill_id: str) -> bool:
        """检查 Skill 是否存在"""
        return skill_id in self._skills

    async def load_from_filesystem(self) -> None:
        """从文件系统加载 Skills"""
        # 加载项目级和用户级 Skills
        skills = await load_all_skills(self._cwd)
        for skill in skills:
            self.register(skill)

    async def load_from_dir(self, dir_path: Path, source: SkillSource) -> int:
        """
        从指定目录加载 Skills

        Returns:
            加载的技能数量
        """
        skills = await load_skills_from_dir(dir_path, source)
        count = 0
        for skill in skills:
            if skill.info.id not in self._skills:
                self.register(skill)
                count += 1
        return count

    def get_by_pattern(self, pattern: str) -> List[SkillInfo]:
        """根据模式匹配 Skills"""
        matched = []
        for skill in self._skills.values():
            if fnmatch.fnmatch(skill.info.id, pattern):
                matched.append(skill.info)
        return matched

    def get_by_source(self, source: SkillSource) -> List[SkillInfo]:
        """获取指定来源的 Skills"""
        return [
            s.info for s in self._skills.values()
            if s.info.source == source
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._skills)
        sources: Dict[str, int] = {}
        for skill in self._skills.values():
            source = skill.info.source.value
            sources[source] = sources.get(source, 0) + 1

        return {
            "total": total,
            "sources": sources,
            "ids": list(self._skills.keys())
        }

    def clear(self) -> None:
        """清空注册表（保留 bundled）"""
        to_remove = [
            sid for sid, skill in self._skills.items()
            if skill.info.source != SkillSource.BUNDLED
        ]
        for sid in to_remove:
            del self._skills[sid]


# 全局注册表
_global_registry: Optional[SkillRegistry] = None


def get_global_registry(cwd: Optional[Path] = None) -> SkillRegistry:
    """获取全局注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry(cwd)
    return _global_registry


def reset_global_registry() -> None:
    """重置全局注册表"""
    global _global_registry
    _global_registry = None


# 内置 Skill 注册函数
_bundled_skills: List[Skill] = []


def register_bundled_skill(
    skill_id: str,
    name: str,
    description: str,
    prompt_template: str,
    argument_hint: Optional[str] = None,
    allowed_tools: Optional[List[str]] = None,
    user_invocable: bool = True,
    base_dir: Optional[str] = None,
) -> None:
    """
    注册内置 Skill

    Args:
        skill_id: 技能 ID
        name: 显示名称
        description: 描述
        prompt_template: 提示词模板
        argument_hint: 参数提示
        allowed_tools: 允许的工具
        user_invocable: 是否可用户调用
        base_dir: 技能目录
    """
    info = SkillInfo(
        id=skill_id,
        name=name,
        description=description,
        argument_hint=argument_hint,
        allowed_tools=allowed_tools or [],
        user_invocable=user_invocable,
        source=SkillSource.BUNDLED,
    )

    skill = Skill(
        info=info,
        prompt_template=prompt_template,
        base_dir=base_dir,
    )

    _bundled_skills.append(skill)


def load_bundled_skills(registry: SkillRegistry) -> int:
    """加载所有内置 Skills 到注册表"""
    for skill in _bundled_skills:
        registry.register(skill)
    return len(_bundled_skills)


async def load_builtin_bundled_skills(registry: SkillRegistry) -> int:
    """
    从内置目录加载 bundled Skills

    目录格式:
        src/skills/bundled/<skill-id>/SKILL.md
    """
    skills = await load_skills_from_dir(
        get_bundled_skills_dir(),
        SkillSource.BUNDLED,
    )

    count = 0
    for skill in skills:
        if skill.info.id not in registry._skills:
            registry.register(skill)
            count += 1
    return count


def clear_bundled_skills() -> None:
    """清空内置 Skills 注册表（用于测试）"""
    _bundled_skills.clear()
