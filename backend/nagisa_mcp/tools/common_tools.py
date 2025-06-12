from fastmcp import FastMCP
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

def register_common_tools(mcp: FastMCP):
    # Register only common tools here

    @mcp.tool()
    def get_current_time() -> str:
        """Get the current system time as a formatted string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    def get_location() -> dict:
        """
        Get the current geographical location information.

        Returns a dictionary containing location details including city name, coordinates, country, and region.

        Returns:
            dict: A dictionary containing geographical information, for example:
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