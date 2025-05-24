from fastmcp import FastMCP
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

class WeatherInput(BaseModel):
    city: str = Field(..., description="The city name, e.g. 'London'")
    unit: str = Field("metric", description="'metric' for Celsius, 'imperial' for Fahrenheit")
    class Config:
        json_schema_extra = {
            "additionalProperties": False
        }

def register_common_tools(mcp: FastMCP):

    @mcp.tool()
    def get_current_time() -> str:
        """Get the current system time as a formatted string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @mcp.tool()
    def get_weather(
        city: str = Field(..., description="The city name, e.g. 'London'"),
        unit: str = Field("metric", description="'metric' for Celsius, 'imperial' for Fahrenheit")
    ) -> dict:
        """
        Get the current weather for a city using OpenWeatherMap API.
        Args:
            city: The city name, e.g. 'London'
            unit: 'metric' for Celsius, 'imperial' for Fahrenheit
        Returns:
            A dictionary with weather info (temperature, description, etc.)
        """
        API_KEY = os.getenv("OPEN_WEATHER_API_KEY")
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