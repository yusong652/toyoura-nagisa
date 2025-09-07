"""
Tool Profile Manager - 简化的Agent身份化工具管理系统

分为两种模式：生活助手 和 编程助手
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class AgentProfile(Enum):
    """Agent身份类型"""
    LIFESTYLE = "lifestyle"  # 生活助手
    CODING = "coding"        # 编程助手
    PFC = "pfc"             # PFC仿真专家
    GENERAL = "general"      # 通用模式，加载所有工具
    DISABLED = "disabled"    # 禁用所有工具


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
        "edit",   # 文件编辑工具
        "bash",   # Updated from run_shell_command
        "ls",     # Updated from list_directory
        "glob",
        "grep",
        "web_search"  # 编程时也需要搜索
    ]
    
    # 生活类工具 (除了coding以外的所有工具，包括web_search)
    LIFESTYLE_TOOLS = [
        "send_email", 
        "check_emails",
        "read_email",
        "list_calendar_events",
        "create_calendar_event",
        "update_calendar_event", 
        "delete_calendar_event",
        "list_contacts",
        "search_contacts",
        "generate_image",
        "search_places",
        "get_location",
        "web_search",  # 生活中也需要搜索
        "get_current_time"
    ]
    
    # PFC simulation tools (coding tools + PFC-specific tools)
    PFC_TOOLS = [
        # File operation tools - for PFC scripts and data files
        "write",
        "read",
        "edit",
        # System command tools - for running PFC-related commands
        "bash",
        "ls",
        "glob",
        "grep",
        # Search tools - for finding PFC documentation and examples
        "web_search",
        # PFC-specific tools (to be added in the future)
        # "pfc_execute",        # Execute PFC commands
        # "pfc_model_create",   # Create models
        # "pfc_model_query",    # Query model state
        # "pfc_simulation_run", # Run simulations
        # "pfc_data_extract",   # Extract data
        # "pfc_visualization"   # Visualization
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
            estimated_tokens=len(LIFESTYLE_TOOLS) * 282,  # 14个工具
            color="#FF9800",  # 橙色
            icon="🌟"
        ),
        
        AgentProfile.PFC: ToolProfile(
            name="PFC Expert",
            description="ITASCA PFC simulation specialist with file operations and analysis tools",
            tools=PFC_TOOLS,
            estimated_tokens=len(PFC_TOOLS) * 282,  # Currently 8 basic tools, will expand in future
            color="#9C27B0",  # 紫色
            icon="⚛️"
        ),
        
        AgentProfile.GENERAL: ToolProfile(
            name="General",
            description="Full tool capabilities, suitable for complex tasks",
            tools=[],  # 空列表表示加载所有工具
            estimated_tokens=24 * 282,  # 所有24个工具
            color="#607D8B",  # 灰蓝色
            icon="🤖"
        ),
        
        AgentProfile.DISABLED: ToolProfile(
            name="Disabled",
            description="No tools enabled, pure conversation mode",
            tools=[],  # 空列表，但通过特殊逻辑处理为禁用所有工具
            estimated_tokens=0,  # 没有工具
            color="#F44336",  # 红色
            icon="🚫"
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
        return profile == AgentProfile.GENERAL
    
    @classmethod
    def should_disable_all_tools(cls, profile: AgentProfile) -> bool:
        """判断是否应该禁用所有工具"""
        return profile == AgentProfile.DISABLED
    
    @classmethod
    def get_available_profiles(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有可用的Agent身份配置（用于前端显示）"""
        return {
            profile.value: {
                "name": config.name,
                "description": config.description, 
                "estimated_tokens": config.estimated_tokens,
                "tool_count": len(config.tools) if config.tools else 24,
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