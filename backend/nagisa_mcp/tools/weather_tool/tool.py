from fastmcp import FastMCP
from pydantic import Field
import os
import requests
import asyncio
from typing import Optional, Dict, Any
from fastmcp.server.context import Context  # type: ignore

from backend.nagisa_mcp.utils.tool_result import ToolResult
from backend.nagisa_mcp.utils.location_utils import get_user_location, get_user_city


def _error(message: str, error_details: Optional[str] = None) -> dict:
    """Create standardized error response."""
    data = {"error": message}
    if error_details:
        data["details"] = error_details
    
    return ToolResult(
        status="error",
        message=f"Weather operation failed: {message}",
        llm_content={
            "operation": "get_weather",
            "result": {
                "error": message,
                "details": error_details
            },
            "summary": f"Unable to retrieve weather: {message}"
        },
        data=data
    ).model_dump()

def _success(weather_data: dict, location_source: str, city: str) -> dict:
    """Create standardized success response."""
    return ToolResult(
        status="success",
        message=f"Weather retrieved successfully for {city}",
        llm_content={
            "operation": "get_weather",
            "result": {
                "city": city,
                "weather_data": weather_data,
                "location_source": location_source
            },
            "summary": f"Weather for {city} ({location_source} location)"
        },
        data={
            "city": city,
            "weather_data": weather_data,
            "location_source": location_source
        }
    ).model_dump()


def register_weather_tools(mcp: FastMCP):
    """Register weather related tools with proper tags synchronization."""

    @mcp.tool(
        tags={"weather", "forecast", "openweather", "climate", "temperature", "location"}, 
        annotations={"category": "weather", "tags": ["weather", "forecast", "openweather", "climate", "temperature", "location"]}
    )
    async def get_weather(
        context: Context,
        city: Optional[str] = Field(None, description="City name in English. If not provided, will auto-detect from user location"),
        forecast_days: int = Field(0, ge=0, le=5, description="Number of days forecast (0-5). 0 for current only")
    ) -> dict:
        """Fetch current weather or forecast with automatic location detection.

        Core Functionality:
        Retrieves weather information from OpenWeatherMap API with intelligent location detection. Automatically determines user's city from browser geolocation when no city is specified, providing personalized weather data. Supports both current weather conditions and multi-day forecasts with temperature ranges and weather descriptions.

        Return Value:
        Success response:
        {
            "operation": "get_weather",
            "result": {
                "city": "New York",
                "weather_data": {
                    "current": {
                        "temperature": 22.5,
                        "description": "scattered clouds",
                        "humidity": 65,
                        "wind_speed": 3.2
                    }
                },
                "location_source": "browser_geolocation"
            },
            "summary": "Weather for New York (browser_geolocation location)"
        }

        Error response:
        {
            "operation": "get_weather",
            "result": {
                "error": "API key not configured",
                "details": "OPEN_WEATHER_API_KEY not set in environment"
            },
            "summary": "Unable to retrieve weather: API key not configured"
        }

        Strategic Usage:
        • Essential for weather-aware scheduling and outdoor activity planning
        • Automatically detects user's location for personalized weather information
        • Provides current conditions and multi-day forecasts for travel planning
        • Use for climate-aware recommendations and local service suggestions
        • Supports manual city specification for travel or location-specific queries
        • Integrates with location services for seamless user experience

        Args:
            city: Optional city name. If not provided, will auto-detect from user location
            forecast_days: Number of days to forecast (0-5). 0 returns current weather only
        """
        API_KEY = os.getenv("OPEN_WEATHER_API_KEY")
        if not API_KEY:
            return _error("API key not configured", "OPEN_WEATHER_API_KEY not set in environment")

        try:
            determined_city = city
            location_source = "manual_input"

            # If no city specified, try to detect from user location
            if not city:
                detected_city = await get_user_city(context, wait_time=8)
                if detected_city:
                    determined_city = detected_city
                    location_source = "auto_detected"
                else:
                    return _error("Location detection failed", "No location information available")

            # Fetch weather data
            if forecast_days and forecast_days > 0:
                # Get forecast data
                url = f"https://api.openweathermap.org/data/2.5/forecast?q={determined_city}&appid={API_KEY}&units=metric"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    return _error("Forecast fetch failed", f"API returned status {resp.status_code}")
                
                data = resp.json()
                from collections import defaultdict

                daily_temps = defaultdict(list)
                daily_desc = defaultdict(list)
                daily_humidity = defaultdict(list)
                daily_wind = defaultdict(list)
                
                for item in data.get("list", []):
                    date_key = item["dt_txt"].split(" ")[0]
                    daily_temps[date_key].append(item["main"]["temp"])
                    daily_desc[date_key].append(item["weather"][0]["description"])
                    daily_humidity[date_key].append(item["main"]["humidity"])
                    daily_wind[date_key].append(item["wind"]["speed"])

                forecast = []
                for date_key in sorted(daily_temps.keys())[:forecast_days]:
                    temps = daily_temps[date_key]
                    desc = max(set(daily_desc[date_key]), key=daily_desc[date_key].count)
                    avg_humidity = sum(daily_humidity[date_key]) / len(daily_humidity[date_key])
                    avg_wind = sum(daily_wind[date_key]) / len(daily_wind[date_key])
                    
                    forecast.append({
                        "date": date_key,
                        "temp_min": round(min(temps), 1),
                        "temp_max": round(max(temps), 1),
                        "temp_avg": round(sum(temps) / len(temps), 1),
                        "description": desc,
                        "humidity": round(avg_humidity),
                        "wind_speed": round(avg_wind, 1)
                    })
                
                weather_data = {
                    "forecast": forecast,
                    "forecast_days": forecast_days
                }
                
            else:
                # Get current weather
                url = f"https://api.openweathermap.org/data/2.5/weather?q={determined_city}&appid={API_KEY}&units=metric"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    return _error("Weather fetch failed", f"API returned status {resp.status_code}")
                
                data = resp.json()
                weather_data = {
                    "current": {
                        "temperature": round(data["main"]["temp"], 1),
                        "feels_like": round(data["main"]["feels_like"], 1),
                        "description": data["weather"][0]["description"],
                        "humidity": data["main"]["humidity"],
                        "wind_speed": round(data["wind"]["speed"], 1),
                        "pressure": data["main"]["pressure"],
                        "visibility": data.get("visibility", "N/A")
                    }
                }

            return _success(weather_data, location_source, determined_city)
            
        except Exception as e:
            return _error("Weather retrieval failed", str(e)) 