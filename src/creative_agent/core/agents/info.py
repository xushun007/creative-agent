"""Agent 信息数据类"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal


@dataclass
class AgentInfo:
    """Agent 配置信息
    
    Agent 是不可变的配置对象，定义了代理的行为和能力。
    """
    
    # 基本信息
    name: str                              # agent 名称（唯一标识）
    description: str                       # 描述
    mode: Literal["primary", "subagent"]   # 模式：主代理或子代理
    
    # 执行配置
    system_prompt: Optional[str] = None    # 系统提示（定义角色和行为）
    allowed_tools: List[str] = field(default_factory=list)  # 允许的工具列表
    
    # LLM 参数
    max_turns: int = 10                    # 最大执行轮次
    model_override: Optional[str] = None   # 可选的模型覆盖
    
    # 元数据
    native: bool = True                    # 是否内置 agent
    hidden: bool = False                   # 是否隐藏（UI 中不显示）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 其他元数据
    
    def __post_init__(self):
        """验证配置"""
        if not self.name:
            raise ValueError("Agent name cannot be empty")
        
        if self.mode not in ["primary", "subagent"]:
            raise ValueError(f"Invalid mode: {self.mode}")
        
        if not self.allowed_tools:
            raise ValueError(f"Agent {self.name} must have at least one allowed tool or '*'")
    
    def can_use_tool(self, tool_name: str) -> bool:
        """检查是否可以使用某个工具"""
        if "*" in self.allowed_tools:
            # 允许所有工具
            # 但 subagent 不能使用 task 工具（防止嵌套）
            if self.mode == "subagent" and tool_name == "task":
                return False
            return True
        
        return tool_name in self.allowed_tools
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "name": self.name,
            "description": self.description,
            "mode": self.mode,
            "system_prompt": self.system_prompt,
            "allowed_tools": self.allowed_tools,
            "max_turns": self.max_turns,
            "model_override": self.model_override,
            "native": self.native,
            "hidden": self.hidden,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        """从字典创建（用于反序列化）"""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            mode=data.get("mode", "subagent"),
            system_prompt=data.get("system_prompt"),
            allowed_tools=data.get("allowed_tools", []),
            max_turns=data.get("max_turns", 10),
            model_override=data.get("model_override"),
            native=data.get("native", False),
            hidden=data.get("hidden", False),
            metadata=data.get("metadata", {}),
        )
