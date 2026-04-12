"""内置 Skill: /verify - 验证代码变更"""

from core.skill import register_bundled_skill


VERIFY_PROMPT = """你正在执行代码变更验证任务。

## 任务目标

验证代码变更是否符合预期，按预期工作。

## 验证步骤

1. 理解代码变更的目的和实现
2. 运行相关测试用例
3. 手动验证功能（如果需要）
4. 记录验证结果

## 用户请求

${ARGUMENTS}

请开始验证，并在完成后报告结果。"""


def register_verify_skill():
    """注册 /verify 技能"""
    register_bundled_skill(
        skill_id="verify",
        name="Verify Code Change",
        description="验证代码变更是否符合预期",
        prompt_template=VERIFY_PROMPT,
        argument_hint="[file] [options]",
        allowed_tools=["bash", "read", "write", "glob", "grep", "edit"],
        user_invocable=True,
    )