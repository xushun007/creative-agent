"""Skill 解析器 - 解析 Frontmatter 和 Skill 内容"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .models import Skill, SkillInfo, SkillSource


def parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """
    解析 Frontmatter 元数据

    返回: (frontmatter_dict, body)
    """
    lines = content.split('\n')

    # 检查是否以 --- 开头
    if not lines or lines[0].strip() != '---':
        return {}, content

    frontmatter: Dict[str, str] = {}
    body_lines: List[str] = []
    in_frontmatter = False
    frontmatter_closed = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if i == 0 and stripped == '---':
            in_frontmatter = True
            continue

        if stripped == '---':
            frontmatter_closed = True
            in_frontmatter = False
            continue

        if in_frontmatter:
            if stripped and not stripped.startswith('#'):
                # 解析 key: value 格式
                if ':' in stripped:
                    key, value = stripped.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    # 去除引号
                    if len(value) >= 2:
                        if (value[0] == '"' and value[-1] == '"') or \
                           (value[0] == "'" and value[-1] == "'"):
                            value = value[1:-1]
                    frontmatter[key] = value
        else:
            body_lines.append(line)

    body = '\n'.join(body_lines).strip()
    return (frontmatter, body) if frontmatter_closed else ({}, content)


def parse_bool(value: Optional[str], default: bool = True) -> bool:
    """解析布尔值"""
    if value is None:
        return default
    return value.lower() in ('true', 'yes', '1', 'on')


def parse_list(value: Optional[str]) -> List[str]:
    """解析列表值（逗号或空格分隔）"""
    if not value:
        return []
    # 支持逗号分隔或空格分隔
    items = re.split(r'[,\s]+', value.strip())
    return [item.strip() for item in items if item.strip()]


def parse_argument_names(value: Optional[str]) -> List[str]:
    """解析参数名称列表"""
    if not value:
        return []
    # 格式: <arg1> <arg2> 或 [arg1, arg2]
    value = value.strip()
    if value.startswith('[') and value.endswith(']'):
        value = value[1:-1]
    return parse_list(value)


def parse_hooks(value: Optional[str]) -> Optional[Dict[str, List[str]]]:
    """解析 hooks 配置，当前支持 JSON 字符串"""
    if not value:
        return None

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    hooks: Dict[str, List[str]] = {}
    for key, commands in parsed.items():
        if isinstance(commands, str):
            hooks[str(key)] = [commands]
        elif isinstance(commands, list):
            hook_commands = [str(cmd) for cmd in commands if str(cmd).strip()]
            if hook_commands:
                hooks[str(key)] = hook_commands

    return hooks or None


def parse_skill_content(
    content: str,
    skill_id: str,
    source: SkillSource,
    base_dir: Optional[str] = None,
    include_body: bool = True,
) -> Skill:
    """
    解析 Skill 文件内容

    Args:
        content: 文件内容
        skill_id: Skill ID
        source: 来源
        base_dir: 技能目录

    Returns:
        Skill 对象
    """
    frontmatter, body = parse_frontmatter(content)

    # 解析各字段
    info = SkillInfo(
        id=skill_id,
        name=frontmatter.get('name', skill_id),
        description=frontmatter.get('description', ''),
        argument_hint=frontmatter.get('argument-hint'),
        when_to_use=frontmatter.get('when-to-use'),
        allowed_tools=parse_list(frontmatter.get('allowed-tools')),
        user_invocable=parse_bool(
            frontmatter.get('user-invocable'),
            default=True
        ),
        source=source,
        paths=parse_list(frontmatter.get('paths')) or None,
        version=frontmatter.get('version'),
        model=frontmatter.get('model'),
        disable_model_invocation=parse_bool(
            frontmatter.get('disable-model-invocation'),
            default=False
        ),
    )

    # 从第一行提取描述（如果没有 description）
    if not info.description and body:
        first_line = body.split('\n')[0].strip()
        if first_line.startswith('# '):
            info.description = first_line[2:].strip()

    return Skill(
        info=info,
        prompt_template=body if include_body else "",
        base_dir=base_dir,
        hooks=parse_hooks(frontmatter.get('hooks')),
    )


def extract_argument_names(prompt: str) -> List[str]:
    """从提示词中提取参数名称"""
    # 匹配 ${name} 格式的变量
    pattern = r'\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
    matches = re.findall(pattern, prompt)

    # 排除内置变量
    builtins = {'ARGUMENTS', 'CTV_SKILL_DIR', 'CLAUDE_SKILL_DIR', 'CLAUDE_SESSION_ID'}
    return [m for m in matches if m not in builtins]
