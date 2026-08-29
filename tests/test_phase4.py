import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.database.database import init_db, get_connection
from app.services.safety import safety_validator
from app.services.automation import default_automation
from app.agent.agent import default_agent

@pytest.fixture
def setup_test_db(tmp_path: Path):
    test_db = tmp_path / "test_afocc_p4.db"
    seed_json = Path(__file__).resolve().parent.parent / "data" / "farm_data.json"
    init_db(db_path=test_db, seed_path=seed_json)
    return test_db

def test_invalid_field_safety_check(setup_test_db: Path):
    val = safety_validator.validate_irrigation_request("Field X", "START_IRRIGATION", db_path=setup_test_db)
    assert val.valid is False
    assert val.status == "BLOCKED"
    assert "does not exist" in val.message

def test_low_water_tank_safety_check(setup_test_db: Path):
    # Artificially set water tank level to 10%
    conn = get_connection(setup_test_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE water_tank SET current_level_pct = 10.0 WHERE farm_id = 1;")
    conn.commit()
    conn.close()

    val = safety_validator.validate_irrigation_request("Field A", "START_IRRIGATION", db_path=setup_test_db)
    assert val.valid is False
    assert val.status == "BLOCKED"
    assert "critically low" in val.message or "blocked" in val.message.lower()

def test_duplicate_operation_prevention(setup_test_db: Path):
    # Set Field A irrigation status to ON
    conn = get_connection(setup_test_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE fields SET irrigation_status = 'ON' WHERE LOWER(name) = 'field a';")
    conn.commit()
    conn.close()

    val = safety_validator.validate_irrigation_request("Field A", "START_IRRIGATION", db_path=setup_test_db)
    assert val.valid is False
    assert val.status == "BLOCKED"
    assert "already ON" in val.message

def test_confirmation_workflow(setup_test_db: Path):
    # Step 1: Initial Command -> PENDING_CONFIRMATION
    res1 = default_agent.run_command("Irrigate Field A.", db_path=setup_test_db)
    assert res1["status"] == "PENDING_CONFIRMATION"
    assert "pending_action" in res1
    assert res1["pending_action"]["field_name"] == "Field A"
    assert res1["pending_action"]["action"] == "START_IRRIGATION"

    # Step 2: Confirmation "Yes" -> SUCCESS & State Mutated
    pending = res1["pending_action"]
    res2 = default_agent.run_command("Yes", pending_action=pending, db_path=setup_test_db)
    assert res2["status"] == "SUCCESS"
    assert "started successfully" in res2["response"]

    # Verify DB state changed to ON
    conn = get_connection(setup_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT irrigation_status FROM fields WHERE LOWER(name) = 'field a';")
    status_row = cursor.fetchone()
    conn.close()
    assert status_row["irrigation_status"] == "ON"

def test_safety_api_routes(setup_test_db: Path):
    with TestClient(app) as client:
        # Reset Field A to OFF
        conn = get_connection(setup_test_db)
        cursor = conn.cursor()
        cursor.execute("UPDATE fields SET irrigation_status = 'OFF' WHERE LOWER(name) = 'field a';")
        cursor.execute("UPDATE water_tank SET current_level_pct = 72.0 WHERE farm_id = 1;")
        conn.commit()
        conn.close()

        val = safety_validator.validate_irrigation_request("Field A", "START_IRRIGATION", db_path=setup_test_db)
        assert val.status == "PENDING_CONFIRMATION"

        # Validate invalid field
        val2 = safety_validator.validate_irrigation_request("Field Unknown", "START_IRRIGATION", db_path=setup_test_db)
        assert val2.status == "BLOCKED"

