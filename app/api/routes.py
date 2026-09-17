from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings
from app.database.database import get_farm_status_data, get_connection
from app.database.models import FarmStatusModel, OperationLogModel
from app.services.safety import safety_validator, SafetyValidationResult
from app.tools import (
    get_water_tank_status,
    get_soil_moisture,
    get_weather,
    get_farm_status as fetch_farm_status,
    check_irrigation_requirement,
    start_irrigation,
    stop_irrigation
)

router = APIRouter()

from fastapi.responses import HTMLResponse
from app.tools.agronomic_tools import update_field_agronomic_profile
from app.templates.dashboard_template import DASHBOARD_HTML

@router.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=DASHBOARD_HTML)


class AgronomicUpdateRequestModel(BaseModel):
    field_name: str
    soil_type: Optional[str] = None
    crop: Optional[str] = None
    growth_stage: Optional[str] = None
    ph_level: Optional[float] = None

@router.post("/api/agronomic/update")
async def update_agronomic_profile_endpoint(payload: AgronomicUpdateRequestModel):
    return update_field_agronomic_profile(
        field_name=payload.field_name,
        soil_type=payload.soil_type,
        crop=payload.crop,
        growth_stage=payload.growth_stage,
        ph_level=payload.ph_level
    )


class SensorTelemetryModel(BaseModel):
    soil_moisture_pct: Optional[float] = None
    water_tank_level_pct: Optional[float] = None
    water_tank_distance_cm: Optional[float] = None
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    relay_status: Optional[str] = None
    field_name: Optional[str] = "Field A"

@router.post("/api/v1/sensors/telemetry")
async def ingest_hardware_telemetry(payload: SensorTelemetryModel):
    try:
        from datetime import datetime
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()

        # Update Soil Moisture for target field
        if payload.soil_moisture_pct is not None:
            cursor.execute(
                "UPDATE fields SET soil_moisture_pct = ?, updated_at = ? WHERE LOWER(name) = LOWER(?);",
                (payload.soil_moisture_pct, now, payload.field_name or "Field A")
            )

        # Update Water Tank level and pump relay status
        if payload.water_tank_level_pct is not None or payload.relay_status is not None:
            if payload.water_tank_level_pct is not None and payload.relay_status is not None:
                cursor.execute(
                    "UPDATE water_tank SET current_level_pct = ?, pump_status = ?, updated_at = ? WHERE farm_id = 1;",
                    (payload.water_tank_level_pct, payload.relay_status, now)
                )
            elif payload.water_tank_level_pct is not None:
                cursor.execute(
                    "UPDATE water_tank SET current_level_pct = ?, updated_at = ? WHERE farm_id = 1;",
                    (payload.water_tank_level_pct, now)
                )
            elif payload.relay_status is not None:
                cursor.execute(
                    "UPDATE water_tank SET pump_status = ?, updated_at = ? WHERE farm_id = 1;",
                    (payload.relay_status, now)
                )

        # Update Microclimate Weather (DHT11/22)
        if payload.temperature_c is not None and payload.humidity_pct is not None:
            cursor.execute(
                "UPDATE weather SET temperature_c = ?, humidity_pct = ?, updated_at = ? WHERE farm_id = 1;",
                (payload.temperature_c, payload.humidity_pct, now)
            )

        conn.commit()
        conn.close()
        return {
            "status": "success",
            "message": "ESP32 hardware telemetry ingested successfully",
            "field_name": payload.field_name or "Field A",
            "ingested_data": payload.model_dump(exclude_none=True),
            "timestamp": now
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telemetry ingestion failed: {str(e)}"
        )


@router.get("/api/health")
async def health_check():
    try:
        farm_status = get_farm_status_data()
        return {
            "status": "healthy",
            "database": "connected",
            "version": settings.VERSION,
            "phase": 4,
            "farm_name": farm_status.farm.name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )

@router.get("/api/farm/status", response_model=FarmStatusModel)
async def get_farm_status_endpoint():
    try:
        return get_farm_status_data()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch farm status: {str(e)}"
        )

# --- FARM TOOLS ENDPOINTS ---

@router.get("/api/tools/water-tank")
async def tool_water_tank_status():
    return get_water_tank_status()

@router.get("/api/tools/soil-moisture")
async def tool_soil_moisture(field_name: str = Query(..., description="Name of the field, e.g. Field A")):
    res = get_soil_moisture(field_name)
    if "error" in res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res["error"])
    return res

@router.get("/api/tools/weather")
async def tool_weather():
    return get_weather()

@router.get("/api/tools/farm-status")
async def tool_farm_status():
    return fetch_farm_status()

@router.post("/api/tools/check-irrigation")
async def tool_check_irrigation(field_name: str = Query(..., description="Name of the field, e.g. Field A")):
    res = check_irrigation_requirement(field_name)
    if "error" in res:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res["error"])
    return res

@router.post("/api/tools/start-irrigation")
async def tool_start_irrigation(field_name: str = Query(..., description="Name of the field, e.g. Field A"), skip_safety: bool = Query(False)):
    return start_irrigation(field_name, skip_safety=skip_safety)

@router.post("/api/tools/stop-irrigation")
async def tool_stop_irrigation(field_name: str = Query(..., description="Name of the field, e.g. Field A"), skip_safety: bool = Query(False)):
    return stop_irrigation(field_name, skip_safety=skip_safety)


# --- SAFETY ENDPOINT ---

class SafetyCheckModel(BaseModel):
    field_name: str
    action: str  # "START_IRRIGATION" | "STOP_IRRIGATION"

@router.post("/api/safety/validate", response_model=SafetyValidationResult)
async def validate_safety(payload: SafetyCheckModel):
    return safety_validator.validate_irrigation_request(payload.field_name, payload.action)

# --- AGENT COMMAND ENDPOINT ---

class CommandRequestModel(BaseModel):
    command: str
    pending_action: Optional[Dict[str, str]] = None

@router.post("/api/agent/command")
async def process_farmer_command(payload: CommandRequestModel):
    try:
        from app.agent.agent import default_agent
        result = default_agent.run_command(payload.command, pending_action=payload.pending_action)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent command processing error: {str(e)}"
        )

@router.get("/api/logs", response_model=List[OperationLogModel])
async def get_operation_logs(limit: int = Query(20, ge=1, le=100)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operation_logs ORDER BY id DESC LIMIT ?;", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [OperationLogModel(**dict(r)) for r in rows]
