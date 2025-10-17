"""Codex配置管理 - 基于 pydantic-settings

配置优先级（从高到低）：
1. 代码传入参数
2. .env 文件（开发环境优先）
3. 系统环境变量
4. 默认值
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, Literal, Tuple
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource


class Config(BaseSettings):
    """配置类 - 支持.env文件和环境变量"""
    
    model_config = SettingsConfigDict(
        env_file=".env.mb",
        env_file_encoding="utf-8",
        env_prefix="CTV_",
        case_sensitive=False,
        extra="allow",
    )
    
    # 模型配置
    model_provider: str = Field(default="deepseek", description="模型提供商")
    model: str = Field(default="qwen-plus", description="模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    api_base: Optional[str] = Field(default=None, description="API基础URL")
    
    # 工作目录
    cwd: Path = Field(default_factory=lambda: Path.cwd() / "workspace", description="工作目录")
    
    # 安全策略
    approval_policy: Literal["always", "on_request", "never"] = Field(default="on_request")
    sandbox_policy: Literal["strict", "workspace_write", "none"] = Field(default="workspace_write")
    
    # 系统提示
    base_instructions: str = Field(
        default="You are Codex, an AI coding assistant. Help users with programming tasks.",
        description="基础系统指令"
    )
    user_instructions: Optional[str] = Field(default=None, description="用户自定义指令")
    
    # 模型参数
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大输出token数")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="采样温度")
    
    # 执行控制
    max_turns: int = Field(default=20, ge=1, le=100, description="最大对话轮次")
    disable_response_storage: bool = Field(default=False, description="禁用响应存储")
    
    # 消息压缩
    enable_compaction: bool = Field(default=False, description="启用消息压缩")
    max_context_tokens: int = Field(default=128000, ge=1000, description="最大上下文token数")
    
    # 压缩策略配置
    compaction_prune_minimum: int = Field(default=5000, ge=1000, description="Prune最小阈值(tokens)")
    compaction_prune_protect: int = Field(default=10000, ge=1000, description="Prune保护最近tokens")
    compaction_protect_turns: int = Field(default=2, ge=0, le=10, description="压缩时保护最近对话轮数")
    compaction_auto_threshold: float = Field(default=0.75, ge=0.1, le=1.0, description="自动压缩触发阈值")
    
    # 日志
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """自定义配置源优先级：代码传入 > .env文件 > 环境变量 > 默认值"""
        return init_settings, dotenv_settings, env_settings, file_secret_settings
    
    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        """加载 API Key，支持 OPENAI_API_KEY"""
        if v:
            return v
        return os.getenv("OPENAI_API_KEY")
    
    @field_validator("cwd", mode="before")
    @classmethod
    def validate_cwd(cls, v) -> Path:
        """转换工作目录为 Path 对象并确保是绝对路径"""
        path = Path(v) if isinstance(v, str) else v
        # 转换为绝对路径，确保AI能正确构建文件路径
        return path.resolve().absolute()
    
    @model_validator(mode="after")
    def ensure_workspace_exists(self):
        """确保工作目录存在"""
        self.cwd.mkdir(parents=True, exist_ok=True)
        return self
    
    @model_validator(mode="after")
    def validate_required_fields(self):
        """验证必需字段"""
        if not self.api_key:
            raise ValueError("API key is required. Set OPENAI_API_KEY or provide api_key")
        if not self.model:
            raise ValueError("Model name is required")
        return self
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """从字典创建配置"""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（隐藏敏感信息）"""
        data = self.model_dump()
        data["cwd"] = str(data["cwd"])
        if data.get("api_key"):
            data["api_key"] = "***" + data["api_key"][-4:] if len(data["api_key"]) > 4 else "***"
        return data
