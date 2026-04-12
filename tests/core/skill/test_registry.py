"""测试 Skill 注册表"""

import pytest
from pathlib import Path
from core.skill import (
    SkillRegistry,
    Skill,
    SkillInfo,
    SkillSource,
    register_bundled_skill,
    load_builtin_bundled_skills,
    load_bundled_skills,
    clear_bundled_skills,
    reset_global_registry,
)


class TestSkillRegistry:
    """测试 SkillRegistry"""

    def setup_method(self):
        """每个测试前重置注册表"""
        reset_global_registry()
        clear_bundled_skills()

    def test_register_skill(self):
        registry = SkillRegistry()
        skill = Skill(
            info=SkillInfo(id="test", name="Test"),
            prompt_template="test"
        )

        registry.register(skill)
        assert registry.exists("test")

    def test_unregister_skill(self):
        registry = SkillRegistry()
        skill = Skill(
            info=SkillInfo(id="test", name="Test"),
            prompt_template="test"
        )

        registry.register(skill)
        assert registry.unregister("test") is True
        assert not registry.exists("test")

    def test_get_skill(self):
        registry = SkillRegistry()
        skill = Skill(
            info=SkillInfo(id="test", name="Test"),
            prompt_template="test"
        )

        registry.register(skill)
        retrieved = registry.get("test")
        assert retrieved is not None
        assert retrieved.info.id == "test"

    def test_list_skills(self):
        registry = SkillRegistry()
        registry.register(Skill(
            info=SkillInfo(id="a", name="A"),
            prompt_template=""
        ))
        registry.register(Skill(
            info=SkillInfo(id="b", name="B"),
            prompt_template=""
        ))

        skills = registry.list()
        assert len(skills) == 2

    def test_list_enabled_only(self):
        registry = SkillRegistry()
        registry.register(Skill(
            info=SkillInfo(id="a", name="A", user_invocable=True),
            prompt_template=""
        ))
        registry.register(Skill(
            info=SkillInfo(id="b", name="B", user_invocable=False),
            prompt_template=""
        ))

        enabled = registry.list(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].id == "a"

    def test_get_statistics(self):
        registry = SkillRegistry()
        registry.register(Skill(
            info=SkillInfo(id="a", name="A", source=SkillSource.BUNDLED),
            prompt_template=""
        ))
        registry.register(Skill(
            info=SkillInfo(id="b", name="B", source=SkillSource.PROJECT),
            prompt_template=""
        ))

        stats = registry.get_statistics()
        assert stats['total'] == 2
        assert stats['sources']['bundled'] == 1
        assert stats['sources']['project'] == 1

    def test_get_by_source(self):
        registry = SkillRegistry()
        registry.register(Skill(
            info=SkillInfo(id="a", name="A", source=SkillSource.BUNDLED),
            prompt_template=""
        ))
        registry.register(Skill(
            info=SkillInfo(id="b", name="B", source=SkillSource.PROJECT),
            prompt_template=""
        ))

        bundled = registry.get_by_source(SkillSource.BUNDLED)
        assert len(bundled) == 1
        assert bundled[0].id == "a"

    def test_clear_keeps_bundled(self):
        registry = SkillRegistry()
        registry.register(Skill(
            info=SkillInfo(id="bundled", name="Bundled", source=SkillSource.BUNDLED),
            prompt_template=""
        ))
        registry.register(Skill(
            info=SkillInfo(id="project", name="Project", source=SkillSource.PROJECT),
            prompt_template=""
        ))

        registry.clear()
        assert registry.exists("bundled")
        assert not registry.exists("project")


class TestRegisterBundledSkill:
    """测试内置 Skill 注册"""

    def setup_method(self):
        clear_bundled_skills()

    def test_register_bundled(self):
        register_bundled_skill(
            skill_id="test",
            name="Test Skill",
            description="Test description",
            prompt_template="Test prompt ${ARGUMENTS}",
            allowed_tools=["bash", "read"]
        )

        # 注册到临时注册表
        registry = SkillRegistry()
        count = load_bundled_skills(registry)

        assert count == 1
        skill = registry.get("test")
        assert skill is not None
        assert skill.info.name == "Test Skill"

    def test_multiple_bundled_registration(self):
        register_bundled_skill("a", "A", "Desc A", "Prompt A")
        register_bundled_skill("b", "B", "Desc B", "Prompt B")

        registry = SkillRegistry()
        count = load_bundled_skills(registry)

        assert count == 2


class TestBuiltinBundledSkills:
    """测试文件驱动的默认 bundled skills"""

    def setup_method(self):
        clear_bundled_skills()

    @pytest.mark.asyncio
    async def test_load_builtin_bundled_skills(self):
        registry = SkillRegistry()

        count = await load_builtin_bundled_skills(registry)

        assert count >= 3
        assert registry.exists("verify")
        assert registry.exists("review")
        assert registry.exists("simplify")

        verify = registry.get("verify")
        assert verify is not None
        assert verify.info.source == SkillSource.BUNDLED
        assert "验证代码变更" in verify.info.description
        assert verify.base_dir is not None
        assert verify.prompt_template == ""
        assert verify.file_path is not None


class TestGlobalRegistry:
    """测试全局注册表"""

    def setup_method(self):
        reset_global_registry()
        clear_bundled_skills()

    def test_get_global_registry(self):
        from core.skill import get_global_registry
        reg1 = get_global_registry()
        reg2 = get_global_registry()
        assert reg1 is reg2

    def test_reset_global_registry(self):
        from core.skill import get_global_registry
        reg1 = get_global_registry()
        reset_global_registry()
        reg2 = get_global_registry()
        assert reg1 is not reg2
