import os
import json
import sqlite3
import pandas as pd
import streamlit as st
from pathlib import Path

from app.config import settings
from app.database.database import get_farm_status_data, get_connection, init_db
from app.agent.agent import default_agent
from app.services.safety import safety_validator

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="AFOCC - AI Farm Operations Command Center",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Database if not already created
init_db()

# Custom CSS Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #2E7D32;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #555555;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F1F8E9;
        border-left: 5px solid #4CAF50;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-on {
        color: #2E7D32;
        font-weight: bold;
    }
    .status-off {
        color: #C62828;
        font-weight: bold;
    }
    .stButton>button {
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

# --- HEADER SECTION ---
st.markdown("<div class='main-header'>🌾 AI FARM OPERATIONS COMMAND CENTER (AFOCC)</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Natural-Language Operational Control, Rule-Based Reasoning, Safety Validation & Automation</div>", unsafe_allow_html=True)

# --- LIVE FARM TELEMETRY DASHBOARD ---
try:
    farm_status = get_farm_status_data()
    farm = farm_status.farm
    tank = farm_status.water_tank
    fields = farm_status.fields
    weather = farm_status.weather

    field_a = next((f for f in fields if f.name == "Field A"), fields[0])
    field_b = next((f for f in fields if f.name == "Field B"), fields[1] if len(fields) > 1 else fields[0])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="🛢 Water Tank",
            value=f"{tank.current_level_pct}%",
            delta=f"Vol: {round((tank.current_level_pct/100)*tank.capacity_litres, 0)}L / {tank.capacity_litres}L"
        )
        pump_color = "🟢 ON" if tank.pump_status == "ON" else "🔴 OFF"
        st.caption(f"Pump Status: **{pump_color}**")

    with col2:
        st.metric(
            label=f"🌱 {field_a.name} ({field_a.crop})",
            value=f"{field_a.soil_moisture_pct}%",
            delta=f"Thresh: {field_a.optimal_moisture_threshold_pct}% ({field_a.soil_type} Soil)"
        )
        status_a = "🟢 Irrigation ON" if field_a.irrigation_status == "ON" else "⚪ Irrigation OFF"
        st.caption(f"Status: **{status_a}** | Stage: {field_a.growth_stage}")

    with col3:
        st.metric(
            label=f"🌾 {field_b.name} ({field_b.crop})",
            value=f"{field_b.soil_moisture_pct}%",
            delta=f"Thresh: {field_b.optimal_moisture_threshold_pct}% ({field_b.soil_type} Soil)"
        )
        status_b = "🟢 Irrigation ON" if field_b.irrigation_status == "ON" else "⚪ Irrigation OFF"
        st.caption(f"Status: **{status_b}** | Stage: {field_b.growth_stage}")

    with col4:
        st.metric(
            label="☀️ Weather Forecast",
            value=f"{weather.temperature_c}°C",
            delta=f"Rain Prob: {weather.rain_probability_pct}%"
        )
        st.caption(f"Humidity: {weather.humidity_pct}% | Sector: {farm.location}")

    # --- AGRONOMIC SOIL-CROP PARAMETER IMPUTATION PANEL ---
    with st.expander("🌾 Dynamic Soil-Crop Agronomic Parameter Imputation Panel (Review 2 Feedback)", expanded=False):
        st.markdown("##### Dynamic FAO-56 Soil Classification & Crop Stage Imputation")
        ag_col1, ag_col2 = st.columns(2)

        from app.tools.agronomic_tools import update_field_agronomic_profile

        with ag_col1:
            st.markdown(f"**{field_a.name} Profile Configuration:**")
            a_soil = st.selectbox("Soil Type (Field A)", ["Loamy", "Clay", "Sandy", "Silt", "Peat", "Saline"], index=["Loamy", "Clay", "Sandy", "Silt", "Peat", "Saline"].index(field_a.soil_type) if field_a.soil_type in ["Loamy", "Clay", "Sandy", "Silt", "Peat", "Saline"] else 0, key="a_soil")
            a_crop = st.selectbox("Crop Type (Field A)", ["Tomato", "Wheat", "Rice", "Cotton", "Maize", "Sugarcane"], index=["Tomato", "Wheat", "Rice", "Cotton", "Maize", "Sugarcane"].index(field_a.crop) if field_a.crop in ["Tomato", "Wheat", "Rice", "Cotton", "Maize", "Sugarcane"] else 0, key="a_crop")
            a_stage = st.selectbox("Growth Stage (Field A)", ["Initial/Vegetative", "Flowering", "Yield Formation", "Maturity"], index=["Initial/Vegetative", "Flowering", "Yield Formation", "Maturity"].index(field_a.growth_stage) if field_a.growth_stage in ["Initial/Vegetative", "Flowering", "Yield Formation", "Maturity"] else 1, key="a_stage")

            if (a_soil != field_a.soil_type) or (a_crop != field_a.crop) or (a_stage != field_a.growth_stage):
                update_field_agronomic_profile(field_a.name, soil_type=a_soil, crop=a_crop, growth_stage=a_stage)
                st.success(f"Imputed new dynamic parameters for {field_a.name}!")
                st.rerun()

            st.info(f"**Imputed Thresholds:** Wilting Point {field_a.wilting_point_pct}% | Field Capacity {field_a.field_capacity_pct}% | Optimal Trigger: **{field_a.optimal_moisture_threshold_pct}%**")

        with ag_col2:
            st.markdown(f"**{field_b.name} Profile Configuration:**")
            b_soil = st.selectbox("Soil Type (Field B)", ["Loamy", "Clay", "Sandy", "Silt", "Peat", "Saline"], index=["Loamy", "Clay", "Sandy", "Silt", "Peat", "Saline"].index(field_b.soil_type) if field_b.soil_type in ["Loamy", "Clay", "Sandy", "Silt", "Peat", "Saline"] else 1, key="b_soil")
            b_crop = st.selectbox("Crop Type (Field B)", ["Tomato", "Wheat", "Rice", "Cotton", "Maize", "Sugarcane"], index=["Tomato", "Wheat", "Rice", "Cotton", "Maize", "Sugarcane"].index(field_b.crop) if field_b.crop in ["Tomato", "Wheat", "Rice", "Cotton", "Maize", "Sugarcane"] else 2, key="b_crop")
            b_stage = st.selectbox("Growth Stage (Field B)", ["Initial/Vegetative", "Flowering", "Yield Formation", "Maturity"], index=["Initial/Vegetative", "Flowering", "Yield Formation", "Maturity"].index(field_b.growth_stage) if field_b.growth_stage in ["Initial/Vegetative", "Flowering", "Yield Formation", "Maturity"] else 0, key="b_stage")

            if (b_soil != field_b.soil_type) or (b_crop != field_b.crop) or (b_stage != field_b.growth_stage):
                update_field_agronomic_profile(field_b.name, soil_type=b_soil, crop=b_crop, growth_stage=b_stage)
                st.success(f"Imputed new dynamic parameters for {field_b.name}!")
                st.rerun()

            st.info(f"**Imputed Thresholds:** Wilting Point {field_b.wilting_point_pct}% | Field Capacity {field_b.field_capacity_pct}% | Optimal Trigger: **{field_b.optimal_moisture_threshold_pct}%**")

