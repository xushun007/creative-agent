"""Codex配置管理"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Codex配置类"""
    # 模型配置
    model_provider: str = "openai"
    model: str = "qwen-plus"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    
    # 工作目录
    cwd: Path = field(default_factory=Path.cwd)
    
    # 安全策略
    approval_policy: str = "on_request"
    sandbox_policy: str = "workspace_write"
    
    # 系统提示
    base_instructions: str = "You are Codex, an AI coding assistant. Help users with programming tasks."
    user_instructions: Optional[str] = None
    
    # 其他设置
    disable_response_storage: bool = False
    max_tokens: int = 4096
    temperature: float = 0.1
    
    # 执行控制
    max_turns: int = 20  # 单次任务最大对话轮次
    
    def __post_init__(self):
        """初始化后处理"""
        if self.api_key is None:
            self.api_key = os.getenv("DASHSCOPE_API_KEY")
        
        if self.api_base is None:
            self.api_base = os.getenv("$OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        # print(self.api_base)
        # print(self.api_key)

        # 确保cwd是Path对象
        if isinstance(self.cwd, str):
            self.cwd = Path(self.cwd)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """从字典创建配置"""
        return cls(**data)
    
    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """从配置文件加载"""
        import json
        import toml
        
        if not config_path.exists():
            return cls()
        
        if config_path.suffix == ".json":
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif config_path.suffix == ".toml":
            data = toml.load(config_path)
        else:
            raise ValueError(f"Unsupported config file format: {config_path.suffix}")
        
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "model_provider": self.model_provider,
            "model": self.model,
            "api_key": self.api_key,
            "api_base": self.api_base,
            "cwd": str(self.cwd),
            "approval_policy": self.approval_policy,
            "sandbox_policy": self.sandbox_policy,
            "base_instructions": self.base_instructions,
            "user_instructions": self.user_instructions,
            "disable_response_storage": self.disable_response_storage,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
    
    def save_to_file(self, config_path: Path):
        """保存到配置文件"""
        import json
        import toml
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        if config_path.suffix == ".json":
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        elif config_path.suffix == ".toml":
            with open(config_path, 'w', encoding='utf-8') as f:
                toml.dump(self.to_dict(), f)
        else:
            raise ValueError(f"Unsupported config file format: {config_path.suffix}")
    
    def validate(self) -> bool:
        """验证配置"""
        if not self.api_key:
            raise ValueError("API key is required")
        
        if not self.model:
            raise ValueError("Model name is required")
        
        if not self.cwd.exists():
            raise ValueError(f"Working directory does not exist: {self.cwd}")
        
        return True
