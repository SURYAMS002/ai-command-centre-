from pathlib import Path
from typing import Dict, Any, Optional
from app.database.database import get_connection
from app.services.logging_service import log_operation

def get_weather(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Tool: get_weather
    Description: Retrieves ambient farm weather conditions including temperature (°C), relative humidity (%), and precipitation/rain probability (%).
    """
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

    data = dict(row)
    result = {
        "temperature_c": data["temperature_c"],
        "humidity_pct": data["humidity_pct"],
        "rain_probability_pct": data["rain_probability_pct"],
        "updated_at": data["updated_at"],
        "summary": f"Temperature is {data['temperature_c']}°C, humidity is {data['humidity_pct']}%, and rain probability is {data['rain_probability_pct']}%."
    }

    log_operation(
        farmer_command="Get weather status",
        tool_called="get_weather",
        tool_output=result,
        status="SUCCESS",
        db_path=db_path
    )


    return result