except Exception as e:
    st.error(f"Failed to load live farm telemetry: {e}")

st.markdown("---")

# --- MAIN LAYOUT: CHAT & COMMAND CENTER ---
col_chat, col_sidebar_info = st.columns([3, 2])

with col_chat:
    st.subheader("💬 Farmer Natural-Language Console")

    # Quick Action Preset Buttons
    st.markdown("**Quick Commands:**")
    q_col1, q_col2, q_col3, q_col4 = st.columns(4)
    quick_cmd = None
    with q_col1:
        if st.button("📊 Farm Status"):
            quick_cmd = "Give me the farm status."
    with q_col2:
        if st.button("❓ Should Irrigate Field A?"):
            quick_cmd = "Should I irrigate Field A?"
    with q_col3:
        if st.button("🚰 Irrigate Field A"):
            quick_cmd = "Irrigate Field A."
    with q_col4:
        if st.button("⏹ Stop Irrigation"):
            quick_cmd = "Stop irrigation."

    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "tools_called" in msg and msg["tools_called"]:
                with st.expander("🛠 Executed Tools & Technical Rationale"):
                    for t in msg["tools_called"]:
                        st.json(t)

    # Process Input from Chat Input or Quick Command
    user_input = st.chat_input("Enter farm command (e.g., 'Check water tank', 'Irrigate Field A')...")
    command_to_process = user_input or quick_cmd

    if command_to_process:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": command_to_process})
        with st.chat_message("user"):
            st.write(command_to_process)

        # Execute Agent Command
        with st.spinner("AFOCC Agent reasoning & executing tools..."):
            agent_res = default_agent.run_command(
                command_to_process,
                pending_action=st.session_state.pending_action
            )

        # Clear pending action if user input was processed
        st.session_state.pending_action = agent_res.get("pending_action")

        # Save assistant message
        asst_msg = {
            "role": "assistant",
            "content": agent_res["response"],
            "tools_called": agent_res.get("tools_called", []),
            "status": agent_res.get("status")
        }
        st.session_state.messages.append(asst_msg)

        # Rerun to update UI
        st.rerun()

    # --- PENDING CONFIRMATION PROMPT DIALOGUE ---
    if st.session_state.pending_action:
        st.warning("⚠️ **SAFETY CONFIRMATION REQUIRED**")
        p_action = st.session_state.pending_action
        field = p_action.get("field_name")
        act = p_action.get("action")

        c_col1, c_col2 = st.columns(2)
        with c_col1:
            if st.button("✅ Confirm & Start Irrigation", type="primary"):
                with st.spinner("Executing Safety & Automation Adapter..."):
                    agent_res = default_agent.run_command(
                        "Yes",
                        pending_action=st.session_state.pending_action
                    )
                st.session_state.pending_action = None
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": agent_res["response"],
                    "tools_called": agent_res.get("tools_called", [])
                })
                st.rerun()

        with c_col2:
            if st.button("❌ Cancel Operation"):
                st.session_state.pending_action = None
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Operation cancelled by farmer.",
                    "tools_called": []
                })
                st.rerun()

