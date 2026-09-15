import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.config import settings
from app.database.models import (
    FarmModel, WaterTankModel, FieldModel, WeatherModel, FarmStatusModel
)

import os

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = db_path or settings.DATABASE_PATH
    if os.environ.get("VERCEL"):
        target_path = Path("/tmp") / "afocc.db"
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target_path)
    except (PermissionError, OSError):
        tmp_path = Path("/tmp") / "afocc.db"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(tmp_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[Path] = None, seed_path: Optional[Path] = None):
    target_db = db_path or (Path("/tmp") / "afocc.db" if os.environ.get("VERCEL") else settings.DATABASE_PATH)
    target_seed = seed_path or settings.SEED_DATA_PATH


    conn = get_connection(target_db)
    cursor = conn.cursor()

    # Create tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS farm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS water_tank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_id INTEGER NOT NULL DEFAULT 1,
            capacity_litres REAL NOT NULL,
            current_level_pct REAL NOT NULL,
            pump_status TEXT NOT NULL CHECK(pump_status IN ('ON', 'OFF')),
            updated_at TEXT NOT NULL,
            FOREIGN KEY (farm_id) REFERENCES farm (id)
        );

        CREATE TABLE IF NOT EXISTS fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_id INTEGER NOT NULL DEFAULT 1,
            name TEXT UNIQUE NOT NULL,
            crop TEXT NOT NULL,
            area_acres REAL NOT NULL,
            soil_moisture_pct REAL NOT NULL,
            irrigation_status TEXT NOT NULL CHECK(irrigation_status IN ('ON', 'OFF')),
            soil_type TEXT NOT NULL DEFAULT 'Loamy',
            growth_stage TEXT NOT NULL DEFAULT 'Vegetative',
            ph_level REAL NOT NULL DEFAULT 6.8,
            nitrogen_ppm REAL NOT NULL DEFAULT 140.0,
            phosphorus_ppm REAL NOT NULL DEFAULT 50.0,
            potassium_ppm REAL NOT NULL DEFAULT 180.0,
            wilting_point_pct REAL NOT NULL DEFAULT 15.0,
            field_capacity_pct REAL NOT NULL DEFAULT 32.0,
            optimal_moisture_threshold_pct REAL NOT NULL DEFAULT 30.0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (farm_id) REFERENCES farm (id)
        );

        CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_id INTEGER NOT NULL DEFAULT 1,
            temperature_c REAL NOT NULL,
            humidity_pct REAL NOT NULL,
            rain_probability_pct REAL NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (farm_id) REFERENCES farm (id)
        );

        CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            farmer_command TEXT NOT NULL,
            detected_intent TEXT,
            tool_called TEXT,
            tool_input TEXT,
            tool_output TEXT,
            decision TEXT,
            action TEXT,
            result TEXT,
            status TEXT NOT NULL,
            details TEXT
        );
    """)

    # Schema migration helper for existing SQLite databases
    cursor.execute("PRAGMA table_info(fields);")
    existing_cols = [row["name"] for row in cursor.fetchall()]
    new_cols_sql = {
        "soil_type": "TEXT NOT NULL DEFAULT 'Loamy'",
        "growth_stage": "TEXT NOT NULL DEFAULT 'Vegetative'",
        "ph_level": "REAL NOT NULL DEFAULT 6.8",
        "nitrogen_ppm": "REAL NOT NULL DEFAULT 140.0",
        "phosphorus_ppm": "REAL NOT NULL DEFAULT 50.0",
        "potassium_ppm": "REAL NOT NULL DEFAULT 180.0",
        "wilting_point_pct": "REAL NOT NULL DEFAULT 15.0",
        "field_capacity_pct": "REAL NOT NULL DEFAULT 32.0",
        "optimal_moisture_threshold_pct": "REAL NOT NULL DEFAULT 30.0"
    }

    for col_name, col_def in new_cols_sql.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE fields ADD COLUMN {col_name} {col_def};")

    conn.commit()

    # Seed initial data if farm table is empty
    cursor.execute("SELECT COUNT(*) as count FROM farm;")
    row = cursor.fetchone()
    if row["count"] == 0 and target_seed.exists():
        with open(target_seed, "r", encoding="utf-8") as f:
            seed_data = json.load(f)

        now = datetime.now().isoformat()

        # Insert Farm
        farm_info = seed_data["farm"]
        cursor.execute(
            "INSERT INTO farm (name, location, created_at) VALUES (?, ?, ?);",
            (farm_info["name"], farm_info["location"], now)
        )
        farm_id = cursor.lastrowid

        # Insert Water Tank
        tank_info = seed_data["water_tank"]
        cursor.execute(
            """INSERT INTO water_tank (farm_id, capacity_litres, current_level_pct, pump_status, updated_at)
               VALUES (?, ?, ?, ?, ?);""",
            (farm_id, tank_info["capacity_litres"], tank_info["current_level_pct"], tank_info["pump_status"], now)
        )

        # Insert Fields
        from app.services.agronomic_engine import AgronomicParameterEngine
        for field in seed_data.get("fields", []):
            s_type = field.get("soil_type", "Loamy" if field["name"] == "Field A" else "Clay")
            g_stage = field.get("growth_stage", "Flowering" if field["name"] == "Field A" else "Vegetative")
            profile = AgronomicParameterEngine.impute_field_parameters(
                soil_type=s_type,
                crop=field["crop"],
                growth_stage=g_stage
            )
            cursor.execute(
                """INSERT INTO fields (
                    farm_id, name, crop, area_acres, soil_moisture_pct, irrigation_status,
                    soil_type, growth_stage, ph_level, nitrogen_ppm, phosphorus_ppm, potassium_ppm,
                    wilting_point_pct, field_capacity_pct, optimal_moisture_threshold_pct, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    farm_id, field["name"], field["crop"], field["area_acres"], field["soil_moisture_pct"], field["irrigation_status"],
                    profile.soil_type, profile.growth_stage, profile.ph_level, profile.nitrogen_ppm, profile.phosphorus_ppm, profile.potassium_ppm,
                    profile.pwp_pct, profile.fc_pct, profile.optimal_moisture_threshold_pct, now
                )
            )

        # Insert Weather
        weather_info = seed_data["weather"]
        cursor.execute(
            """INSERT INTO weather (farm_id, temperature_c, humidity_pct, rain_probability_pct, updated_at)
               VALUES (?, ?, ?, ?, ?);""",
            (farm_id, weather_info["temperature_c"], weather_info["humidity_pct"], weather_info["rain_probability_pct"], now)
        )

        # Insert Sample Historical Operation Logs if empty
        cursor.execute("SELECT COUNT(*) as count FROM operation_logs;")
        if cursor.fetchone()["count"] == 0:
            sample_logs = [
                (now, "Irrigate Field A", "START_IRRIGATION", "start_irrigation", '{"field_name": "Field A"}', '{"status": "success"}', "RECOMMENDED", "START_IRRIGATION", "Pump started for Field A", "SUCCESS", "Irrigation pump started for Field A. Imputed threshold: 16.0%. Estimated water: 450 Litres."),
                (now, "Check farm status", "FARM_STATUS", "get_farm_status", '{}', '{"status": "success"}', "INFO", "FETCH_TELEMETRY", "Telemetry retrieved", "SUCCESS", "Fetched farm telemetry. Water Tank: 72.0%, Field A: 24.0%, Field B: 48.0%."),
                (now, "Irrigate Field B", "START_IRRIGATION", "start_irrigation", '{"field_name": "Field B"}', '{"status": "blocked"}', "BLOCKED", "SAFETY_CHECK", "Operation blocked", "BLOCKED", "Safety Gate Blocked: Field B moisture (48.0%) is already above optimal threshold (43.6%)."),
                (now, "Should I irrigate Field A?", "CHECK_IRRIGATION", "check_irrigation_requirement", '{"field_name": "Field A"}', '{"status": "evaluated"}', "EVALUATED", "DECISION_CHECK", "Moisture adequate", "SUCCESS", "Decision Engine: Field A moisture is 24.0% > threshold 16.0%. No irrigation needed."),
                (now, "Impute agronomic profile for Field A", "AGRONOMIC_UPDATE", "update_field_agronomic_profile", '{"soil_type": "Sandy", "crop": "Wheat"}', '{"status": "success"}', "IMPUTED", "PROFILE_UPDATE", "Profile updated", "SUCCESS", "Updated Field A profile to Sandy Soil, Wheat crop, Yield Formation stage. Dynamic threshold: 16.0%.")
            ]
            cursor.executemany(
                """INSERT INTO operation_logs (timestamp, farmer_command, detected_intent, tool_called, tool_input, tool_output, decision, action, result, status, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                sample_logs
            )

        conn.commit()


    conn.close()

def get_farm_status_data(db_path: Optional[Path] = None) -> FarmStatusModel:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM farm LIMIT 1;")
    farm_row = cursor.fetchone()
    if not farm_row:
        conn.close()
        raise ValueError("Farm database has not been initialized.")

    farm = FarmModel(**dict(farm_row))

    cursor.execute("SELECT * FROM water_tank WHERE farm_id = ? LIMIT 1;", (farm.id,))
    tank_row = cursor.fetchone()
    water_tank = WaterTankModel(**dict(tank_row))

    cursor.execute("SELECT * FROM fields WHERE farm_id = ?;", (farm.id,))
    field_rows = cursor.fetchall()
    fields = [FieldModel(**dict(r)) for r in field_rows]

    cursor.execute("SELECT * FROM weather WHERE farm_id = ? LIMIT 1;", (farm.id,))
    weather_row = cursor.fetchone()
    weather = WeatherModel(**dict(weather_row))

    conn.close()

    return FarmStatusModel(
        farm=farm,
        water_tank=water_tank,
        fields=fields,
        weather=weather
    )
