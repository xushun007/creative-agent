"""Skill 加载器 - 从文件系统加载 Skill"""

import os
from pathlib import Path
from typing import List, Optional

from .models import Skill, SkillSource
from .parser import parse_skill_content


async def load_skill_from_file(
    file_path: Path,
    source: SkillSource,
    base_dir: Optional[str] = None
) -> Optional[Skill]:
    """
    从文件加载 Skill

    Args:
        file_path: SKILL.md 文件路径
        source: 来源
        base_dir: 技能目录

    Returns:
        Skill 对象，解析失败返回 None
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except (IOError, UnicodeDecodeError):
        return None

    # 获取目录名作为 skill_id
    skill_id = file_path.parent.name

    return parse_skill_content(
        content=content,
        skill_id=skill_id,
        source=source,
        base_dir=base_dir or str(file_path.parent)
    )


async def load_skills_from_dir(
    dir_path: Path,
    source: SkillSource
) -> List[Skill]:
    """
    从目录加载 Skills

    目录格式: skill-name/SKILL.md

    Args:
        dir_path: 技能目录
        source: 来源

    Returns:
        Skill 列表
    """
    skills: List[Skill] = []

    if not dir_path.exists() or not dir_path.is_dir():
        return skills

    try:
        entries = list(dir_path.iterdir())
    except PermissionError:
        return skills

    for entry in entries:
        if not entry.is_dir():
            continue

        skill_file = entry / 'SKILL.md'
        if not skill_file.exists():
            continue

        skill = await load_skill_from_file(
            skill_file,
            source,
            base_dir=str(entry)
        )
        if skill:
            skills.append(skill)

    return skills


def get_skills_base_dirs(cwd: Path) -> dict[str, Path]:
    """
    获取 Skills 基础目录

    Returns:
        {
            "project": Path,
            "user": Path,
            "project_compat": Path,
            "user_compat": Path,
        }
    """
    home = Path.home()
    config_home = os.environ.get(
        'XDG_CONFIG_HOME',
        home / '.config'
    )

    # 主目录: CTV Agent 自定义目录
    user_dir = Path(config_home) / 'ctv-agent' / 'skills'
    project_dir = cwd / '.ctv-agent' / 'skills'

    # 兼容目录: Claude Code 目录
    user_compat_dir = home / '.claude' / 'skills'
    project_compat_dir = cwd / '.claude' / 'skills'

    return {
        "project": project_dir,
        "user": user_dir,
        "project_compat": project_compat_dir,
        "user_compat": user_compat_dir,
    }


def get_bundled_skills_dir() -> Path:
    """获取内置 Skills 目录"""
    return Path(__file__).resolve().parents[2] / 'skills' / 'bundled'


async def load_all_skills(cwd: Path) -> List[Skill]:
    """
    加载所有层级的 Skills

    Args:
        cwd: 当前工作目录

    Returns:
        去重后的 Skill 列表
    """
    base_dirs = get_skills_base_dirs(cwd)
    all_skills: List[Skill] = []

    load_order = [
        ("project", SkillSource.PROJECT),
        ("user", SkillSource.USER),
        ("project_compat", SkillSource.PROJECT),
        ("user_compat", SkillSource.USER),
    ]

    for key, source in load_order:
        dir_path = base_dirs[key]
        if not dir_path.exists():
            continue
        skills = await load_skills_from_dir(dir_path, source)
        all_skills.extend(skills)

    # 去重（按 ID，保留更高优先级目录中的第一个）
    seen = set()
    unique_skills: List[Skill] = []
    for skill in all_skills:
        if skill.info.id not in seen:
            seen.add(skill.info.id)
            unique_skills.append(skill)

    return unique_skills
