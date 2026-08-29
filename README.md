# AI FARM OPERATIONS COMMAND CENTER (AFOCC)

**Version:** 1.0.0 (Phases 1-4 Complete + Streamlit Command Center UI)  
**Repository:** [https://github.com/SURYAMS002/ai-command-centre-](https://github.com/SURYAMS002/ai-command-centre-)

---

## 1. System Overview & Core Concept

**AFOCC** is an **AI-Agent-Based Farm Operations Command Centre**. It demonstrates how a single, unified natural-language AI agent orchestrates heterogeneous farm telemetry, rule-based decision engines, safety validation mechanisms, and automated field operations.

```
NATURAL LANGUAGE COMMAND
          ↓
       AI AGENT
          ↓
     TOOL SELECTION
          ↓
  FARM INFORMATION / DECISION
          ↓
    SAFETY LAYER
          ↓
     AUTOMATION
          ↓
    FARM OPERATION
          ↓
   FEEDBACK / LOGGING
```

---

## 2. Streamlit UI & Core Features

Launch the interactive web UI:

```powershell
streamlit run streamlit_app.py
```

URL: [http://127.0.0.1:8501](http://127.0.0.1:8501)

### Key UI Capabilities:
1. **Live Farm Telemetry Dashboard:** Top metric cards displaying Water Tank (capacity, volume, level %, pump status), Field A & B (crop, area, soil moisture %, irrigation status), and Weather (temp, humidity, rain probability).
2. **Natural-Language Agent Console:** Interactive chat interface + preset one-click demo buttons (*"Give me the farm status"*, *"Should I irrigate Field A?"*, *"Irrigate Field A"*, *"Stop irrigation"*).
3. **Safety Confirmation UI:** Renders **"✅ Confirm Start Irrigation"** and **"❌ Cancel"** buttons directly inside chat when an operation is pending confirmation.
4. **Executed Tools & Rationale Inspector:** Technical drawer displaying exact tool names, arguments, and JSON outputs.
5. **Simulated Sensor Override Panel (Sidebar):** Sliders to adjust soil moisture and water tank level dynamically to demonstrate Safety Layer blocks (e.g. tank level $\le 10\%$).
6. **Real-Time Operation Audit Logs:** Table displaying recorded commands, tool executions, decisions, results, and timestamps from SQLite `operation_logs`.

---

## 3. Project Architecture

```
afocc/
│
├── streamlit_app.py             # Streamlit Command Center Web UI
├── app/
│   ├── main.py                  # FastAPI application entrypoint
│   ├── config.py                # Configuration manager
│   ├── agent/                   # OpenAI AI Agent Core & Tool Dispatch
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── schemas.py
│   ├── tools/                   # Farm Tool implementations
│   │   ├── water.py
│   │   ├── soil.py
│   │   ├── weather.py
│   │   ├── irrigation.py
│   │   └── farm_status.py
│   ├── services/                # Decision Engine, Safety Layer, Automation & Audit Logging
│   │   ├── decision_engine.py
│   │   ├── safety.py
│   │   ├── automation.py
│   │   ├── actuator.py
│   │   └── logging_service.py
│   ├── database/                # SQLite State Management
│   │   ├── database.py
│   │   └── models.py
│   └── api/                     # REST API Routes
│       └── routes.py
├── data/
│   ├── farm_data.json           # Initial simulated farm state
│   └── afocc.db                 # SQLite database (auto-seeded)
├── tests/                       # Pytest Automated Test Suite (23 tests)
│   ├── test_phase1.py
│   ├── test_phase2.py
│   ├── test_phase3.py
│   └── test_phase4.py
├── .env.example                 # Configuration template
├── requirements.txt             # Project dependencies
└── README.md                    # System documentation
```

---

## 4. Execution & Testing

### Running the Streamlit UI
```powershell
.\.venv\Scripts\streamlit.exe run streamlit_app.py
```

### Running the FastAPI Backend Server
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Running Full Automated Test Suite (23 Tests)
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
