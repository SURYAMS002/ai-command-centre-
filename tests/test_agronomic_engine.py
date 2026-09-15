import pytest
from pathlib import Path
from app.database.database import init_db, get_connection
from app.services.agronomic_engine import AgronomicParameterEngine, SOIL_PROPERTIES, CROP_AGRONOMIC_PROPERTIES
from app.services.decision_engine import IrrigationDecisionEngine
from app.tools.agronomic_tools import get_soil_crop_parameters, update_field_agronomic_profile
from app.tools.soil import get_soil_moisture

@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_agronomic.db"
    seed_file = tmp_path / "seed.json"

    # Create dummy seed file
    seed_content = """{
        "farm": {"name": "Test Agronomic Farm", "location": "Sector 9"},
        "water_tank": {"capacity_litres": 5000, "current_level_pct": 80.0, "pump_status": "OFF"},
        "fields": [
            {"name": "Field A", "crop": "Tomato", "area_acres": 1.0, "soil_moisture_pct": 24.0, "irrigation_status": "OFF"},
            {"name": "Field B", "crop": "Wheat", "area_acres": 2.0, "soil_moisture_pct": 45.0, "irrigation_status": "OFF"}
        ],
        "weather": {"temperature_c": 30.0, "humidity_pct": 65.0, "rain_probability_pct": 10.0}
    }"""
    seed_file.write_text(seed_content, encoding="utf-8")
    init_db(db_path=db_file, seed_path=seed_file)
    return db_file


def test_agronomic_engine_threshold_calculations():
    # Sandy soil, Tomato, Flowering stage
    sandy_tomato = AgronomicParameterEngine.calculate_optimal_moisture_threshold("Sandy", "Tomato", "Flowering")
    # PWP=10.0, FC=22.0, MAD=0.35 -> Threshold = 10 + (22-10)*(1-0.35) = 10 + 12*0.65 = 17.8%
    assert sandy_tomato["pwp_pct"] == 10.0
    assert sandy_tomato["fc_pct"] == 22.0
    assert sandy_tomato["threshold_pct"] == 17.8

    # Clay soil, Tomato, Flowering stage
    clay_tomato = AgronomicParameterEngine.calculate_optimal_moisture_threshold("Clay", "Tomato", "Flowering")
    # PWP=26.0, FC=48.0, MAD=0.35 -> Threshold = 26 + (48-26)*(0.65) = 26 + 22*0.65 = 40.3%
    assert clay_tomato["pwp_pct"] == 26.0
    assert clay_tomato["fc_pct"] == 48.0
    assert clay_tomato["threshold_pct"] == 40.3


def test_impute_field_parameters():
    profile = AgronomicParameterEngine.impute_field_parameters(
        soil_type="Clay",
        crop="Rice",
        growth_stage="Initial/Vegetative"
    )
    assert profile.soil_type == "Clay"
    assert profile.crop == "Rice"
    assert profile.ph_level == 7.2  # Clay default
    assert profile.nitrogen_ppm == 180.0  # Rice target


def test_agronomic_tools_and_db_migration(temp_db: Path):
    # Verify Initial Field A data
    params = get_soil_crop_parameters("Field A", db_path=temp_db)
    assert params["field_name"] == "Field A"
    assert params["soil_type"] == "Loamy"
    assert "wilting_point_pct" in params

    # Update Field A to Sandy soil and Flowering stage
    updated = update_field_agronomic_profile("Field A", soil_type="Sandy", growth_stage="Flowering", db_path=temp_db)
    assert updated["success"] is True
    assert updated["updated_profile"]["soil_type"] == "Sandy"

    # Re-check via get_soil_moisture
    soil_res = get_soil_moisture("Field A", db_path=temp_db)
    assert soil_res["soil_type"] == "Sandy"
    assert soil_res["growth_stage"] == "Flowering"


def test_dynamic_decision_engine_with_soil_parameters(temp_db: Path):
    engine = IrrigationDecisionEngine()
    
    # Field A is currently 24% soil moisture.
    # On Sandy soil, threshold is ~17.8% -> Moisture 24% >= 17.8% -> NOT RECOMMENDED
    update_field_agronomic_profile("Field A", soil_type="Sandy", growth_stage="Flowering", db_path=temp_db)
    res_sandy = engine.evaluate("Field A", db_path=temp_db)
    assert res_sandy["recommended"] is False
    assert "sufficient" in res_sandy["summary"]

    # Switch Field A to Clay soil. Threshold becomes ~40.3% -> Moisture 24% < 40.3% -> RECOMMENDED!
    update_field_agronomic_profile("Field A", soil_type="Clay", growth_stage="Flowering", db_path=temp_db)
    res_clay = engine.evaluate("Field A", db_path=temp_db)
    assert res_clay["recommended"] is True
    assert "RECOMMENDED" in res_clay["summary"]
