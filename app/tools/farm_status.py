from pathlib import Path
from typing import Dict, Any, Optional
from app.database.database import get_farm_status_data
from app.services.logging_service import log_operation

def get_farm_status(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Tool: get_farm_status
    Description: Retrieves complete, aggregated operational status across all farm components (water tank, fields, soil moisture, active irrigation, weather).
    """
    try:
        farm_status = get_farm_status_data(db_path)
        data = farm_status.model_dump()
        
        # Build natural language summary string
        fields_summary = ", ".join([
            f"{f['name']}: soil {f['soil_moisture_pct']}%, irrigation {f['irrigation_status']}"
            for f in data["fields"]
        ])
        summary = (
            f"Farm '{data['farm']['name']}' Status: Tank level is {data['water_tank']['current_level_pct']}% full. "
            f"Fields ({fields_summary}). "
            f"Weather: Temp {data['weather']['temperature_c']}°C, Humidity {data['weather']['humidity_pct']}%, Rain Prob {data['weather']['rain_probability_pct']}%."
        )
        
        result = {
            "farm": data["farm"],
            "water_tank": data["water_tank"],
            "fields": data["fields"],
            "weather": data["weather"],
            "summary": summary
        }

        log_operation(
            farmer_command="Give me the farm status",
            tool_called="get_farm_status",
            tool_output={"summary": summary},
            status="SUCCESS",
            db_path=db_path
        )
        return result

    except Exception as e:
        result = {"error": f"Failed to retrieve farm status: {str(e)}"}
        log_operation(
            farmer_command="Give me the farm status",
            tool_called="get_farm_status",
            tool_output=result,
            status="FAILED",
            details=str(e),
            db_path=db_path
        )
        return result

