"""记忆管理器"""

import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Any
from datetime import datetime

from .models import MemoryMessage, SessionMeta, CompactedMarker
from .rollout_recorder import RolloutRecorder
from .project_doc import ProjectDocLoader

try:
    from utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from core.compaction.utils import estimate_tokens, extract_message_text
except ImportError:
    # 简单回退实现
    def estimate_tokens(text: str) -> int:
        return max(0, len(text or "") // 4)
    
    def extract_message_text(message: dict) -> str:
        return str(message.get("content", ""))


class MemoryManager:
    """记忆管理器（纯存储层）
    
    核心职责：
    - 管理运行时对话历史（内存）
    - 持久化会话到 JSONL 文件
    - 支持会话恢复
    - 加载项目文档
    - 提供消息访问接口
    
    设计原则：
    - 与 CompactionManager 解耦，不依赖压缩逻辑
    - 只负责存储和读取，不做策略决策
    - Token 估算使用 compaction.utils 统一实现
    """
    
    def __init__(
        self,
        session_dir: Path,
        session_id: str,  # 必须由 Session 传入
        cwd: Path,
        model: str,
        config: Any = None,  # Config 对象，用于获取完整配置
        tool_registry: Any = None,  # 工具注册器，用于生成工具列表
        user_instructions: Optional[str] = None,
        auto_load_project_docs: bool = True
    ):
        """创建新的记忆管理器
        
        Args:
            session_dir: 会话存储目录
            session_id: 会话 ID（必须由 Session 传入，不自动生成）
            cwd: 当前工作目录
            model: 模型名称
            config: Config 对象（用于获取完整的系统提示配置）
            tool_registry: 工具注册器（用于生成工具列表）
            user_instructions: 用户指令（可选）
            auto_load_project_docs: 是否自动加载项目文档
        """
        self.session_id = session_id
        self.cwd = Path(cwd)
        self.model = model
        self.config = config
        self.tool_registry = tool_registry
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # 运行时消息历史
        self.messages: List[MemoryMessage] = []
        
        # 项目文档加载器
        self.doc_loader = ProjectDocLoader(self.cwd)
        
        # 创建 Rollout 记录器
        rollout_filename = f"rollout-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{self.session_id}.jsonl"
        self.rollout_path = self.session_dir / rollout_filename
        self.recorder = RolloutRecorder(self.rollout_path, self.session_id)
        
        # 初始化会话（包括完整的系统消息设置）
        self._initialize_session(user_instructions, auto_load_project_docs)
    
    def _initialize_session(
        self, 
        user_instructions: Optional[str],
        auto_load_project_docs: bool
    ):
        """初始化新会话（包含完整的系统消息设置）"""
        logger.info(f"初始化新会话: {self.session_id}")
        
        # 1. 构建完整的系统提示词
        system_prompt = self._build_system_prompt(user_instructions, auto_load_project_docs)
        
        # 2. 写入会话元数据
        project_docs = self.doc_loader.load_as_system_message() if auto_load_project_docs else None
        meta = SessionMeta(
            session_id=self.session_id,
            created_at=datetime.now(),
            cwd=str(self.cwd),
            model=self.model,
            user_instructions=user_instructions,
            project_docs=project_docs
        )
        self.recorder.write_session_meta(meta)
        
        # 3. 添加系统消息
        if system_prompt:
            self.add_system_message(system_prompt)
            logger.info(f"添加系统消息: {len(system_prompt)} 字符")
    
    def _build_system_prompt(
        self,
        user_instructions: Optional[str],
        auto_load_project_docs: bool
    ) -> str:
        """构建完整的系统提示词（迁移自 ModelClient._setup_system_messages）
        
        包含：
        1. 基础系统提示词（从 prompt 文件读取）
        2. 用户自定义指令
        3. 项目文档（AGENTS.md）
        4. 环境信息（cwd, 批准策略等）
        5. 可用工具列表
        """
        # 1. 读取基础系统提示词
        system_prompt = self._load_base_prompt()
        
        # 2. 添加用户自定义指令
        if user_instructions:
            system_prompt += f"\n\n用户指令:\n{user_instructions}"
        
        # 3. 加载项目文档
        if auto_load_project_docs:
            project_docs = self.doc_loader.load_as_system_message()
            if project_docs:
                system_prompt += f"\n\n{project_docs}"
        
        # 4. 添加环境信息和工具列表
        if self.config and self.tool_registry:
            env_info = self._build_environment_info()
            system_prompt += f"\n\n{env_info}"
        
        return system_prompt
    
    def _load_base_prompt(self) -> str:
        """加载基础系统提示词"""
        try:
            from pathlib import Path
            prompt_file = Path(__file__).parent.parent.parent / "prompt" / "ctv-claude-code-system-prompt-zh.txt"
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # 回退到配置中的基础指令
            if self.config:
                return getattr(self.config, 'base_instructions', 
                              "You are Codex, an AI coding assistant.")
            return "You are Codex, an AI coding assistant."
    
    def _build_environment_info(self) -> str:
        """构建环境信息和工具列表"""
        parts = ["## 当前环境信息", ""]
        
        # 环境配置
        parts.append(f"当前工作目录: {self.cwd}")
        if self.config:
            parts.append(f"批准策略: {getattr(self.config, 'approval_policy', 'on_request')}")
            parts.append(f"沙箱策略: {getattr(self.config, 'sandbox_policy', 'workspace_write')}")
        
        # 工具列表
        if self.tool_registry:
            parts.append("\n## 可用工具\n")
            parts.append("你可以使用以下工具:")
            
            available_tools = self.tool_registry.get_tools_dict(enabled_only=True)
            for i, tool in enumerate(available_tools):
                parts.append(f"{i+1}. {tool['name']} - {tool['description']}")
            
            parts.append("\n请根据用户的需求，使用合适的工具来完成任务。在执行可能有风险的操作时，会根据批准策略询问用户确认。")
        
        return "\n".join(parts)
    
    @classmethod
    def resume_session(
        cls,
        rollout_path: Path
    ) -> "MemoryManager":
        """恢复已有会话
        
        Args:
            rollout_path: rollout 文件路径
        
        Returns:
            恢复的记忆管理器实例
        """
        logger.info(f"恢复会话: {rollout_path}")
        
        # 1. 加载历史
        session_meta, messages = RolloutRecorder.load_history(rollout_path)
        
        # 2. 创建管理器（不初始化）
        instance = cls.__new__(cls)
        instance.session_id = session_meta.session_id
        instance.cwd = Path(session_meta.cwd)
        instance.model = session_meta.model
        instance.session_dir = rollout_path.parent
        instance.rollout_path = rollout_path
        
        # 3. 恢复组件
        instance.messages = messages
        instance.doc_loader = ProjectDocLoader(instance.cwd)
        
        # 4. 重新打开 Recorder（追加模式）
        instance.recorder = RolloutRecorder(rollout_path, session_meta.session_id)
        
        logger.info(f"恢复完成: {len(messages)} 条消息")
        return instance
    
    def add_system_message(self, content: str) -> MemoryMessage:
        """添加系统消息
        
        Args:
            content: 消息内容
        
        Returns:
            添加的消息对象
        """
        msg = MemoryMessage(
            role="system",
            content=content,
            timestamp=datetime.now()
        )
        self.messages.append(msg)
        self.recorder.write_message(msg)
        return msg
    
    def add_user_message(self, content: str) -> MemoryMessage:
        """添加用户消息
        
        Args:
            content: 消息内容
        
        Returns:
            添加的消息对象
        """
        msg = MemoryMessage(
            role="user",
            content=content,
            timestamp=datetime.now()
        )
        self.messages.append(msg)
        self.recorder.write_message(msg)
        return msg
    
    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[list] = None
    ) -> MemoryMessage:
        """添加助手消息
        
        Args:
            content: 消息内容
            tool_calls: 工具调用列表（可选）
        
        Returns:
            添加的消息对象
        """
        msg = MemoryMessage(
            role="assistant",
            content=content,
            timestamp=datetime.now(),
            tool_calls=tool_calls
        )
        self.messages.append(msg)
        self.recorder.write_message(msg)
        return msg
    
    def add_tool_message(
        self,
        content: str,
        tool_call_id: str
    ) -> MemoryMessage:
        """添加工具消息
        
        Args:
            content: 工具输出内容
            tool_call_id: 工具调用 ID
        
        Returns:
            添加的消息对象
        """
        msg = MemoryMessage(
            role="tool",
            content=content,
            timestamp=datetime.now(),
            tool_call_id=tool_call_id
        )
        self.messages.append(msg)
        self.recorder.write_message(msg)
        return msg
    
    def add_message(self, message: MemoryMessage) -> None:
        """添加消息对象（通用方法）
        
        Args:
            message: 消息对象
        """
        self.messages.append(message)
        self.recorder.write_message(message)
    
    def get_messages(
        self,
        filter_system: bool = False,
        filter_compressed: bool = False
    ) -> List[MemoryMessage]:
        """获取消息列表
        
        Args:
            filter_system: 是否过滤系统消息
            filter_compressed: 是否过滤压缩摘要消息
        
        Returns:
            消息列表
        """
        messages = self.messages.copy()
        
        if filter_system:
            messages = [m for m in messages if m.role != "system"]
        
        if filter_compressed:
            messages = [m for m in messages if not m.metadata.get("compressed")]
        
        return messages
    
    def replace_messages(self, messages: List[MemoryMessage], persist: bool = False) -> None:
        """替换整个消息历史（用于压缩后）
        
        Args:
            messages: 新的消息列表
            persist: 是否持久化新消息（压缩时不需要，因为已有压缩标记）
        
        注意：
        - 压缩场景：Session 会先调用 record_compaction() 写入标记，再调用此方法
        - 恢复场景：RolloutRecorder 已从文件读取，无需再次持久化
        - 手动替换场景：如果需要持久化，设置 persist=True
        """
        self.messages = messages
        
        # 如果需要持久化（非压缩场景），逐条写入
        if persist:
            for msg in messages:
                self.recorder.write_message(msg)
    
    def record_compaction(
        self,
        summary: str,
        original_count: int,
        tokens_saved: int = 0,
        strategy: str = "unknown"
    ) -> None:
        """记录压缩操作
        
        Args:
            summary: 压缩摘要
            original_count: 原始消息数量
            tokens_saved: 节省的 token 数
            strategy: 压缩策略名称
        """
        marker = CompactedMarker(
            summary=summary,
            original_count=original_count,
            tokens_saved=tokens_saved,
            strategy=strategy
        )
        self.recorder.write_compacted_marker(marker)
        logger.info(f"记录压缩: {original_count} 条消息 → 摘要, 节省 {tokens_saved} tokens")
    
    def get_context_for_llm(self) -> List[dict]:
        """获取 LLM 可用的上下文（转换为字典格式）
        
        Returns:
            消息字典列表
        """
        return [msg.to_dict() for msg in self.messages]
    
    def get_stats(self) -> dict:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        # 使用统一的 token 估算
        total_tokens = sum(estimate_tokens(m.content) for m in self.messages)
        
        return {
            "session_id": self.session_id,
            "total_messages": len(self.messages),
            "user_messages": sum(1 for m in self.messages if m.role == "user"),
            "assistant_messages": sum(1 for m in self.messages if m.role == "assistant"),
            "system_messages": sum(1 for m in self.messages if m.role == "system"),
            "tool_messages": sum(1 for m in self.messages if m.role == "tool"),
            "estimated_tokens": total_tokens,
            "rollout_path": str(self.rollout_path),
            "cwd": str(self.cwd),
            "model": self.model
        }
    
    @classmethod
    def list_sessions(cls, session_dir: Path) -> List[Tuple[Path, SessionMeta]]:
        """列出所有会话
        
        Args:
            session_dir: 会话目录
        
        Returns:
            [(rollout_path, session_meta), ...] 列表
        """
        return RolloutRecorder.list_sessions(session_dir)

