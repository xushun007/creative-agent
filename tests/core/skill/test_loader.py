"""测试 Skill 加载器"""

import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from core.skill import (
    get_bundled_skills_dir,
    load_skill_from_file,
    load_skills_from_dir,
    load_all_skills,
    get_skills_base_dirs,
    SkillSource,
)


class TestLoadSkillFromFile:
    """测试从文件加载 Skill"""

    @pytest.mark.asyncio
    async def test_load_valid_skill_file(self, tmp_path):
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
description: Test skill
argument-hint: [arg]
---
Skill body content""")

        skill = await load_skill_from_file(skill_file, SkillSource.PROJECT)

        assert skill is not None
        assert skill.info.id == "test-skill"
        assert skill.info.description == "Test skill"
        assert skill.prompt_template == "Skill body content"

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self, tmp_path):
        skill_file = tmp_path / "nonexistent" / "SKILL.md"

        skill = await load_skill_from_file(skill_file, SkillSource.PROJECT)

        assert skill is None

    @pytest.mark.asyncio
    async def test_load_invalid_content(self, tmp_path):
        skill_dir = tmp_path / "bad-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("\x00\x01\x02")  # Invalid UTF-8

        skill = await load_skill_from_file(skill_file, SkillSource.PROJECT)

        # 可能返回 None 或解析错误
        assert skill is None or skill.info.id == "bad-skill"


class TestLoadSkillsFromDir:
    """测试从目录加载 Skills"""

    @pytest.mark.asyncio
    async def test_load_empty_dir(self, tmp_path):
        skills = await load_skills_from_dir(tmp_path, SkillSource.PROJECT)
        assert skills == []

    @pytest.mark.asyncio
    async def test_load_dir_with_skills(self, tmp_path):
        # 创建多个 skill 目录
        skill1_dir = tmp_path / "skill-one"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("---\ndescription: Skill One\n---\nBody 1")

        skill2_dir = tmp_path / "skill-two"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("---\ndescription: Skill Two\n---\nBody 2")

        skills = await load_skills_from_dir(tmp_path, SkillSource.USER, lazy_body=False)

        assert len(skills) == 2
        ids = {s.info.id for s in skills}
        assert "skill-one" in ids
        assert "skill-two" in ids

    @pytest.mark.asyncio
    async def test_load_skips_non_directories(self, tmp_path):
        # 创建文件而非目录
        (tmp_path / "file.md").write_text("content")

        skills = await load_skills_from_dir(tmp_path, SkillSource.PROJECT, lazy_body=False)
        assert skills == []

    @pytest.mark.asyncio
    async def test_load_skips_missing_skill_md(self, tmp_path):
        skill_dir = tmp_path / "incomplete-skill"
        skill_dir.mkdir()
        # 只有 README，没有 SKILL.md
        (skill_dir / "README.md").write_text("readme")

        skills = await load_skills_from_dir(tmp_path, SkillSource.PROJECT, lazy_body=False)
        assert skills == []

    @pytest.mark.asyncio
    async def test_load_dir_lazy_body(self, tmp_path):
        skill_dir = tmp_path / "lazy-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: Lazy Skill\n---\nLazy Body")

        skills = await load_skills_from_dir(tmp_path, SkillSource.PROJECT, lazy_body=True)

        assert len(skills) == 1
        skill = skills[0]
        assert skill.prompt_template == ""
        assert skill.file_path == skill_dir / "SKILL.md"


class TestGetSkillsBaseDirs:
    """测试获取基础目录"""

    def test_get_base_dirs(self, tmp_path, monkeypatch):
        # 临时设置 HOME
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        dirs = get_skills_base_dirs(tmp_path)

        assert "user" in dirs
        assert "project" in dirs
        assert "project_compat" in dirs
        assert "user_compat" in dirs
        assert dirs["project"] == tmp_path / ".ctv-agent" / "skills"
        assert dirs["user"] == tmp_path / ".config" / "ctv-agent" / "skills"
        assert dirs["project_compat"] == tmp_path / ".claude" / "skills"
        assert dirs["user_compat"] == tmp_path / ".claude" / "skills"

    def test_xdg_config_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        dirs = get_skills_base_dirs(tmp_path)

        assert dirs["user"] == tmp_path / "config" / "ctv-agent" / "skills"


class TestBundledSkillsDir:
    """测试内置 Skills 目录"""

    def test_get_bundled_skills_dir(self):
        bundled_dir = get_bundled_skills_dir()

        assert bundled_dir.name == "bundled"
        assert bundled_dir.exists()
        assert (bundled_dir / "verify" / "SKILL.md").exists()
        assert (bundled_dir / "verify" / "examples" / "checklist.md").exists()
        assert (bundled_dir / "review" / "examples" / "findings-format.md").exists()
        assert (bundled_dir / "simplify" / "examples" / "safety-rules.md").exists()


class TestLoadAllSkills:
    """测试加载所有 Skills"""

    @pytest.mark.asyncio
    async def test_load_from_nonexistent_dirs(self, tmp_path):
        skills = await load_all_skills(tmp_path)
        # 即使目录不存在也应返回空列表
        assert skills == []

    @pytest.mark.asyncio
    async def test_load_deduplicates_by_id(self, tmp_path):
        # 创建相同的 skill 在不同位置
        project_dir = tmp_path / ".ctv-agent" / "skills"
        project_dir.mkdir(parents=True)
        skill_dir = project_dir / "duplicate"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: Project\n---\nProject body")

        # 加载两次应该去重
        skills = await load_all_skills(tmp_path)
        ids = [s.info.id for s in skills]
        assert ids.count("duplicate") == 1

    @pytest.mark.asyncio
    async def test_loads_compat_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))

        compat_project_dir = tmp_path / ".claude" / "skills"
        compat_project_dir.mkdir(parents=True)
        compat_skill_dir = compat_project_dir / "compat-project"
        compat_skill_dir.mkdir()
        (compat_skill_dir / "SKILL.md").write_text("---\ndescription: Compat Project\n---\nBody")

        compat_user_dir = tmp_path / ".claude" / "skills"
        compat_user_dir.mkdir(parents=True, exist_ok=True)
        compat_user_skill_dir = compat_user_dir / "compat-user"
        compat_user_skill_dir.mkdir()
        (compat_user_skill_dir / "SKILL.md").write_text("---\ndescription: Compat User\n---\nBody")

        skills = await load_all_skills(tmp_path)
        ids = {s.info.id for s in skills}

        assert "compat-project" in ids
        assert "compat-user" in ids

    @pytest.mark.asyncio
    async def test_primary_dirs_override_compat_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))

        primary_project_dir = tmp_path / ".ctv-agent" / "skills"
        primary_project_dir.mkdir(parents=True)
        primary_skill_dir = primary_project_dir / "shared-skill"
        primary_skill_dir.mkdir()
        (primary_skill_dir / "SKILL.md").write_text(
            "---\ndescription: Primary\n---\nPrimary body"
        )

        compat_project_dir = tmp_path / ".claude" / "skills"
        compat_project_dir.mkdir(parents=True)
        compat_skill_dir = compat_project_dir / "shared-skill"
        compat_skill_dir.mkdir()
        (compat_skill_dir / "SKILL.md").write_text(
            "---\ndescription: Compat\n---\nCompat body"
        )

        skills = await load_all_skills(tmp_path)
        assert len([s for s in skills if s.info.id == "shared-skill"]) == 1

        skill = next(s for s in skills if s.info.id == "shared-skill")
        assert skill.info.description == "Primary"
