from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple, Any


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _normalize_path(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except TypeError:
        # Python < 3.9 fallback (resolve without strict parameter).
        try:
            return path.resolve()
        except FileNotFoundError:
            return path.absolute()


def _resolve_existing_parent(path: Path) -> Path:
    current = path
    while not current.exists():
        parent = current.parent
        if parent == current:
            return current
        current = parent
    return _normalize_path(current)


def _normalize_policy_value(value: Optional[str]) -> str:
    if not value:
        return "workspace_write"
    value = str(value).strip().lower()
    if value in {"none", "full", "full_access", "danger_full_access"}:
        return "full_access"
    if value in {"strict", "read_only", "readonly"}:
        return "read_only"
    if value in {"workspace_write", "workspace-write", "workspace"}:
        return "workspace_write"
    return "workspace_write"


@dataclass(frozen=True)
class PathPolicy:
    mode: str
    read_scope: str
    workspace_root: Path
    allowed_roots: Tuple[Path, ...]
    read_only_subpaths: Tuple[Path, ...]
    deny_roots: Tuple[Path, ...]

    def is_full_access(self) -> bool:
        return self.mode == "full_access"

    def is_read_only(self) -> bool:
        return self.mode == "read_only"


def build_path_policy(config: Optional[Any], cwd: Optional[Path] = None) -> PathPolicy:
    policy_value = _normalize_policy_value(getattr(config, "sandbox_policy", None))
    if policy_value == "full_access":
        mode = "full_access"
    elif policy_value == "read_only":
        mode = "read_only"
    else:
        mode = "workspace_write"

    read_scope = "full" if mode == "full_access" else "workspace_only"

    workspace_root = getattr(config, "cwd", None)
    workspace_root = Path(workspace_root) if workspace_root else (cwd or Path.cwd())
    workspace_root = _normalize_path(workspace_root)

    allowed_roots = (_normalize_path(workspace_root),)
    read_only_subpaths = tuple(
        _normalize_path(root / name)
        for root in allowed_roots
        for name in (".git", ".codex")
    )

    return PathPolicy(
        mode=mode,
        read_scope=read_scope,
        workspace_root=workspace_root,
        allowed_roots=allowed_roots,
        read_only_subpaths=read_only_subpaths,
        deny_roots=tuple(),
    )


def policy_from_context(context: Optional[Any], cwd: Optional[Path] = None) -> PathPolicy:
    config = None
    if context is not None:
        extra = getattr(context, "extra", None) or {}
        config = extra.get("config")
    return build_path_policy(config, cwd=cwd)


def _is_under_any(path: Path, roots: Iterable[Path]) -> bool:
    for root in roots:
        if path == root or _is_relative_to(path, root):
            return True
    return False


def check_path_access(policy: PathPolicy, path: Path, op: str) -> Tuple[bool, Optional[str]]:
    if policy.is_full_access():
        return True, None

    op = op.lower().strip()
    raw_path = Path(path)
    if not raw_path.is_absolute():
        raw_path = policy.workspace_root / raw_path

    normalized_path = _normalize_path(raw_path)
    normalized_parent = _resolve_existing_parent(raw_path.parent)

    if policy.deny_roots and _is_under_any(normalized_path, policy.deny_roots):
        return False, "路径位于禁止访问范围内"

    if op in {"read", "list", "glob", "grep", "search"}:
        if policy.read_scope == "full":
            return True, None
        if _is_under_any(normalized_path, policy.allowed_roots):
            return True, None
        return False, "读取路径不在允许范围内"

    if op in {"write", "edit", "patch", "delete", "create"}:
        if policy.is_read_only():
            return False, "只读模式禁止写入"
        if not _is_under_any(normalized_parent, policy.allowed_roots):
            return False, "写入路径不在允许范围内"
        if not _is_under_any(normalized_path, policy.allowed_roots):
            return False, "写入路径不在允许范围内"
        if _is_under_any(normalized_path, policy.read_only_subpaths):
            return False, "写入路径位于只读子路径内"
        return True, None

    return False, "未知操作类型"
