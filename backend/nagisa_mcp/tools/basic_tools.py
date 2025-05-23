from datetime import datetime

# 延迟导入 mcp，仅在注册工具时导入，避免循环依赖

def register_tools():
    from nagisa_mcp.server import mcp
    @mcp.tool()
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    @mcp.tool()
    def get_current_time() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S") 