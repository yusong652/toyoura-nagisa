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
        "execute_python_script",
        "read_many_files", 
        "write_file",
        "delete_file",
        "read_file",
        "run_shell_command",
        "list_directory",
        "delete_directory", 
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
        "search_tools",
        "get_available_tool_categories", 
        "get_current_time",
        "calculate"
    ]
    
    # 工具分类定义
    TOOL_PROFILES: Dict[AgentProfile, ToolProfile] = {
        AgentProfile.CODING: ToolProfile(
            name="编程助手",
            description="专注于代码开发、文件操作和编程相关任务",
            tools=CODING_TOOLS,
            estimated_tokens=len(CODING_TOOLS) * 282,  # 12个工具
            color="#4CAF50",  # 绿色
            icon="💻"
        ),
        
        AgentProfile.LIFESTYLE: ToolProfile(
            name="生活助手", 
            description="专注于日常生活、沟通、娱乐和信息服务",
            tools=LIFESTYLE_TOOLS,
            estimated_tokens=len(LIFESTYLE_TOOLS) * 282,  # 18个工具
            color="#FF9800",  # 橙色
            icon="🌟"
        ),
        
        AgentProfile.GENERAL: ToolProfile(
            name="通用助手",
            description="具备全部工具能力，适用于复杂任务",
            tools=[],  # 空列表表示加载所有工具
            estimated_tokens=8479,  # 所有30个工具
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
                "tool_count": len(config.tools) if config.tools else 30,
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