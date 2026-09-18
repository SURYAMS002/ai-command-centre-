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

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="🛢 Water Tank (HC-SR04 Sensor)",
            value=f"{tank.current_level_pct}%",
            delta=f"Vol: {round((tank.current_level_pct/100)*tank.capacity_litres, 0)}L / {tank.capacity_litres}L"
        )
        pump_color = "🟢 MOTOR RUNNING" if tank.pump_status == "ON" else "🔴 MOTOR STOPPED"
        st.caption(f"Pump Relay Status: **{pump_color}**")

    with col2:
        st.metric(
            label=f"🌱 Real Hardware Soil Field ({field_a.crop})",
            value=f"{field_a.soil_moisture_pct}%",
            delta=f"Optimal Target: {field_a.optimal_moisture_threshold_pct}% ({field_a.soil_type} Soil)"
        )
        status_a = "🟢 Irrigation ON" if field_a.irrigation_status == "ON" else "⚪ Irrigation OFF"
        st.caption(f"Status: **{status_a}** | Stage: {field_a.growth_stage}")

    with col3:
        st.metric(
            label="☀️ Microclimate (DHT22 Sensor)",
            value=f"{weather.temperature_c}°C",
            delta=f"Rain Prob: {weather.rain_probability_pct}%"
        )
        st.caption(f"Humidity: {weather.humidity_pct}% | Sector: {farm.location}")

    # --- AGRONOMIC SOIL-CROP PARAMETER IMPUTATION PANEL ---
    with st.expander("🌾 Dynamic Soil-Crop Agronomic Parameter Imputation Panel (Review 2 Feedback)", expanded=True):
        st.markdown("##### Dynamic FAO-56 Soil Classification & Crop Stage Imputation")

        from app.tools.agronomic_tools import update_field_agronomic_profile

        st.markdown(f"**{field_a.name} Profile Configuration:**")
        ag_col1, ag_col2, ag_col3 = st.columns(3)

        with ag_col1:
            a_soil = st.selectbox("Soil Type", ["Loamy", "Clay", "Sandy", "Silt", "Peat", "Saline"], index=["Loamy", "Clay", "Sandy", "Silt", "Peat", "Saline"].index(field_a.soil_type) if field_a.soil_type in ["Loamy", "Clay", "Sandy", "Silt", "Peat", "Saline"] else 0, key="a_soil")
        with ag_col2:
            a_crop = st.selectbox("Crop Type", ["Tomato", "Wheat", "Rice", "Cotton", "Maize", "Sugarcane"], index=["Tomato", "Wheat", "Rice", "Cotton", "Maize", "Sugarcane"].index(field_a.crop) if field_a.crop in ["Tomato", "Wheat", "Rice", "Cotton", "Maize", "Sugarcane"] else 0, key="a_crop")
        with ag_col3:
            a_stage = st.selectbox("Growth Stage", ["Initial/Vegetative", "Flowering", "Yield Formation", "Maturity"], index=["Initial/Vegetative", "Flowering", "Yield Formation", "Maturity"].index(field_a.growth_stage) if field_a.growth_stage in ["Initial/Vegetative", "Flowering", "Yield Formation", "Maturity"] else 1, key="a_stage")

        if (a_soil != field_a.soil_type) or (a_crop != field_a.crop) or (a_stage != field_a.growth_stage):
            update_field_agronomic_profile(field_a.name, soil_type=a_soil, crop=a_crop, growth_stage=a_stage)
            st.success(f"Imputed new dynamic FAO-56 parameters for {field_a.name}!")
            st.rerun()

        st.info(f"**Imputed Thresholds:** Wilting Point: **{field_a.wilting_point_pct}%** | Field Capacity: **{field_a.field_capacity_pct}%** | Optimal Target Trigger: **{field_a.optimal_moisture_threshold_pct}%**")

except Exception as e:
    st.error(f"Failed to load live farm telemetry: {e}")

st.markdown("---")

# --- MAIN LAYOUT: CHAT & COMMAND CENTER ---
# --- MULTI-PERSPECTIVE DASHBOARD NAVIGATION ---
tab_cmd, tab_water, tab_agronomic, tab_audit = st.tabs([
    "🎛 Live Command & Control",
    "📊 Past Irrigations & Water Pumped Analytics",
    "🌾 Agronomic & Soil NPK Health Monitor",
    "🤖 Farmer Queries & AI Audit Trail"
])

# ==============================================================================
# TAB 1: LIVE COMMAND & CONTROL CENTER
# ==============================================================================
with tab_cmd:
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
            if st.button("🚰 Start Irrigation"):
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
        user_input = st.chat_input("Enter farm command (e.g., 'Check water tank', 'Start irrigation')...")
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
        st.subheader("⚙️ Real-Time System Operations & Decision Rules")

        st.info(f"""
        **AFOCC Dynamic Agronomic Decision Rules:**
        - 💧 **{field_a.name} ({field_a.crop} / {field_a.soil_type}):** Irrigate if Moisture < **{field_a.optimal_moisture_threshold_pct}%** (FC: {field_a.field_capacity_pct}%, PWP: {field_a.wilting_point_pct}%)
        - 🛢 **Minimum Water Reserve:** > 10% (Safety Gate Blocked if ≤ 10%)
        - 🌧 **Rainfall Forecast Threshold:** < 60% Rain Prob
        
        *Irrigation auto-starts when moisture < threshold and auto-stops when target is reached.*
        """)


