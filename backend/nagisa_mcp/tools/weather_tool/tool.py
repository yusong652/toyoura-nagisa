from fastmcp import FastMCP
from pydantic import Field
import os
import requests


def register_weather_tools(mcp: FastMCP):
    """Register weather related tools."""

    @mcp.tool(tags={"weather"}, annotations={"category": "weather"})
    def get_weather(
        city: str = Field(..., description="City name in English, e.g. 'London'"),
        forecast_days: int = Field(0, ge=0, le=5, description="Number of days forecast (0-5). 0 for current only")
    ) -> dict:
        """Fetch current weather or simple forecast from OpenWeatherMap API."""
        API_KEY = os.getenv("OPEN_WEATHER_API_KEY")
        if not API_KEY:
            return {"error": "OPEN_WEATHER_API_KEY not set in environment"}

        try:
            if forecast_days and forecast_days > 0:
                url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    return {"error": f"Failed to fetch forecast: {resp.status_code}"}
                data = resp.json()
                from collections import defaultdict

                daily_temps = defaultdict(list)
                daily_desc = defaultdict(list)
                for item in data.get("list", []):
                    date_key = item["dt_txt"].split(" ")[0]
                    daily_temps[date_key].append(item["main"]["temp"])
                    daily_desc[date_key].append(item["weather"][0]["description"])

                forecast = []
                for date_key in sorted(daily_temps.keys())[:forecast_days]:
                    temps = daily_temps[date_key]
                    desc = max(set(daily_desc[date_key]), key=daily_desc[date_key].count)
                    forecast.append({
                        "date": date_key,
                        "temp_min": min(temps),
                        "temp_max": max(temps),
                        "description": desc
                    })
                return {"city": data.get("city", {}).get("name", city), "forecast": forecast}
            else:
                url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    return {"error": f"Failed to fetch weather: {resp.status_code}"}
                data = resp.json()
                return {
                    "city": data.get("name"),
                    "temperature": data["main"]["temp"],
                    "description": data["weather"][0]["description"],
                    "humidity": data["main"]["humidity"],
                    "wind_speed": data["wind"]["speed"]
                }
        except Exception as e:
            return {"error": str(e)} 