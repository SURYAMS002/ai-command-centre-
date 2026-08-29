import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database.database import init_db
from app.agent.agent import AFOCCAgent

@pytest.fixture
def setup_test_db(tmp_path: Path):
    test_db = tmp_path / "test_afocc_p3.db"
    seed_json = Path(__file__).resolve().parent.parent / "data" / "farm_data.json"
    init_db(db_path=test_db, seed_path=seed_json)
    return test_db

@pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OPENAI_API_KEY required for live agent tests")
def test_agent_check_water_tank(setup_test_db: Path):
    agent = AFOCCAgent(api_key=settings.OPENAI_API_KEY)
    res = agent.run_command("Check the water tank.", db_path=setup_test_db)
    
    assert res["status"] == "SUCCESS"
    assert len(res["tools_called"]) >= 1
    assert res["tools_called"][0]["tool"] == "get_water_tank_status"
    assert "72" in res["response"] or "5000" in res["response"] or "tank" in res["response"].lower()

@pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OPENAI_API_KEY required for live agent tests")
def test_agent_check_soil_moisture(setup_test_db: Path):
    agent = AFOCCAgent(api_key=settings.OPENAI_API_KEY)
    res = agent.run_command("Check soil moisture in Field A.", db_path=setup_test_db)
    
    assert res["status"] == "SUCCESS"
    assert len(res["tools_called"]) >= 1
    tool_names = [t["tool"] for t in res["tools_called"]]
    assert "get_soil_moisture" in tool_names
    assert "24" in res["response"] or "Field A" in res["response"]

@pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OPENAI_API_KEY required for live agent tests")
def test_agent_check_weather(setup_test_db: Path):
    agent = AFOCCAgent(api_key=settings.OPENAI_API_KEY)
    res = agent.run_command("What is the weather?", db_path=setup_test_db)
    
    assert res["status"] == "SUCCESS"
    assert len(res["tools_called"]) >= 1
    tool_names = [t["tool"] for t in res["tools_called"]]
    assert "get_weather" in tool_names

@pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OPENAI_API_KEY required for live agent tests")
def test_agent_should_irrigate(setup_test_db: Path):
    agent = AFOCCAgent(api_key=settings.OPENAI_API_KEY)
    res = agent.run_command("Should I irrigate Field A?", db_path=setup_test_db)
    
    assert res["status"] == "SUCCESS"
    assert len(res["tools_called"]) >= 1
    tool_names = [t["tool"] for t in res["tools_called"]]
    assert "check_irrigation_requirement" in tool_names or "get_soil_moisture" in tool_names

@pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OPENAI_API_KEY required for live agent tests")
def test_agent_start_irrigation(setup_test_db: Path):
    agent = AFOCCAgent(api_key=settings.OPENAI_API_KEY)
    res = agent.run_command("Irrigate Field A.", db_path=setup_test_db)
    
    assert res["status"] in ["SUCCESS", "PENDING_CONFIRMATION"]
    assert len(res["tools_called"]) >= 1 or "pending_action" in res


@pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OPENAI_API_KEY required for live agent tests")
def test_agent_api_endpoint():
    with TestClient(app) as client:
        resp = client.post("/api/agent/command", json={"command": "Give me the current farm status."})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert len(data["tools_called"]) >= 1
