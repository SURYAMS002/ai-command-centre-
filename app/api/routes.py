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

@router.get("/")
async def root():
    return {
        "title": settings.APP_NAME,
        "version": settings.VERSION,
        "phase": 4,
        "status": "operational",
        "docs_url": "/docs"
    }

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
