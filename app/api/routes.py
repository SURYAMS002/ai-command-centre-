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

@router.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AFOCC - AI Farm Operations Command Center</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; margin: 0; }
            .card { background: #1e293b; border-radius: 12px; padding: 30px; max-width: 700px; margin: 0 auto; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; }
            h1 { color: #38bdf8; margin-top: 0; font-size: 28px; }
            p { color: #94a3b8; line-height: 1.6; }
            .btn { display: inline-block; background: #0284c7; color: white; padding: 12px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-right: 10px; margin-top: 15px; transition: 0.2s; }
            .btn:hover { background: #0369a1; }
            .btn-alt { background: #10b981; }
            .btn-alt:hover { background: #059669; }
            .endpoint-box { background: #0f172a; padding: 15px; border-radius: 8px; margin-top: 20px; font-family: monospace; color: #a7f3d0; border: 1px solid #1e293b; }
            .tag { background: #3b82f6; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; vertical-align: middle; margin-left: 8px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🌾 AI Farm Operations Command Center (AFOCC) <span class="tag">v1.0</span></h1>
            <p>Phase 1 Dynamic Agronomic Soil-Crop Parameter Imputation Engine & Multi-Agent Safety System is operational on Vercel.</p>
            
            <a href="/docs" class="btn">🚀 Open Interactive API Specs (/docs)</a>
            <a href="/api/farm/status" class="btn btn-alt">📊 Real-Time Farm Status API</a>
            
            <div class="endpoint-box">
                <strong>Active Endpoints:</strong><br>
                • GET  /api/farm/status<br>
                • GET  /api/health<br>
                • GET  /api/tools/soil-moisture?field_name=Field A<br>
                • POST /api/agent/command<br>
                • POST /api/safety/validate
            </div>
        </div>
    </body>
    </html>
    """


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
