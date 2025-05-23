import asyncio
from fastmcp import Client

async def main():
    # 创建客户端
    client = Client("nagisa_mcp/fast_mcp_server.py")
    async with client:
        # 测试获取当前时间
        print("\n测试获取当前时间:")
        time = await client.call_tool("get_current_time")
        print(f"当前时间: {time}")
        
        # 测试计算功能
        print("\n测试计算功能:")
        result = await client.call_tool("calculate", {"expression": "2 + 2 * 3"})
        print(f"计算结果: {result}")
        
        # 测试天气查询
        print("\n测试天气查询:")
        try:
            weather = await client.call_tool("search_weather", {"city": "北京"})
            print(f"北京天气: {weather}")
        except Exception as e:
            print(f"天气查询错误: {e}")
        
        # 测试翻译功能
        print("\n测试翻译功能:")
        translation = await client.call_tool("translate_text", {"text": "你好", "target_language": "en"})
        print(f"翻译结果: {translation}")

if __name__ == "__main__":
    asyncio.run(main()) 