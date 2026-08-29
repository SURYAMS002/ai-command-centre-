from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.database.database import get_connection

class DecisionEngineConfig(BaseModel):
    soil_moisture_threshold: float = 30.0
    min_tank_level_pct: float = 20.0
    rain_probability_threshold: float = 60.0

class IrrigationDecisionEngine:
    """
    Explainable Rule-Based Irrigation Decision Engine.
    Evaluates irrigation requirement based on configurable threshold rules over farm sensor state.
    """

    def __init__(self, config: Optional[DecisionEngineConfig] = None):
        self.config = config or DecisionEngineConfig()

    def evaluate(self, field_name: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # 1. Check Field State
        cursor.execute("SELECT * FROM fields WHERE LOWER(name) = LOWER(?);", (field_name,))
        field_row = cursor.fetchone()
        if not field_row:
            conn.close()
            raise ValueError(f"Field '{field_name}' does not exist in the farm database.")

        field = dict(field_row)

        # 2. Check Water Tank State
        cursor.execute("SELECT * FROM water_tank WHERE farm_id = 1 LIMIT 1;")
        tank_row = cursor.fetchone()
        if not tank_row:
            conn.close()
            raise ValueError("Water tank information is not available in the database.")
        tank = dict(tank_row)

        # 3. Check Weather State
        cursor.execute("SELECT * FROM weather WHERE farm_id = 1 LIMIT 1;")
        weather_row = cursor.fetchone()
        if not weather_row:
            conn.close()
            raise ValueError("Weather information is not available in the database.")
        weather = dict(weather_row)

        conn.close()

        # Evaluate rules
        soil_moisture = field["soil_moisture_pct"]
        tank_level = tank["current_level_pct"]
        rain_prob = weather["rain_probability_pct"]

        soil_condition_met = soil_moisture < self.config.soil_moisture_threshold
        tank_condition_met = tank_level > self.config.min_tank_level_pct
        rain_condition_met = rain_prob < self.config.rain_probability_threshold

        recommended = soil_condition_met and tank_condition_met and rain_condition_met

        # Build explainable natural language rationale
        reasons = []
        if not soil_condition_met:
            reasons.append(f"soil moisture is sufficient ({soil_moisture:.1f}% >= threshold {self.config.soil_moisture_threshold:.1f}%)")
        else:
            reasons.append(f"soil moisture is low ({soil_moisture:.1f}% < threshold {self.config.soil_moisture_threshold:.1f}%)")

        if not tank_condition_met:
            reasons.append(f"water tank level is critically low ({tank_level:.1f}% <= minimum {self.config.min_tank_level_pct:.1f}%)")
        else:
            reasons.append(f"water tank has sufficient capacity ({tank_level:.1f}% > minimum {self.config.min_tank_level_pct:.1f}%)")

        if not rain_condition_met:
            reasons.append(f"rain is expected soon ({rain_prob:.1f}% >= threshold {self.config.rain_probability_threshold:.1f}%)")
        else:
            reasons.append(f"rainfall probability is low ({rain_prob:.1f}% < threshold {self.config.rain_probability_threshold:.1f}%)")

        if recommended:
            summary = (
                f"Irrigation IS RECOMMENDED for {field['name']}. "
                f"Reason: Soil moisture is low ({soil_moisture:.1f}%), tank level is adequate ({tank_level:.1f}%), "
                f"and rainfall probability is low ({rain_prob:.1f}%)."
            )
        else:
            summary = f"Irrigation IS NOT RECOMMENDED for {field['name']}. Reason: " + "; ".join(reasons) + "."

        return {
            "field": field["name"],
            "crop": field["crop"],
            "recommended": recommended,
            "summary": summary,
            "metrics": {
                "soil_moisture_pct": soil_moisture,
                "soil_moisture_threshold_pct": self.config.soil_moisture_threshold,
                "soil_condition_met": soil_condition_met,
                "tank_level_pct": tank_level,
                "min_tank_level_pct": self.config.min_tank_level_pct,
                "tank_condition_met": tank_condition_met,
                "rain_probability_pct": rain_prob,
                "rain_probability_threshold_pct": self.config.rain_probability_threshold,
                "rain_condition_met": rain_condition_met,
                "current_irrigation_status": field["irrigation_status"]
            }
        }

# Global default instance
decision_engine = IrrigationDecisionEngine()
