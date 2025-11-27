"""
全局异常处理器模块

提供标准化的异常处理逻辑，特别是针对LLM配置和导入错误的处理。
"""

from fastapi import Request
from fastapi.responses import JSONResponse


async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    """
    处理配置相关的值错误，特别是LLM客户端不支持的情况
    """
    error_message = str(exc)
    
    # 检查是否是LLM客户端相关的错误
    if "Unsupported LLM client" in error_message or "Unknown LLM client" in error_message:
        return JSONResponse(
            status_code=400,
            content={
                "error": "LLM Configuration Error",
                "message": error_message,
                "type": "unsupported_llm_client",
                "suggestion": "Please update your configuration to use 'gemini' as the LLM client."
            }
        )
    
    # 其他值错误
    return JSONResponse(
        status_code=400,
        content={
            "error": "Configuration Error",
            "message": error_message,
            "type": "value_error"
        }
    )


async def handle_import_error(request: Request, exc: ImportError) -> JSONResponse:
    """
    处理导入错误，通常是由于缺少依赖或已删除的模块引起
    """
    error_message = str(exc)
    
    # 检查是否是LLM客户端相关的导入错误
    if any(client in error_message for client in ["gpt", "anthropic", "mistral", "grok"]):
        return JSONResponse(
            status_code=500,
            content={
                "error": "LLM Client Import Error",
                "message": "Legacy LLM clients have been removed in the new architecture.",
                "type": "deprecated_client",
                "details": error_message,
                "solution": "Please configure your system to use 'gemini' as the LLM client."
            }
        )
    
    # 其他导入错误
    return JSONResponse(
        status_code=500,
        content={
            "error": "Import Error",
            "message": error_message,
            "type": "import_error"
        }
    )