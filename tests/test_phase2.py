import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.database.database import init_db, get_connection
from app.tools import (
    get_water_tank_status,
    get_soil_moisture,
    get_weather,
    get_farm_status,
    check_irrigation_requirement,
    start_irrigation,
    stop_irrigation
)

@pytest.fixture
def setup_test_db(tmp_path: Path):
    test_db = tmp_path / "test_afocc_p2.db"
    seed_json = Path(__file__).resolve().parent.parent / "data" / "farm_data.json"
    init_db(db_path=test_db, seed_path=seed_json)
    return test_db

def test_water_tank_tool(setup_test_db: Path):
    res = get_water_tank_status(db_path=setup_test_db)
    assert "capacity_litres" in res
    assert res["capacity_litres"] == 5000.0
    assert res["current_level_pct"] == 72.0
    assert res["pump_status"] == "OFF"

def test_soil_moisture_tool(setup_test_db: Path):
    res_a = get_soil_moisture("Field A", db_path=setup_test_db)
    assert res_a["field_name"] == "Field A"
    assert res_a["crop"] == "Tomato"
    assert res_a["soil_moisture_pct"] == 24.0

    res_b = get_soil_moisture("Field B", db_path=setup_test_db)
    assert res_b["field_name"] == "Field B"
    assert res_b["soil_moisture_pct"] == 48.0

    res_invalid = get_soil_moisture("Field X", db_path=setup_test_db)
    assert "error" in res_invalid
    assert "not found" in res_invalid["error"]

def test_weather_tool(setup_test_db: Path):
    res = get_weather(db_path=setup_test_db)
    assert res["temperature_c"] == 31.0
    assert res["humidity_pct"] == 68.0
    assert res["rain_probability_pct"] == 15.0

def test_farm_status_tool(setup_test_db: Path):
    res = get_farm_status(db_path=setup_test_db)
    assert "summary" in res
    assert "Demo Farm" in res["summary"]
    assert len(res["fields"]) == 2

def test_decision_engine_tool(setup_test_db: Path):
    # Field A has 24% soil moisture (< 30%) -> SHOULD BE RECOMMENDED
    res_a = check_irrigation_requirement("Field A", db_path=setup_test_db)
    assert res_a["recommended"] is True
    assert "IS RECOMMENDED" in res_a["summary"]

    # Field B has 48% soil moisture (>= 30%) -> SHOULD NOT BE RECOMMENDED
    res_b = check_irrigation_requirement("Field B", db_path=setup_test_db)
    assert res_b["recommended"] is False
    assert "IS NOT RECOMMENDED" in res_b["summary"]

def test_mock_actuator_state_mutation(setup_test_db: Path):
    # Initial status of Field A is OFF
    initial = get_soil_moisture("Field A", db_path=setup_test_db)
    assert initial["irrigation_status"] == "OFF"

    # Start irrigation
    start_res = start_irrigation("Field A", skip_safety=True, db_path=setup_test_db)
    assert start_res["success"] is True
    assert start_res["irrigation_status"] == "ON"
    assert start_res["changed"] is True

    # Verify state in DB updated to ON
    after_start = get_soil_moisture("Field A", db_path=setup_test_db)
    assert after_start["irrigation_status"] == "ON"

    # Redundant start returns changed=False
    start_again = start_irrigation("Field A", skip_safety=True, db_path=setup_test_db)
    assert start_again["changed"] is False

    # Stop irrigation
    stop_res = stop_irrigation("Field A", skip_safety=True, db_path=setup_test_db)
    assert stop_res["success"] is True
    assert stop_res["irrigation_status"] == "OFF"
    assert stop_res["changed"] is True

    # Verify state in DB updated to OFF
    after_stop = get_soil_moisture("Field A", db_path=setup_test_db)
    assert after_stop["irrigation_status"] == "OFF"

def test_operation_logging(setup_test_db: Path):
    start_irrigation("Field A", skip_safety=True, db_path=setup_test_db)
    check_irrigation_requirement("Field B", db_path=setup_test_db)

    conn = get_connection(setup_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operation_logs ORDER BY id ASC;")
    logs = cursor.fetchall()
    conn.close()

    assert len(logs) >= 2
    tool_names = [l["tool_called"] for l in logs]
    assert any("start_irrigation" in t for t in tool_names)
    assert any("check_irrigation_requirement" in t for t in tool_names)


def test_tool_rest_endpoints():
    with TestClient(app) as client:
        # Water tank
        resp = client.get("/api/tools/water-tank")
        assert resp.status_code == 200
        assert resp.json()["current_level_pct"] > 0


        # Soil moisture
        resp = client.get("/api/tools/soil-moisture?field_name=Field%20A")
        assert resp.status_code == 200
        assert resp.json()["crop"] == "Tomato"

        # Weather
        resp = client.get("/api/tools/weather")
        assert resp.status_code == 200
        assert resp.json()["temperature_c"] == 31.0

        # Check irrigation
        resp = client.post("/api/tools/check-irrigation?field_name=Field%20A")
        assert resp.status_code == 200
        assert resp.json()["recommended"] is True

        # Start irrigation
        resp = client.post("/api/tools/start-irrigation?field_name=Field%20A&skip_safety=true")
        assert resp.status_code == 200
        assert resp.json()["irrigation_status"] == "ON"


        # Logs
        resp = client.get("/api/logs")
        assert resp.status_code == 200
        assert len(resp.json()) > 0
