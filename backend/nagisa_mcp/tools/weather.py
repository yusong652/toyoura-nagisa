# from nagisa_mcp.server import mcp

def register_tools():
    from nagisa_mcp.server import mcp
    @mcp.tool()
    async def search_weather(city: str) -> dict:
        # 这里只是模拟数据，实际应用中应该调用真实的天气 API
        weather_data = {
            "北京": {"temperature": 25, "condition": "晴", "humidity": 40},
            "上海": {"temperature": 28, "condition": "多云", "humidity": 60},
            "广州": {"temperature": 30, "condition": "雨", "humidity": 80}
        }
        if city in weather_data:
            return weather_data[city]
        raise ValueError(f"City {city} not found") 