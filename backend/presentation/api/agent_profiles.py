"""
Agent Profile API Endpoints - Agent身份切换相关的API接口

提供Agent身份管理功能，包括切换、获取列表、推荐等。
"""

from fastapi import APIRouter, HTTPException, Request

from backend.presentation.models.agent_profile_models import (
    UpdateAgentProfileRequest,
    AgentProfileResponse, 
    GetAgentProfilesResponse,
    AgentProfileInfo,
    AgentProfileType
)
from backend.infrastructure.mcp.tool_profile_manager import ToolProfileManager, AgentProfile
from backend.infrastructure.llm import LLMClientBase


router = APIRouter(prefix="/api/agent", tags=["agent-profiles"])

# 全局状态：当前的Agent Profile
_current_agent_profile: AgentProfileType = AgentProfileType.GENERAL



def _convert_profile_type_to_enum(profile_type: AgentProfileType) -> AgentProfile:
    """转换API枚举到内部枚举"""
    if profile_type == AgentProfileType.DISABLED:
        # 禁用工具时返回None，在业务逻辑中特殊处理
        raise ValueError("DISABLED profile should be handled separately")
    
    mapping = {
        AgentProfileType.CODING: AgentProfile.CODING,
        AgentProfileType.LIFESTYLE: AgentProfile.LIFESTYLE,
        AgentProfileType.GENERAL: AgentProfile.GENERAL
    }
    return mapping[profile_type]


def _create_profile_info(profile_type: AgentProfileType) -> AgentProfileInfo:
    """创建Agent身份信息"""
    if profile_type == AgentProfileType.DISABLED:
        return AgentProfileInfo(
            profile_type=profile_type,
            name="Disabled",
            description="All tools disabled, pure text conversation mode",
            tool_count=0,
            estimated_tokens=0,
            color="#9E9E9E",  # 灰色
            icon="🚫"
        )
    
    try:
        profile_enum = _convert_profile_type_to_enum(profile_type)
        profile_config = ToolProfileManager.get_profile(profile_enum)
        
        return AgentProfileInfo(
            profile_type=profile_type,
            name=profile_config.name,
            description=profile_config.description,
            tool_count=len(profile_config.tools) if profile_config.tools else 30,
            estimated_tokens=profile_config.estimated_tokens,
            color=profile_config.color,
            icon=profile_config.icon
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的Profile类型: {profile_type}")


@router.post("/profile", response_model=AgentProfileResponse)
async def update_agent_profile(request: UpdateAgentProfileRequest, api_request: Request):
    """
    切换Agent身份
    
    支持的身份类型：
    - coding: 编程助手 (12个工具，专注代码开发)
    - lifestyle: 生活助手 (19个工具，专注日常服务)  
    - general: 通用助手 (30个工具，完整能力)
    - disabled: 禁用工具 (0个工具，纯文本模式)
    """
    global _current_agent_profile
    
    try:
        print(f"[DEBUG] Agent profile switch request: {request.profile}")
        
        # 获取LLM客户端
        llm_client: LLMClientBase = api_request.app.state.llm_client
        
        # 处理工具禁用情况
        if request.profile == AgentProfileType.DISABLED:
            llm_client.update_config(tools_enabled=False)
            _current_agent_profile = AgentProfileType.DISABLED
            
            # 清除工具缓存
            if request.session_id and hasattr(llm_client, '_clear_session_tool_cache'):
                await llm_client._clear_session_tool_cache(request.session_id)
            
            profile_info = _create_profile_info(AgentProfileType.DISABLED)
            
            return AgentProfileResponse(
                success=True,
                current_profile=AgentProfileType.DISABLED,
                profile_info=profile_info,
                tools_enabled=False,
                message="已切换到纯文本对话模式，所有工具已禁用"
            )
        
        # 启用工具并设置profile
        llm_client.update_config(tools_enabled=True)
        
        # 更新LLM客户端的agent_profile (需要在LLM客户端中添加支持)
        if hasattr(llm_client, 'update_agent_profile'):
            llm_client.update_agent_profile(request.profile.value)
        
        # 清除工具缓存以应用新的profile设置
        if request.session_id and hasattr(llm_client, '_clear_session_tool_cache'):
            await llm_client._clear_session_tool_cache(request.session_id)
            print(f"[DEBUG] Cleared tool cache for session: {request.session_id}")
        
        # 更新全局状态
        _current_agent_profile = request.profile
        
        # 创建响应信息
        profile_info = _create_profile_info(request.profile)
        
        print(f"[DEBUG] Agent profile switched to: {request.profile} ({profile_info.tool_count} tools)")
        
        return AgentProfileResponse(
            success=True,
            current_profile=request.profile,
            profile_info=profile_info,
            tools_enabled=True,
            message=f"已切换到{profile_info.name}模式，加载{profile_info.tool_count}个工具"
        )
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Agent profile switch failed: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"切换Agent身份失败: {str(e)}")


@router.get("/profiles", response_model=GetAgentProfilesResponse)
async def get_available_profiles():
    """获取所有可用的Agent身份列表"""
    global _current_agent_profile
    
    try:
        available_profiles = []
        
        # 添加所有支持的profile类型
        for profile_type in AgentProfileType:
            profile_info = _create_profile_info(profile_type)
            available_profiles.append(profile_info)
        
        return GetAgentProfilesResponse(
            success=True,
            current_profile=_current_agent_profile,
            available_profiles=available_profiles,
            message=f"当前Agent身份: {_current_agent_profile.value}"
        )
        
    except Exception as e:
        print(f"[ERROR] Get available profiles failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取Agent身份列表失败: {str(e)}")



@router.get("/status", response_model=dict)
async def get_agent_status(api_request: Request):
    """获取当前Agent状态信息"""
    global _current_agent_profile
    
    try:
        llm_client: LLMClientBase = api_request.app.state.llm_client
        tools_enabled = getattr(llm_client, 'tools_enabled', True)
        
        current_profile_info = _create_profile_info(_current_agent_profile)
        
        return {
            "success": True,
            "current_profile": _current_agent_profile,
            "profile_info": current_profile_info.model_dump(),
            "tools_enabled": tools_enabled,
            "message": f"当前模式: {current_profile_info.name}"
        }
        
    except Exception as e:
        print(f"[ERROR] Get agent status failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")