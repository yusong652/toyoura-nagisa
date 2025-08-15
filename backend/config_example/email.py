"""
Email Configuration Module
Contains configurations for email sending and receiving
"""
from __future__ import annotations
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailConfig(BaseSettings):
    """Email Configuration"""
    
    # SMTP configuration - required sensitive information
    smtp_server: str = Field(description="SMTP server address", env="EMAIL_SMTP_SERVER")
    smtp_port: int = Field(default=587, ge=1, le=65535, description="SMTP port", env="EMAIL_SMTP_PORT")
    username: str = Field(description="Email username", env="EMAIL_USERNAME")
    password: str = Field(description="Email password or app password", env="EMAIL_PASSWORD")
    
    # IMAP configuration - required sensitive information
    imap_server: str = Field(description="IMAP server address", env="EMAIL_IMAP_SERVER")
    imap_port: int = Field(default=993, ge=1, le=65535, description="IMAP port", env="EMAIL_IMAP_PORT")
    
    # Email configuration
    use_tls: bool = Field(default=True, description="Whether to use TLS")
    use_ssl: bool = Field(default=False, description="Whether to use SSL")
    sender_name: str = Field(default="Nagisa Assistant", description="Sender name")
    timeout: int = Field(default=30, ge=1, description="Connection timeout (seconds)")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    

class AuthConfig(BaseSettings):
    """Google Auth Configuration"""
    
    # Google OAuth configuration - required sensitive information
    client_id: str = Field(description="Google OAuth client ID")
    client_secret: str = Field(description="Google OAuth client secret")
    
    # Google Maps API configuration - required sensitive information
    google_maps_api_key: str = Field(description="Google Maps API key", env="GOOGLE_MAPS_API_KEY")
    
    # Optional configuration
    redirect_uri: str = Field(default="urn:ietf:wg:oauth:2.0:oob", description="Redirect URI")
    scopes: list[str] = Field(
        default=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar"
        ],
        description="OAuth scope list"
    )
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='AUTH_',
        extra='ignore'
    )


class SearchConfig(BaseSettings):
    """Search Configuration"""
    
    # Google Custom Search API configuration - required sensitive information
    google_api_key: str = Field(description="Google Custom Search API key")
    google_search_engine_id: str = Field(description="Google Custom Search engine ID")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='SEARCH__',
        extra='ignore'
    )
    

# Global configuration instances
def get_email_config() -> EmailConfig:
    """Get email configuration instance"""
    return EmailConfig()


def get_auth_config() -> AuthConfig:
    """Get authentication configuration instance"""
    return AuthConfig()


def get_search_config() -> SearchConfig:
    """Get search configuration instance"""
    return SearchConfig() 