# ==============================================================================
# TAB 2: HISTORICAL IRRIGATION & WATER PUMPED ANALYTICS
# ==============================================================================
with tab_water:
    st.subheader("📊 Past Irrigated Statuses & Water Consumption Analytics")
    st.markdown("Detailed historical breakdown of irrigation pump cycles, water volumes extracted, and safety gate interventions.")

    try:
        conn = get_connection()
        df_logs_all = pd.read_sql_query("SELECT * FROM operation_logs ORDER BY id DESC;", conn)
        conn.close()

        w_col1, w_col2, w_col3, w_col4 = st.columns(4)
        total_ops = len(df_logs_all)
        irrigation_ops = len(df_logs_all[df_logs_all['action'] == 'START_IRRIGATION'])
        blocked_ops = len(df_logs_all[df_logs_all['status'] == 'BLOCKED'])
        total_water_litres = irrigation_ops * 450.0  # 450L per cycle estimate

        with w_col1:
            st.metric("💧 Total Water Pumped", f"{total_water_litres:,.0f} Litres", delta="Estimated Cumulative Volume")
        with w_col2:
            st.metric("🔄 Active Irrigation Cycles", f"{irrigation_ops} Cycles", delta=f"{total_ops} Total Commands")
        with w_col3:
            st.metric("🛡️ Safety Interventions", f"{blocked_ops} Blocked", delta="Hazardous Over-irrigations Prevented")
        with w_col4:
            st.metric("🛢 Water Tank Reserve", f"{tank.current_level_pct}%", delta=f"{round((tank.current_level_pct/100)*tank.capacity_litres, 0)}L Available")

        st.markdown("---")
        st.markdown("#### 📉 Water Volume Pumped Trend Over Operations")
        
        # Water consumption timeline chart
        if not df_logs_all.empty:
            df_water = df_logs_all.copy()
            df_water['Water_Pumped_L'] = df_water['action'].apply(lambda x: 450.0 if x == 'START_IRRIGATION' else 0.0)
            df_water['Operation_Index'] = range(len(df_water), 0, -1)
            st.bar_chart(df_water.set_index('Operation_Index')['Water_Pumped_L'], use_container_width=True)

        st.markdown("#### 📋 Logged Past Irrigation Statuses & Pump Events")
        if not df_logs_all.empty:
            st.dataframe(
                df_logs_all[['id', 'timestamp', 'farmer_command', 'action', 'status', 'details']],
                column_config={
                    "id": "Log ID",
                    "timestamp": "Timestamp",
                    "farmer_command": "Farmer Command",
                    "action": "Action Code",
                    "status": "Execution Status",
                    "details": "Technical Details & Rationale"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No past irrigation operations recorded yet.")

    except Exception as e:
        st.error(f"Failed to load historical water analytics: {e}")


# ==============================================================================
# TAB 3: AGRONOMIC & SOIL NPK HEALTH MONITOR
# ==============================================================================
with tab_agronomic:
    st.subheader("🌾 Agronomic Soil Classification & NPK Health Monitor")
    st.markdown("Real hardware field soil moisture, FAO-56 wilting point, field capacity, and nutrient adequacy metrics.")

    a_col1, a_col2 = st.columns([2, 1])
    with a_col1:
        st.markdown(f"### 📍 Real Hardware Field Health Profile ({field_a.crop})")
        st.write(f"- **Soil Classification:** {field_a.soil_type}")
        st.write(f"- **Growth Stage:** {field_a.growth_stage}")
        st.write(f"- **Current Real-Time Soil Moisture:** **{field_a.soil_moisture_pct}%**")
        st.write(f"- **FAO-56 Imputed Optimal Target:** **{field_a.optimal_moisture_threshold_pct}%**")
        st.write(f"- **Field Capacity (FC):** {field_a.field_capacity_pct}% | **Wilting Point (PWP):** {field_a.wilting_point_pct}%")
        st.write(f"- **Soil pH Level:** {field_a.ph_level}")
        st.write(f"- **NPK Balance (N-P-K):** Nitrogen: {field_a.nitrogen_ppm} ppm, Phosphorus: {field_a.phosphorus_ppm} ppm, Potassium: {field_a.potassium_ppm} ppm")

    with a_col2:
        st.markdown("#### 📊 Moisture vs FAO-56 Threshold")
        chart_data = pd.DataFrame({
            "Metric": ["Current Moisture (%)", "Optimal Target (%)", "Field Capacity (%)"],
            "Value": [field_a.soil_moisture_pct, field_a.optimal_moisture_threshold_pct, field_a.field_capacity_pct]
        }).set_index("Metric")
        st.bar_chart(chart_data)


# ==============================================================================
# TAB 4: FARMER QUERIES & AI AUDIT TRAIL
# ==============================================================================
with tab_audit:
    st.subheader("🤖 Farmer Queries & AI Agent Audit Trail")
    st.markdown("Complete record of natural-language farmer prompts, detected intent classifications, tool execution outputs, and safety verification outcomes.")

    try:
        conn = get_connection()
        df_audit = pd.read_sql_query("SELECT * FROM operation_logs ORDER BY id DESC;", conn)
        conn.close()

        if not df_audit.empty:
            # Download CSV Button
            csv = df_audit.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Complete Audit Logs (CSV)",
                data=csv,
                file_name="afocc_operation_audit_logs.csv",
                mime="text/csv"
            )

            st.markdown("#### 🔍 Searchable Operations & Queries Audit Table")
            st.dataframe(
                df_audit,
                column_config={
                    "id": "Log ID",
                    "timestamp": "Timestamp",
                    "farmer_command": "Farmer Prompt / Query",
                    "detected_intent": "Intent Classified",
                    "tool_called": "Tool Executed",
                    "action": "Action Implemented",
                    "status": "Status",
                    "details": "Technical Rationale & Details"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("No audit entries recorded yet.")

    except Exception as e:
        st.error(f"Failed to load AI audit trail: {e}")

