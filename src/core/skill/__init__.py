"""Skill 模块 - 提供 Skill 能力

使用示例:
    from core.skill import SkillRegistry, load_builtin_bundled_skills

    # 获取注册表
    registry = get_global_registry()

    # 加载内置 Skill
    await load_builtin_bundled_skills(registry)

    # 加载文件系统中的 Skills
    await registry.load_from_filesystem()

    # 列出所有 Skills
    for skill in registry.list():
        print(f"/{skill.id}: {skill.description}")
"""

from .executor import SkillExecutor, get_executor, reset_executor
from .loader import (
    get_bundled_skills_dir,
    get_skills_base_dirs,
    load_all_skills,
    load_skill_from_file,
    load_skills_from_dir,
)
from .models import Skill, SkillInfo, SkillSource
from .parser import (
    extract_argument_names,
    parse_argument_names,
    parse_frontmatter,
    parse_skill_content,
    parse_bool,
    parse_list,
)
from .registry import (
    SkillRegistry,
    clear_bundled_skills,
    get_global_registry,
    load_builtin_bundled_skills,
    load_bundled_skills,
    register_bundled_skill,
    reset_global_registry,
)

__all__ = [
    # 模型
    "Skill",
    "SkillInfo",
    "SkillSource",
    # 注册表
    "SkillRegistry",
    "get_global_registry",
    "reset_global_registry",
    "register_bundled_skill",
    "load_bundled_skills",
    "load_builtin_bundled_skills",
    "clear_bundled_skills",
    # 加载器
    "load_skill_from_file",
    "load_skills_from_dir",
    "load_all_skills",
    "get_skills_base_dirs",
    "get_bundled_skills_dir",
    # 解析器
    "parse_frontmatter",
    "parse_skill_content",
    "parse_bool",
    "parse_list",
    "parse_argument_names",
    "extract_argument_names",
    # 执行器
    "SkillExecutor",
    "get_executor",
    "reset_executor",
]
