from pathlib import Path
from typing import Dict, Any, Optional
from app.database.database import get_connection
from app.services.logging_service import log_operation

def get_water_tank_status(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Tool: get_water_tank_status
    Description: Retrieves the current status of the farm's main water tank, including total capacity, current water level percentage, volume in litres, and pump operational status.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM water_tank WHERE farm_id = 1 LIMIT 1;")
    row = cursor.fetchone()
    conn.close()

    if not row:
        result = {"error": "Water tank record not found."}
        log_operation(
            farmer_command="Check water tank status",
            tool_called="get_water_tank_status",
            tool_output=result,
            status="FAILED",
            details="Water tank record missing from database",
            db_path=db_path
        )
        return result

    data = dict(row)
    current_litres = (data["current_level_pct"] / 100.0) * data["capacity_litres"]
    result = {
        "capacity_litres": data["capacity_litres"],
        "current_level_pct": data["current_level_pct"],
        "current_volume_litres": round(current_litres, 1),
        "pump_status": data["pump_status"],
        "updated_at": data["updated_at"],
        "summary": f"Water tank is {data['current_level_pct']}% full ({round(current_litres, 1)}L / {data['capacity_litres']}L). Pump is {data['pump_status']}."
    }

    log_operation(
        farmer_command="Check water tank status",
        tool_called="get_water_tank_status",
        tool_output=result,
        status="SUCCESS",
        db_path=db_path
    )


    return result
