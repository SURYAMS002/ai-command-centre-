import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.database.database import init_db, get_farm_status_data
from app.database.models import FarmStatusModel

client = TestClient(app)

def test_database_initialization(tmp_path: Path):
    test_db = tmp_path / "test_afocc.db"
    seed_json = Path(__file__).resolve().parent.parent / "data" / "farm_data.json"
    
    # Initialize DB in temporary directory
    init_db(db_path=test_db, seed_path=seed_json)
    
    # Verify state can be queried
    status_data = get_farm_status_data(db_path=test_db)
    
    assert isinstance(status_data, FarmStatusModel)
    assert status_data.farm.name == "Demo Farm"
    assert status_data.water_tank.capacity_litres == 5000
    assert status_data.water_tank.current_level_pct == 72.0
    assert len(status_data.fields) == 2
    assert status_data.fields[0].name == "Field A"
    assert status_data.fields[0].soil_moisture_pct == 24.0
    assert status_data.fields[1].name == "Field B"
    assert status_data.fields[1].soil_moisture_pct == 48.0
    assert status_data.weather.temperature_c == 31.0
    assert status_data.weather.rain_probability_pct == 15.0

def test_root_endpoint():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert data["phase"] in [1, 2, 3, 4]




def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["farm_name"] == "Demo Farm"

def test_farm_status_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/farm/status")
        assert response.status_code == 200
        data = response.json()
        assert "farm" in data
        assert "water_tank" in data
        assert "fields" in data
        assert "weather" in data
        assert data["farm"]["name"] == "Demo Farm"
        assert data["water_tank"]["current_level_pct"] > 0