with col_sidebar_info:
    st.subheader("⚙️ System Operations & Decision Rules")

    st.info("""
    **AFOCC Decision Engine Rules:**
    - 💧 **Soil Moisture Threshold:** < 30%
    - 🛢 **Minimum Water Reserve:** > 20% (Blocked if ≤ 10%)
    - 🌧 **Rainfall Threshold:** < 60%
    
    *Irrigation is recommended ONLY when all safety conditions are met.*
    """)

    # --- SIMULATED SENSOR OVERRIDE CONTROLS ---
    st.markdown("### 🎛 Simulated Sensor Overrides")
    st.caption("Adjust simulated sensors to test Safety Layer constraint blocks.")

    conn = get_connection()
    cursor = conn.cursor()

    # Tank Level Slider
    cursor.execute("SELECT current_level_pct FROM water_tank WHERE farm_id = 1;")
    curr_tank = cursor.fetchone()["current_level_pct"]
    new_tank = st.slider("Water Tank Level (%)", 0.0, 100.0, float(curr_tank), step=5.0)

    # Soil Moisture Slider Field A
    cursor.execute("SELECT soil_moisture_pct FROM fields WHERE LOWER(name) = 'field a';")
    curr_soil_a = cursor.fetchone()["soil_moisture_pct"]
    new_soil_a = st.slider("Field A Soil Moisture (%)", 0.0, 100.0, float(curr_soil_a), step=1.0)

    if st.button("💾 Apply Sensor Overrides"):
        cursor.execute("UPDATE water_tank SET current_level_pct = ? WHERE farm_id = 1;", (new_tank,))
        cursor.execute("UPDATE fields SET soil_moisture_pct = ? WHERE LOWER(name) = 'field a';", (new_soil_a,))
        conn.commit()
        conn.close()
        st.success("Simulated sensor state updated in SQLite DB!")
        st.rerun()
    else:
        conn.close()

# --- BOTTOM SECTION: REAL-TIME AUDIT LOGS TABLE ---
st.markdown("---")
st.subheader("📋 Real-Time Operation Audit Logs")

try:
    conn = get_connection()
    df_logs = pd.read_sql_query("SELECT id, timestamp, farmer_command, tool_called, action, status, details FROM operation_logs ORDER BY id DESC LIMIT 15;", conn)
    conn.close()

    if not df_logs.empty:
        st.dataframe(
            df_logs,
            column_config={
                "id": "Log ID",
                "timestamp": "Timestamp",
                "farmer_command": "Farmer Command",
                "tool_called": "Tool Executed",
                "action": "Action",
                "status": "Status",
                "details": "Details & Rationale"
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.caption("No operations logged yet.")

except Exception as e:
    st.error(f"Failed to load audit logs: {e}")
