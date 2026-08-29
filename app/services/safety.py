from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.database.database import get_connection

class SafetyValidationResult(BaseModel):
    valid: bool
    status: str  # "ALLOWED" | "BLOCKED" | "PENDING_CONFIRMATION"
    message: str
    requires_confirmation: bool = False
    field_name: Optional[str] = None
    action: str
    metrics: Optional[Dict[str, Any]] = None

class SafetyValidator:
    """
    Safety Validation Layer.
    Ensures that no physical actuator command is executed without passing strict safety constraints:
    1. Field existence verification.
    2. Water tank capacity & minimum reserve check (tank > 20%, blocked if <= 10%).
    3. Duplicate operation prevention (prevent starting if already ON, stopping if already OFF).
    4. Farmer confirmation requirement.
    """

    def validate_irrigation_request(
        self,
        field_name: str,
        action: str,  # "START_IRRIGATION" | "STOP_IRRIGATION"
        db_path: Optional[Path] = None
    ) -> SafetyValidationResult:
        action_upper = action.upper()
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # 1. Field Existence Check
        cursor.execute("SELECT * FROM fields WHERE LOWER(name) = LOWER(?);", (field_name.strip(),))
        field_row = cursor.fetchone()
        if not field_row:
            conn.close()
            return SafetyValidationResult(
                valid=False,
                status="BLOCKED",
                message=f"Safety Violation: Field '{field_name}' does not exist in farm database.",
                requires_confirmation=False,
                field_name=field_name,
                action=action_upper
            )

        field = dict(field_row)
        exact_field_name = field["name"]

        # 2. Water Tank Reserves Check (for START_IRRIGATION)
        cursor.execute("SELECT * FROM water_tank WHERE farm_id = 1 LIMIT 1;")
        tank_row = cursor.fetchone()
        if not tank_row:
            conn.close()
            return SafetyValidationResult(
                valid=False,
                status="BLOCKED",
                message="Safety Violation: Water tank status record unavailable.",
                requires_confirmation=False,
                field_name=exact_field_name,
                action=action_upper
            )

        tank = dict(tank_row)
        tank_level = tank["current_level_pct"]

        if action_upper == "START_IRRIGATION":
            if tank_level <= 10.0:
                conn.close()
                return SafetyValidationResult(
                    valid=False,
                    status="BLOCKED",
                    message=f"Safety Hazard: Water tank level is critically low ({tank_level:.1f}% <= 10.0%). Irrigation blocked to prevent pump damage.",
                    requires_confirmation=False,
                    field_name=exact_field_name,
                    action=action_upper,
                    metrics={"tank_level_pct": tank_level, "soil_moisture_pct": field["soil_moisture_pct"]}
                )
            elif tank_level < 20.0:
                conn.close()
                return SafetyValidationResult(
                    valid=False,
                    status="BLOCKED",
                    message=f"Safety Restraint: Water tank level is low ({tank_level:.1f}% < 20.0%). Insufficient water reserve for field irrigation.",
                    requires_confirmation=False,
                    field_name=exact_field_name,
                    action=action_upper,
                    metrics={"tank_level_pct": tank_level, "soil_moisture_pct": field["soil_moisture_pct"]}
                )

        # 3. Duplicate Operation Prevention
        current_irrigation_status = field["irrigation_status"]
        if action_upper == "START_IRRIGATION" and current_irrigation_status == "ON":
            conn.close()
            return SafetyValidationResult(
                valid=False,
                status="BLOCKED",
                message=f"Operation Prevented: Irrigation for {exact_field_name} is already ON.",
                requires_confirmation=False,
                field_name=exact_field_name,
                action=action_upper,
                metrics={"current_irrigation_status": current_irrigation_status}
            )
        elif action_upper == "STOP_IRRIGATION" and current_irrigation_status == "OFF":
            conn.close()
            return SafetyValidationResult(
                valid=False,
                status="BLOCKED",
                message=f"Operation Prevented: Irrigation for {exact_field_name} is already OFF.",
                requires_confirmation=False,
                field_name=exact_field_name,
                action=action_upper,
                metrics={"current_irrigation_status": current_irrigation_status}
            )

        conn.close()

        # 4. Confirmation Required
        action_verb = "start" if action_upper == "START_IRRIGATION" else "stop"
        return SafetyValidationResult(
            valid=True,
            status="PENDING_CONFIRMATION",
            message=f"{exact_field_name} soil moisture is {field['soil_moisture_pct']:.1f}% and tank level is {tank_level:.1f}%. Do you want me to {action_verb} irrigation?",
            requires_confirmation=True,
            field_name=exact_field_name,
            action=action_upper,
            metrics={
                "soil_moisture_pct": field["soil_moisture_pct"],
                "tank_level_pct": tank_level,
                "current_irrigation_status": current_irrigation_status
            }
        )

# Global default instance
safety_validator = SafetyValidator()
