from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

from app.config import settings
from app.database.database import get_connection
from app.services.logging_service import log_operation

def get_weather(location: Optional[str] = None, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Tool: get_weather
    Description: Retrieves farm weather conditions including temperature (°C), relative humidity (%), and rain probability (%).
    Uses live OpenWeatherMap API if OPENWEATHER_API_KEY is configured, with automatic fallback to simulated SQLite state database.
    """
    target_location = location or settings.DEFAULT_FARM_LOCATION
    api_key = settings.OPENWEATHER_API_KEY

    if api_key:
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={target_location}&units=metric&appid={api_key}"
            response = httpx.get(url, timeout=5.0)
            
            if response.status_code == 200:
                data = response.json()
                temp_c = round(float(data["main"]["temp"]), 1)
                humidity_pct = round(float(data["main"]["humidity"]), 1)
                clouds_pct = float(data.get("clouds", {}).get("all", 0))
                
                # Rain probability estimation from OpenWeather response
                if "rain" in data:
                    rain_prob_pct = min(100.0, round(data["rain"].get("1h", 0.5) * 50.0, 1))
                else:
                    rain_prob_pct = round(min(100.0, clouds_pct * 0.8), 1)

                weather_desc = data["weather"][0]["description"].title() if data.get("weather") else "Clear"
                now = datetime.now().isoformat()

                # Sync live weather telemetry into SQLite state database
                conn = get_connection(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """UPDATE weather 
                       SET temperature_c = ?, humidity_pct = ?, rain_probability_pct = ?, updated_at = ? 
                       WHERE farm_id = 1;""",
                    (temp_c, humidity_pct, rain_prob_pct, now)
                )
                conn.commit()
                conn.close()

                result = {
                    "location": target_location,
                    "temperature_c": temp_c,
                    "humidity_pct": humidity_pct,
                    "rain_probability_pct": rain_prob_pct,
                    "description": weather_desc,
                    "source": "LIVE_OPENWEATHER_API",
                    "updated_at": now,
                    "summary": f"Live weather for {target_location}: {weather_desc}, {temp_c}°C, humidity {humidity_pct}%, rain probability {rain_prob_pct}%."
                }

                log_operation(
                    farmer_command=f"Get weather for {target_location}",
                    tool_called="get_weather",
                    tool_input={"location": target_location},
                    tool_output=result,
                    status="SUCCESS",
                    db_path=db_path
                )
                return result

        except Exception as e:
            # Catch API errors or timeout and fall back to SQLite database state
            pass

    # Fallback: Retrieve telemetry from SQLite state database
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM weather WHERE farm_id = 1 LIMIT 1;")
    row = cursor.fetchone()
    conn.close()

    if not row:
        result = {"error": "Weather data record not found."}
        log_operation(
            farmer_command="Get weather status",
            tool_called="get_weather",
            tool_output=result,
            status="FAILED",
            details="Weather record missing from database",
            db_path=db_path
        )
        return result

    db_data = dict(row)
    result = {
        "location": target_location,
        "temperature_c": db_data["temperature_c"],
        "humidity_pct": db_data["humidity_pct"],
        "rain_probability_pct": db_data["rain_probability_pct"],
        "source": "SIMULATED_DATABASE",
        "updated_at": db_data["updated_at"],
        "summary": f"Weather for {target_location}: Temperature is {db_data['temperature_c']}°C, humidity is {db_data['humidity_pct']}%, and rain probability is {db_data['rain_probability_pct']}%."
    }

    log_operation(
        farmer_command=f"Get weather for {target_location}",
        tool_called="get_weather",
        tool_input={"location": target_location},
        tool_output=result,
        status="SUCCESS",
        db_path=db_path
    )

    return result
