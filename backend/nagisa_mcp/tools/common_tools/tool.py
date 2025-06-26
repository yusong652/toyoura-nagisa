# 内容来自原 common_tools.py 
from fastmcp import FastMCP
from fastmcp.server.context import Context
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional
import sys
from backend.config import LOCATION_DB_PATH
import time
import asyncio

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# Import using fully-qualified path to avoid duplicate module loading
from backend.nagisa_mcp.location_manager import get_location_manager, LocationData

load_dotenv()

# 获取位置管理器实例
location_manager = get_location_manager()

def _fetch_server_location() -> Optional[LocationData]:
    """
    通过 IP 地址获取服务器的地理位置。
    使用 ip-api.com 作为免费服务。
    """
    try:
        response = requests.get("http://ip-api.com/json", timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            location = LocationData(
                latitude=data['lat'],
                longitude=data['lon'],
                source="server_ip_geolocation",
                city=data.get('city'),
                country=data.get('country'),
                region=data.get('regionName')
            )
            print(f"Fetched server location: {location.to_dict()}")
            return location
    except requests.exceptions.RequestException as e:
        print(f"Error fetching server location: {e}")
    
    return None

# 反向地理编码（使用 OpenStreetMap Nominatim）
def _reverse_geocode(lat: float, lon: float) -> dict[str, Optional[str]]:
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "format": "json",
            "lat": lat,
            "lon": lon,
            "zoom": 10,
            "addressdetails": 1,
        }
        headers = {"User-Agent": "Nagisa-FastMCP/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("address", {})
            return {
                "city": data.get("city") or data.get("town") or data.get("village"),
                "region": data.get("state"),
                "country": data.get("country"),
            }
    except Exception as e:
        print(f"[reverse_geocode] failed: {e}")
    return {"city": None, "region": None, "country": None}

def register_common_tools(mcp: FastMCP):
    # Register only common tools here

    @mcp.tool()
    def get_current_time() -> dict:
        """Get the current system time as a formatted string."""
        return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    @mcp.tool()
    def get_weather(
        city: str = Field(..., description="The city name in English, e.g. 'London' (do not use non-English names)"),
        forecast_days: int = Field(0, ge=0, le=5, description="Number of days to fetch weather forecast for (0-5). 0 returns current weather only")
    ) -> dict:
        """
        Get the current weather for a city (in Celsius) or a simple daily forecast for the specified number of days.

        Args:
            city: The city name in English, e.g. 'London'.
            forecast_days: Number of days to fetch forecast for (max 5 as per OpenWeatherMap free tier). If 0, only current weather is returned.

        Returns:
            dict: Weather information. If forecast_days == 0, returns current conditions. Otherwise returns a list of daily forecasts.
        """
        API_KEY = os.getenv("OPEN_WEATHER_API_KEY")
        if not API_KEY:
            return {"error": "OPEN_WEATHER_API_KEY not set in environment"}

        try:
            if forecast_days and forecast_days > 0:
                # Fetch 5-day / 3-hour forecast and aggregate by day
                url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    return {"error": f"Failed to fetch weather forecast: {resp.status_code}"}
                data = resp.json()
                from collections import defaultdict
                daily_temps = defaultdict(list)
                daily_descriptions = defaultdict(list)
                for item in data.get("list", []):
                    date_str = item["dt_txt"].split(" ")[0]  # 'YYYY-MM-DD'
                    daily_temps[date_str].append(item["main"]["temp"])
                    daily_descriptions[date_str].append(item["weather"][0]["description"])
                forecast = []
                for date_str in sorted(daily_temps.keys())[:forecast_days]:
                    temps = daily_temps[date_str]
                    # Choose the most frequent description for the day
                    descs = daily_descriptions[date_str]
                    description = max(set(descs), key=descs.count)
                    forecast.append({
                        "date": date_str,
                        "temp_min": min(temps),
                        "temp_max": max(temps),
                        "description": description
                    })
                return {
                    "city": data.get("city", {}).get("name", city),
                    "forecast": forecast
                }
            else:
                # Current weather
                url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
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
    async def get_location(context: Context) -> dict:
        """
        Gets the client's geographical location, requesting it from the frontend if necessary.

        Workflow:
        1. Checks for a cached location associated with the current session.
        2. If no location is cached, it sends a request to the frontend via WebSocket.
        3. Waits for a few seconds for the frontend to report the location.
        4. If the request times out, it uses the server's IP address location as a final fallback.
        """
        session_id = context.client_id
        if not session_id:
            return {"error": "Session ID is missing."}

        # 1. 检查会话缓存
        loc = location_manager.get_session_location(session_id)
        if loc:
            return loc.to_dict()

        # 2. 如果没有缓存，请求前端并等待
        # 优雅地通过 Context.fastmcp 获取到在 FastAPI lifespan 中挂载的应用实例
        # -------- Debugging information --------
        print("[get_location] fastmcp object:", context.fastmcp)
        print("[get_location] fastmcp id:", id(context.fastmcp))
        app = getattr(context.fastmcp, "app", None)
        print("[get_location] Retrieved app:", app, "id:", id(app) if app else None)
        if app is not None:
            print("[get_location] app.state keys:", list(vars(app.state).keys()))

        connection_manager = None
        if app is not None and hasattr(app.state, "connection_manager"):
            connection_manager = app.state.connection_manager
            print(f"Requesting location from frontend for session {session_id} via WebSocket")
            asyncio.create_task(connection_manager.send_json(
                session_id, {"type": "REQUEST_LOCATION"}
            ))
        else:
            print("[get_location] connection_manager not found – relying solely on SSE LOCATION_REQUEST already emitted.")
        
        # 3. 等待前端响应
        wait_seconds = 30
        check_interval = 0.5  # 秒
        elapsed = 0.0
        while elapsed < wait_seconds:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            loc = location_manager.get_session_location(session_id)
            if loc:
                print(f"Received location from frontend for session {session_id}")
                loc_dict = loc.to_dict()
                # 若浏览器上报仅有经纬度，补充城市/国家信息
                if loc.source == "browser_geolocation" and not loc.city:
                    extra = _reverse_geocode(loc.latitude, loc.longitude)
                    loc_dict.update(extra)
                return loc_dict
        
        print(f"Timed out waiting for frontend location for session {session_id}")

        # 4. 使用全局位置作为备选
        loc = location_manager.get_global_location()
        if loc:
            print(f"Using global location as fallback for session {session_id}")
            return loc.to_dict()
            
        # 5. 使用服务器 IP 位置作为最终兜底
        print("Using server IP location as last resort.")
        loc = _fetch_server_location()
        if loc:
            return loc.to_dict()

        return {"error": "Location could not be determined."}