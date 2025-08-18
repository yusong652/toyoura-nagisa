"""
Tool Profile Manager - 简化的Agent身份化工具管理系统

分为两种模式：生活助手 和 编程助手
"""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum


class AgentProfile(Enum):
    """Agent身份类型"""
    LIFESTYLE = "lifestyle"  # 生活助手
    CODING = "coding"        # 编程助手
    GENERAL = "general"      # 通用模式，加载所有工具


@dataclass
class ToolProfile:
    """工具集合配置"""
    name: str
    description: str
    tools: List[str]
    estimated_tokens: int
    color: str  # 前端显示颜色
    icon: str   # 前端显示图标


class ToolProfileManager:
    """工具集合管理器"""
    
    # 编程类工具 (coding + web_search)
    CODING_TOOLS = [
        "write",
        "read",
        "bash",  # Updated from run_shell_command
        "ls",    # Updated from list_directory
        "glob",
        "grep",
        "replace",
        "web_search"  # 编程时也需要搜索
    ]
    
    # 生活类工具 (除了coding以外的所有工具，包括web_search)
    LIFESTYLE_TOOLS = [
        "get_user_email",
        "send_email", 
        "check_emails",
        "list_calendar_events",
        "create_calendar_event",
        "update_calendar_event", 
        "delete_calendar_event",
        "list_contacts",
        "search_contacts",
        "generate_image",
        "search_places", 
        "get_place_details",
        "get_location",
        "get_weather",
        "web_search",  # 生活中也需要搜索
        "get_current_time"
    ]
    
    # 工具分类定义
    TOOL_PROFILES: Dict[AgentProfile, ToolProfile] = {
        AgentProfile.CODING: ToolProfile(
            name="Coding",
            description="Specialized in code development, file operations and programming tasks",
            tools=CODING_TOOLS,
            estimated_tokens=len(CODING_TOOLS) * 282,  # 8个工具
            color="#4CAF50",  # 绿色
            icon="💻"
        ),
        
        AgentProfile.LIFESTYLE: ToolProfile(
            name="Lifestyle", 
            description="Focused on daily life, communication, entertainment and information services",
            tools=LIFESTYLE_TOOLS,
            estimated_tokens=len(LIFESTYLE_TOOLS) * 282,  # 16个工具
            color="#FF9800",  # 橙色
            icon="🌟"
        ),
        
        AgentProfile.GENERAL: ToolProfile(
            name="General",
            description="Full tool capabilities, suitable for complex tasks",
            tools=[],  # 空列表表示加载所有工具
            estimated_tokens=23 * 282,  # 所有23个工具
            color="#607D8B",  # 灰蓝色
            icon="🤖"
        )
    }
    
    @classmethod
    def get_profile(cls, profile: AgentProfile) -> ToolProfile:
        """获取Agent配置"""
        return cls.TOOL_PROFILES[profile]
    
    @classmethod  
    def get_tools_for_profile(cls, profile: AgentProfile) -> List[str]:
        """获取指定身份的工具列表"""
        profile_config = cls.TOOL_PROFILES[profile]
        return profile_config.tools
    
    @classmethod
    def should_load_all_tools(cls, profile: AgentProfile) -> bool:
        """判断是否应该加载所有工具"""
        return profile == AgentProfile.GENERAL or len(cls.TOOL_PROFILES[profile].tools) == 0
    
    @classmethod
    def get_available_profiles(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有可用的Agent身份配置（用于前端显示）"""
        return {
            profile.value: {
                "name": config.name,
                "description": config.description, 
                "estimated_tokens": config.estimated_tokens,
                "tool_count": len(config.tools) if config.tools else 23,
                "color": config.color,
                "icon": config.icon
            }
            for profile, config in cls.TOOL_PROFILES.items()
        }
    
    @classmethod
    def validate_profile(cls, profile_name: str) -> Optional[AgentProfile]:
        """验证并返回Agent身份枚举"""
        try:
            return AgentProfile(profile_name)
        except ValueError:
            return None
    
    @classmethod
    def get_recommended_profile(cls, query: str) -> AgentProfile:
        """基于查询内容推荐最合适的Agent身份"""
        query_lower = query.lower()
        
        # 编程相关关键词
        coding_keywords = {
            "code", "python", "script", "file", "program", "debug", 
            "git", "function", "class", "api", "develop", "build",
            "test", "deploy", "command", "shell", "terminal"
        }
        if any(keyword in query_lower for keyword in coding_keywords):
            return AgentProfile.CODING
            
        # 其他都归为生活类
        return AgentProfile.LIFESTYLE