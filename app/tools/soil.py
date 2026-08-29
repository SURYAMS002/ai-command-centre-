from pathlib import Path
from typing import Dict, Any, Optional
from app.database.database import get_connection
from app.services.logging_service import log_operation

def get_soil_moisture(field_name: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Tool: get_soil_moisture
    Description: Retrieves current soil moisture percentage, crop type, acreage, and irrigation status for a specified field.
    Input: field_name (str) - e.g. 'Field A', 'Field B'
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fields WHERE LOWER(name) = LOWER(?);", (field_name.strip(),))
    row = cursor.fetchone()
    conn.close()

    if not row:
        error_msg = f"Field '{field_name}' not found in farm records."
        result = {"error": error_msg}
        log_operation(
            farmer_command=f"Check soil moisture in {field_name}",
            tool_called="get_soil_moisture",
            tool_input={"field_name": field_name},
            tool_output=result,
            status="FAILED",
            details=error_msg,
            db_path=db_path
        )
        return result

    data = dict(row)
    result = {
        "field_name": data["name"],
        "crop": data["crop"],
        "area_acres": data["area_acres"],
        "soil_moisture_pct": data["soil_moisture_pct"],
        "irrigation_status": data["irrigation_status"],
        "updated_at": data["updated_at"],
        "summary": f"{data['name']} ({data['crop']}) soil moisture is {data['soil_moisture_pct']}%. Irrigation is currently {data['irrigation_status']}."
    }

    log_operation(
        farmer_command=f"Check soil moisture in {field_name}",
        tool_called="get_soil_moisture",
        tool_input={"field_name": field_name},
        tool_output=result,
        status="SUCCESS",
        db_path=db_path
    )


    return result
