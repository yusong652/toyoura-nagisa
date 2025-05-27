from fastmcp import FastMCP
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

def register_common_tools(mcp: FastMCP):

    @mcp.tool()
    def get_current_time() -> str:
        """Get the current system time as a formatted string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @mcp.tool()
    def get_weather(
        city: str = Field(..., description="The city name in English, e.g. 'London' (please do not use Chinese)"),
        unit: str = Field("metric", description="'metric' for Celsius, 'imperial' for Fahrenheit")
    ) -> dict:
        """
        Get the current weather for a city using the OpenWeatherMap API.

        Note: The 'city' parameter must be provided in English (e.g., 'London'). 
        Do not use Chinese or other non-English city names, as the API only supports English input.

        Args:
            city: The city name in English, e.g. 'London'. Do not use Chinese.
            unit: 'metric' for Celsius, 'imperial' for Fahrenheit.

        Returns:
            A dictionary with weather information (temperature, description, etc.)
        """
        API_KEY = os.getenv("OPEN_WEATHER_API_KEY")
        print(city)
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units={unit}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "city": data.get("name"),
                    "temperature": data["main"]["temp"],
                    "description": data["weather"][0]["description"],
                    "humidity": data["main"]["humidity"],
                    "wind_speed": data["wind"]["speed"]
                }
            else:
                return {"error": f"Failed to fetch weather: {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def get_location() -> dict:
        """
        获取当前服务器的公网IP地理位置信息。

        本工具通过后端服务器的公网IP调用第三方API（如ip-api.com）获取地理位置。
        返回内容包括城市名、经纬度等。
        未来可扩展为前端定位（如浏览器或移动端定位）。

        Returns:
            一个包含地理位置信息的字典，例如：
            {
                "city": "Beijing",
                "latitude": 39.9042,
                "longitude": 116.4074,
                "country": "China",
                "region": "Beijing"
            }
        """
        try:
            resp = requests.get("http://ip-api.com/json/", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "city": data.get("city"),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "country": data.get("country"),
                    "region": data.get("regionName"),
                    "ip": data.get("query")
                }
            else:
                return {"error": f"Failed to fetch location: {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)} 