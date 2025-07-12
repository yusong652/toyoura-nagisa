"""
基础配置模块
包含路径配置、调试设置等通用配置项
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
CHAT_DIR = PROJECT_ROOT / "chat"


class BaseConfig(BaseSettings):
    """基础配置类"""
    
    # 路径配置
    base_dir: Path = Field(default=PROJECT_ROOT, description="项目根目录")
    chat_dir: Path = Field(default=CHAT_DIR, description="对话相关文件目录")
    tool_db_path: Path = Field(default=PROJECT_ROOT / "tool_db", description="工具数据库路径")
    location_db_path: Path = Field(default=PROJECT_ROOT / "location_data", description="位置数据库路径")
    memory_db_path: Path = Field(default=PROJECT_ROOT / "memory_db", description="记忆数据库路径")
    
    # 调试配置
    debug: bool = Field(default=False, description="全局调试开关")
    
    # 提示词配置
    base_prompt_env_key: str = Field(default="NAGISA_BASE_PROMPT", description="基础提示词环境变量键")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        env_prefix='APP_',
        extra='ignore'
    )
    

    
    def __init__(self, **data):
        super().__init__(**data)
        # 确保必要的目录存在
        self.tool_db_path.mkdir(parents=True, exist_ok=True)
        self.location_db_path.mkdir(parents=True, exist_ok=True)
        self.memory_db_path.mkdir(parents=True, exist_ok=True) 