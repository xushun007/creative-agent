"""内置 Skills 注册入口"""

from .review import register_review_skill
from .simplify import register_simplify_skill
from .verify import register_verify_skill


def register_all_bundled_skills():
    """注册所有内置 Skills"""
    register_verify_skill()
    register_review_skill()
    register_simplify_skill()


__all__ = [
    "register_all_bundled_skills",
    "register_verify_skill",
    "register_review_skill",
    "register_simplify_skill",
]