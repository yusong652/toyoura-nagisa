"""
邮件配置模块
包含邮件发送和接收相关的配置
"""
from __future__ import annotations
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailConfig(BaseSettings):
    """邮件配置"""
    
    # SMTP配置 - 必需的敏感信息
    smtp_server: str = Field(description="SMTP服务器地址", env="EMAIL_SMTP_SERVER")
    smtp_port: int = Field(default=587, ge=1, le=65535, description="SMTP端口", env="EMAIL_SMTP_PORT")
    username: str = Field(description="邮箱用户名", env="EMAIL_USERNAME")
    password: str = Field(description="邮箱密码或应用密码", env="EMAIL_PASSWORD")
    
    # IMAP配置 - 必需的敏感信息
    imap_server: str = Field(description="IMAP服务器地址", env="EMAIL_IMAP_SERVER")
    imap_port: int = Field(default=993, ge=1, le=65535, description="IMAP端口", env="EMAIL_IMAP_PORT")
    
    # 邮件配置
    use_tls: bool = Field(default=True, description="是否使用TLS")
    use_ssl: bool = Field(default=False, description="是否使用SSL")
    sender_name: str = Field(default="Nagisa Assistant", description="发件人名称")
    timeout: int = Field(default=30, ge=1, description="连接超时时间(秒)")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    



class AuthConfig(BaseSettings):
    """Google Auth配置"""
    
    # Google OAuth配置 - 必需的敏感信息
    client_id: str = Field(description="Google OAuth客户端ID", env="AUTH_CLIENT_ID")
    client_secret: str = Field(description="Google OAuth客户端密钥", env="AUTH_CLIENT_SECRET")
    
    # 可选配置
    redirect_uri: str = Field(default="urn:ietf:wg:oauth:2.0:oob", description="重定向URI")
    scopes: list[str] = Field(
        default=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar"
        ],
        description="OAuth权限范围"
    )
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    



class SearchConfig(BaseSettings):
    """搜索配置"""
    
    # Google Custom Search API配置 - 必需的敏感信息
    google_api_key: str = Field(description="Google Custom Search API密钥")
    google_search_engine_id: str = Field(description="Google Custom Search引擎ID")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='SEARCH__',
        extra='ignore'
    )
    



# 全局配置实例
def get_email_config() -> EmailConfig:
    """获取邮件配置实例"""
    return EmailConfig()


def get_auth_config() -> AuthConfig:
    """获取认证配置实例"""
    return AuthConfig()


def get_search_config() -> SearchConfig:
    """获取搜索配置实例"""
    return SearchConfig() 