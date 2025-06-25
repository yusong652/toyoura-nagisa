# 内容来自原 common_tools.py 
from fastmcp import FastMCP
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional
import sys
from backend.config import LOCATION_DB_PATH

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from nagisa_mcp.location_manager import get_location_manager

load_dotenv()

# 获取位置管理器实例
location_manager = get_location_manager(LOCATION_DB_PATH)

def register_common_tools(mcp: FastMCP):
    # Register only common tools here

    @mcp.tool()
    def get_current_time() -> dict:
        """Get the current system time as a formatted string."""
        return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    @mcp.tool()
    def get_weather(
        city: str = Field(..., description="The city name in English, e.g. 'London' (do not use non-English names)")
    ) -> dict:
        """
        Get the current weather for a city (in Celsius).

        Args:
            city: The city name in English, e.g. 'London'.

        Returns:
            dict: A dictionary with weather information (temperature in Celsius, description, etc.)
        """
        API_KEY = os.getenv("OPEN_WEATHER_API_KEY")
        print(city)
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
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
    def get_location(session_id: Optional[str] = Field(None, description="Session ID to get location for")) -> dict:
        """
        Get the current geographical location information.

        Returns a dictionary containing location details including city name, coordinates, country, and region.
        This tool will use browser geolocation if available, otherwise falls back to IP-based location.

        Args:
            session_id: Optional session ID to get location for. If not provided, uses the most recent location.

        Returns:
            dict: A dictionary containing geographical information, for example:
            {
                "city": "Beijing",
                "latitude": 39.9042,
                "longitude": 116.4074,
                "country": "China",
                "region": "Beijing",
                "source": "browser_geolocation"
            }
        """
        def enrich_location_info(location):
            """补充位置信息（城市、国家等）"""
            if not location.city:
                try:
                    resp = requests.get(
                        f"http://ip-api.com/json/?lat={location.latitude}&lon={location.longitude}", 
                        timeout=5
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        location_manager.update_session_location(
                            location.session_id,
                            city=data.get("city"),
                            country=data.get("country"),
                            region=data.get("regionName")
                        )
                        location.city = data.get("city")
                        location.country = data.get("country")
                        location.region = data.get("regionName")
                except Exception as e:
                    pass  # 如果反向地理编码失败，继续使用现有信息
            return location

        # 首先尝试获取指定session的位置信息
        if session_id:
            session_location = location_manager.get_session_location(session_id)
            if session_location:
                session_location = enrich_location_info(session_location)
                return {
                    "city": session_location.city,
                    "latitude": session_location.latitude,
                    "longitude": session_location.longitude,
                    "country": session_location.country,
                    "region": session_location.region,
                    "accuracy": session_location.accuracy,
                    "source": session_location.source,
                    "timestamp": session_location.timestamp,
                    "session_id": session_location.session_id
                }
        
        # 如果没有指定session或session不存在，尝试获取全局位置信息
        global_location = location_manager.get_global_location()
        if global_location:
            global_location = enrich_location_info(global_location)
            return {
                "city": global_location.city,
                "latitude": global_location.latitude,
                "longitude": global_location.longitude,
                "country": global_location.country,
                "region": global_location.region,
                "accuracy": global_location.accuracy,
                "source": global_location.source,
                "timestamp": global_location.timestamp,
                "session_id": global_location.session_id
            }
        
        # 如果没有任何位置信息，回退到IP定位
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
                    "ip": data.get("query"),
                    "source": "ip_geolocation",
                    "accuracy": "low"  # IP定位精度较低
                }
            else:
                return {"error": f"Failed to fetch location: {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)} 