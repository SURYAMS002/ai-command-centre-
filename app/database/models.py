from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class FarmModel(BaseModel):
    id: Optional[int] = None
    name: str
    location: str
    created_at: Optional[str] = None

class WaterTankModel(BaseModel):
    id: Optional[int] = None
    farm_id: int = 1
    capacity_litres: float
    current_level_pct: float
    pump_status: str  # "ON" | "OFF"
    updated_at: Optional[str] = None

class FieldModel(BaseModel):
    id: Optional[int] = None
    farm_id: int = 1
    name: str
    crop: str
    area_acres: float
    soil_moisture_pct: float
    irrigation_status: str  # "ON" | "OFF"
    soil_type: str = "Loamy"
    growth_stage: str = "Vegetative"
    ph_level: float = 6.8
    nitrogen_ppm: float = 140.0
    phosphorus_ppm: float = 50.0
    potassium_ppm: float = 180.0
    wilting_point_pct: float = 15.0
    field_capacity_pct: float = 32.0
    optimal_moisture_threshold_pct: float = 30.0
    updated_at: Optional[str] = None

class WeatherModel(BaseModel):
    id: Optional[int] = None
    farm_id: int = 1
    temperature_c: float
    humidity_pct: float
    rain_probability_pct: float
    updated_at: Optional[str] = None

class OperationLogModel(BaseModel):
    id: Optional[int] = None
    timestamp: str
    farmer_command: str
    detected_intent: Optional[str] = None
    tool_called: Optional[str] = None
    tool_input: Optional[str] = None
    tool_output: Optional[str] = None
    decision: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    status: str  # "SUCCESS" | "FAILED" | "BLOCKED" | "PENDING_CONFIRMATION"
    details: Optional[str] = None

class FarmStatusModel(BaseModel):
    farm: FarmModel
    water_tank: WaterTankModel
    fields: List[FieldModel]
    weather: WeatherModel
