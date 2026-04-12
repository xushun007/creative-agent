"""测试 Skill 解析器"""

import pytest
from core.skill.parser import (
    parse_frontmatter,
    parse_bool,
    parse_hooks,
    parse_list,
    parse_argument_names,
    parse_skill_content,
)
from core.skill.models import SkillSource


class TestParseFrontmatter:
    """测试 Frontmatter 解析"""

    def test_parse_with_frontmatter(self):
        content = """---
description: Test skill
argument-hint: [arg]
---
Body content"""
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter['description'] == 'Test skill'
        assert frontmatter['argument-hint'] == '[arg]'
        assert body == 'Body content'

    def test_parse_without_frontmatter(self):
        content = "Just body content"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == "Just body content"

    def test_parse_empty_frontmatter(self):
        content = "---\n---\nBody"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == "Body"

    def test_parse_frontmatter_with_quotes(self):
        content = """---
description: "Quoted description"
argument-hint: '[hint]'
---
Body"""
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter['description'] == 'Quoted description'
        assert frontmatter['argument-hint'] == '[hint]'

    def test_parse_multiline_value(self):
        content = """---
description: Multi
  line
---
Body"""
        frontmatter, body = parse_frontmatter(content)
        # 当前实现只取冒号后的第一部分
        assert 'description' in frontmatter


class TestParseBool:
    """测试布尔值解析"""

    def test_parse_true_values(self):
        assert parse_bool('true') is True
        assert parse_bool('True') is True
        assert parse_bool('yes') is True
        assert parse_bool('YES') is True
        assert parse_bool('1') is True
        assert parse_bool('on') is True

    def test_parse_false_values(self):
        assert parse_bool('false') is False
        assert parse_bool('False') is False
        assert parse_bool('no') is False
        assert parse_bool('no') is False
        assert parse_bool('0') is False
        assert parse_bool('off') is False

    def test_parse_default(self):
        assert parse_bool(None) is True
        assert parse_bool(None, default=False) is False


class TestParseList:
    """测试列表解析"""

    def test_parse_comma_separated(self):
        result = parse_list('a, b, c')
        assert result == ['a', 'b', 'c']

    def test_parse_space_separated(self):
        result = parse_list('a b c')
        assert result == ['a', 'b', 'c']

    def test_parse_empty(self):
        assert parse_list('') == []
        assert parse_list(None) == []

    def test_parse_with_extra_spaces(self):
        result = parse_list('  a  ,  b  ')
        assert result == ['a', 'b']


class TestParseHooks:
    """测试 hooks 解析"""

    def test_parse_hooks_json(self):
        hooks = parse_hooks('{"on_skill_start":["echo start"],"on_skill_complete":["echo done"]}')
        assert hooks is not None
        assert hooks["on_skill_start"] == ["echo start"]
        assert hooks["on_skill_complete"] == ["echo done"]

    def test_parse_hooks_invalid(self):
        assert parse_hooks("not-json") is None


class TestParseSkillContent:
    """测试 Skill 内容解析"""

    def test_parse_full_skill(self):
        content = """---
name: Test Skill
description: A test skill
argument-hint: [arg]
allowed-tools: bash, read
user-invocable: true
---
Skill prompt body"""

        skill = parse_skill_content(
            content,
            'test-skill',
            SkillSource.PROJECT,
            '/test/dir'
        )

        assert skill.info.id == 'test-skill'
        assert skill.info.name == 'Test Skill'
        assert skill.info.description == 'A test skill'
        assert skill.info.argument_hint == '[arg]'
        assert 'bash' in skill.info.allowed_tools
        assert 'read' in skill.info.allowed_tools
        assert skill.info.user_invocable is True
        assert skill.prompt_template == 'Skill prompt body'
        assert skill.base_dir == '/test/dir'

    def test_parse_extracts_description_from_header(self):
        content = """# My Skill Header

Body content"""

        skill = parse_skill_content(
            content,
            'my-skill',
            SkillSource.BUNDLED
        )

        assert skill.info.description == 'My Skill Header'

    def test_parse_hooks_from_frontmatter(self):
        content = """---
description: Hook skill
hooks: '{"on_skill_start":["echo start"]}'
---
Body"""

        skill = parse_skill_content(
            content,
            'hook-skill',
            SkillSource.PROJECT
        )

        assert skill.hooks is not None
        assert skill.hooks["on_skill_start"] == ["echo start"]


class TestExtractArgumentNames:
    """测试参数名提取"""

    def test_extract_standard_variables(self):
        prompt = "Hello ${NAME}, you have ${COUNT} items"
        from core.skill.parser import extract_argument_names
        names = extract_argument_names(prompt)
        assert 'NAME' in names
        assert 'COUNT' in names

    def test_extract_builtins_excluded(self):
        prompt = "${ARGUMENTS} ${CTV_SKILL_DIR} ${CLAUDE_SKILL_DIR} ${custom}"
        from core.skill.parser import extract_argument_names
        names = extract_argument_names(prompt)
        assert 'custom' in names
        assert 'ARGUMENTS' not in names
        assert 'CTV_SKILL_DIR' not in names
        assert 'CLAUDE_SKILL_DIR' not in names
