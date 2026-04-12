"""Skill CLI 命令"""

import re
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich import print as rprint

from core.skill import (
    SkillRegistry,
    SkillExecutor,
    get_global_registry,
    load_builtin_bundled_skills,
    load_bundled_skills,
    reset_global_registry,
)
from core.config import Config

console = Console()


async def init_skill_registry(config: Config) -> SkillRegistry:
    """初始化 Skill 注册表"""
    cwd = config.cwd
    registry = get_global_registry(cwd)

    # 加载内置 Skills
    await load_builtin_bundled_skills(registry)

    # 加载动态注册的内置 Skills（主要用于测试/扩展）
    load_bundled_skills(registry)

    # 加载文件系统中的 Skills
    await registry.load_from_filesystem()

    return registry


def parse_skill_command(input_str: str) -> Optional[tuple[str, str]]:
    """
    解析技能命令

    支持格式:
    - /skill-name
    - /skill-name args
    - /skill-name "args with spaces"

    Returns:
        (skill_id, arguments) 或 None
    """
    input_str = input_str.strip()

    # 检查是否以 / 开头
    if not input_str.startswith('/'):
        return None

    # 提取技能名称和参数
    # 格式: /skill-id [args]
    rest = input_str[1:].strip()

    if not rest:
        return None

    # 简单的空格分隔
    parts = rest.split(None, 1)
    skill_id = parts[0]
    arguments = parts[1] if len(parts) > 1 else ""

    return skill_id, arguments


def execute_skill(
    registry: SkillRegistry,
    skill_id: str,
    arguments: str,
    context: dict
) -> Optional[dict]:
    """
    执行 Skill

    Returns:
        执行结果字典，或 None（如果 Skill 不存在）
    """
    executor = SkillExecutor(registry)
    result = executor.execute(skill_id, arguments, context)

    if result["success"]:
        return result

    return None


def list_skills(registry: SkillRegistry):
    """列出所有可用 Skills"""
    skills = registry.list(enabled_only=True)

    if not skills:
        console.print("[yellow]没有可用的 Skills[/yellow]")
        return

    table = Table(title="Available Skills", show_header=True, header_style="bold magenta")
    table.add_column("Command", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Argument Hint", style="dim")

    for skill in skills:
        table.add_row(
            f"/{skill.id}",
            skill.description or "",
            skill.argument_hint or ""
        )

    console.print(table)


def show_skill_help(registry: SkillRegistry, skill_id: str):
    """显示单个 Skill 的帮助信息"""
    skill = registry.get(skill_id)
    if not skill:
        console.print(f"[red]Skill not found: {skill_id}[/red]")
        return

    console.print(f"\n[bold cyan]/{skill.info.id}[/bold cyan]")
    console.print(f"[bold]Description:[/bold] {skill.info.description or '(none)'}")

    if skill.info.argument_hint:
        console.print(f"[bold]Argument Hint:[/bold] {skill.info.argument_hint}")

    if skill.info.when_to_use:
        console.print(f"[bold]When to Use:[/bold] {skill.info.when_to_use}")

    if skill.info.allowed_tools:
        console.print(f"[bold]Allowed Tools:[/bold] {', '.join(skill.info.allowed_tools)}")

    console.print()


def is_skill_command(input_str: str) -> bool:
    """检查是否为技能命令"""
    return input_str.strip().startswith('/')


def handle_skill_command(
    registry: SkillRegistry,
    input_str: str,
    context: dict
) -> Optional[dict]:
    """
    处理技能命令

    Returns:
        渲染后的提示词（如果成功），None（如果失败或不是技能命令）
    """
    parsed = parse_skill_command(input_str)
    if not parsed:
        return None

    skill_id, arguments = parsed

    # 特殊命令
    if skill_id in ('help', 'h'):
        if arguments:
            show_skill_help(registry, arguments)
        else:
            list_skills(registry)
        return None

    # 执行 Skill
    result = execute_skill(registry, skill_id, arguments, context)
    if result:
        console.print(f"[green]Executing /{skill_id}...[/green]\n")
        return result

    # Skill 不存在
    console.print(f"[red]Skill not found: {skill_id}[/red]")
    return None
