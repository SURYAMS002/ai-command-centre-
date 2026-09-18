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
        from app.services.agronomic_engine import AgronomicParameterEngine
        now = datetime.now().isoformat()
        conn = get_connection()
        cursor = conn.cursor()

        field_target = payload.field_name or "Field A"

        # 1. Update Soil Moisture for target field
        if payload.soil_moisture_pct is not None:
            cursor.execute(
                "UPDATE fields SET soil_moisture_pct = ?, updated_at = ? WHERE LOWER(name) = LOWER(?);",
                (payload.soil_moisture_pct, now, field_target)
            )

        # 2. Update Water Tank level
        if payload.water_tank_level_pct is not None:
            cursor.execute(
                "UPDATE water_tank SET current_level_pct = ?, updated_at = ? WHERE farm_id = 1;",
                (payload.water_tank_level_pct, now)
            )

        # 3. Update Microclimate Weather (DHT11/22)
        if payload.temperature_c is not None and payload.humidity_pct is not None:
            cursor.execute(
                "UPDATE weather SET temperature_c = ?, humidity_pct = ?, updated_at = ? WHERE farm_id = 1;",
                (payload.temperature_c, payload.humidity_pct, now)
            )

        conn.commit()

        # 4. Fetch Current Field Agronomic State & Calculate Dynamic FAO-56 Threshold
        cursor.execute("SELECT * FROM fields WHERE LOWER(name) = LOWER(?);", (field_target,))
        field_row = cursor.fetchone()
        
        cursor.execute("SELECT * FROM water_tank WHERE farm_id = 1;")
        tank_row = cursor.fetchone()
        
        cursor.execute("SELECT * FROM weather WHERE farm_id = 1;")
        weather_row = cursor.fetchone()

        field_dict = dict(field_row) if field_row else {}
        tank_dict = dict(tank_row) if tank_row else {}
        weather_dict = dict(weather_row) if weather_row else {}

        soil_type = field_dict.get("soil_type", "Loamy")
        crop = field_dict.get("crop", "Tomato")
        growth_stage = field_dict.get("growth_stage", "Vegetative")
        curr_moisture = payload.soil_moisture_pct if payload.soil_moisture_pct is not None else field_dict.get("soil_moisture_pct", 0.0)
        curr_tank = payload.water_tank_level_pct if payload.water_tank_level_pct is not None else tank_dict.get("current_level_pct", 50.0)
        curr_temp = payload.temperature_c if payload.temperature_c is not None else weather_dict.get("temperature_c", 25.0)
        curr_hum = payload.humidity_pct if payload.humidity_pct is not None else weather_dict.get("humidity_pct", 60.0)
        current_pump_status = tank_dict.get("pump_status", "OFF")

        # Dynamic FAO-56 Threshold Calculation
        fao_calc = AgronomicParameterEngine.calculate_optimal_moisture_threshold(soil_type, crop, growth_stage)
        opt_threshold = fao_calc["threshold_pct"]
        fc_pct = fao_calc["fc_pct"]
        pwp_pct = fao_calc["pwp_pct"]

        # Save imputed threshold to DB
        cursor.execute(
            """UPDATE fields SET wilting_point_pct = ?, field_capacity_pct = ?, optimal_moisture_threshold_pct = ?
               WHERE LOWER(name) = LOWER(?);""",
            (pwp_pct, fc_pct, opt_threshold, field_target)
        )
        conn.commit()

        # 5. Closed-Loop Auto-Start / Auto-Stop Decision Engine
        target_pump_command = current_pump_status
        decision_reasoning = ""
        log_action = None

        if curr_tank <= 10.0 and current_pump_status == "ON":
            # Safety Tank Low Lockout
            target_pump_command = "OFF"
            decision_reasoning = f"CRITICAL SAFETY: Water tank level ({curr_tank:.1f}%) is below minimum 10% safety threshold. Emergency auto-stopping pump."
            log_action = "PUMP_EMERGENCY_STOP"

        elif curr_moisture < opt_threshold and curr_tank > 10.0 and current_pump_status == "OFF":
            # AUTO-START Trigger
            target_pump_command = "ON"
            decision_reasoning = (
                f"[FAO-56 AUTO-START] Live soil moisture ({curr_moisture:.1f}%) is below optimal threshold ({opt_threshold:.1f}%) "
                f"for {crop} ({growth_stage}) in {soil_type} soil. Microclimate: {curr_temp:.1f}°C, {curr_hum:.1f}% RH. Tank: {curr_tank:.1f}%. "
                f"Actuating relay to START irrigation motor."
            )
            log_action = "PUMP_AUTO_START"

        elif curr_moisture >= opt_threshold and current_pump_status == "ON":
            # AUTO-STOP Trigger (Zero Manual Stop Needed!)
            target_pump_command = "OFF"
            decision_reasoning = (
                f"[FAO-56 AUTO-STOP] Live soil moisture has reached {curr_moisture:.1f}%, meeting target threshold ({opt_threshold:.1f}%) "
                f"for {crop} in {soil_type} soil. Automatically deactivating relay to STOP irrigation motor."
            )
            log_action = "PUMP_AUTO_STOP"
        else:
            decision_reasoning = (
                f"System Optimal: Soil moisture {curr_moisture:.1f}% vs threshold {opt_threshold:.1f}%. "
                f"Pump state remains {current_pump_status}."
            )

        # Update DB with new pump state if changed
        if target_pump_command != current_pump_status:
            cursor.execute("UPDATE water_tank SET pump_status = ?, updated_at = ? WHERE farm_id = 1;", (target_pump_command, now))
            cursor.execute("UPDATE fields SET irrigation_status = ?, updated_at = ? WHERE LOWER(name) = LOWER(?);", (target_pump_command, now, field_target))
            
            if log_action:
                cursor.execute(
                    "INSERT INTO operation_logs (farm_id, action, details, status, timestamp) VALUES (1, ?, ?, 'SUCCESS', ?);",
                    (log_action, decision_reasoning, now)
                )
            conn.commit()

        conn.close()

        return {
            "status": "success",
            "pump_command": target_pump_command,
            "field_name": field_target,
            "current_soil_moisture_pct": curr_moisture,
            "optimal_threshold_pct": opt_threshold,
            "field_capacity_pct": fc_pct,
            "wilting_point_pct": pwp_pct,
            "water_tank_level_pct": curr_tank,
            "ai_reasoning": decision_reasoning,
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
