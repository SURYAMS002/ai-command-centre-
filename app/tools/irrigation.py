from pathlib import Path
from typing import Dict, Any, Optional

from app.services.decision_engine import decision_engine
from app.services.safety import safety_validator
from app.services.automation import default_automation
from app.services.logging_service import log_operation

def check_irrigation_requirement(field_name: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Tool: check_irrigation_requirement
    Description: Evaluates whether a specific field requires irrigation using the explainable rule-based decision engine.
    Input: field_name (str) - e.g. 'Field A', 'Field B'
    """
    try:
        result = decision_engine.evaluate(field_name, db_path=db_path)
        log_operation(
            farmer_command=f"Should I irrigate {field_name}?",
            tool_called="check_irrigation_requirement",
            tool_input={"field_name": field_name},
            tool_output=result,
            decision="IRRIGATION_RECOMMENDED" if result["recommended"] else "IRRIGATION_NOT_RECOMMENDED",
            status="SUCCESS",
            details=result["summary"],
            db_path=db_path
        )
        return result
    except Exception as e:
        error_result = {"error": str(e), "field": field_name, "recommended": False}
        log_operation(
            farmer_command=f"Should I irrigate {field_name}?",
            tool_called="check_irrigation_requirement",
            tool_input={"field_name": field_name},
            tool_output=error_result,
            status="FAILED",
            details=str(e),
            db_path=db_path
        )
        return error_result

def start_irrigation(field_name: str, skip_safety: bool = False, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Tool: start_irrigation
    Description: Triggers the automation adapter to validate safety conditions and start irrigation for the specified field.
    Input: field_name (str) - e.g. 'Field A'
    """
    try:
        res = default_automation.execute_irrigation_action(field_name, "START_IRRIGATION", skip_safety=skip_safety, db_path=db_path)
        return res
    except Exception as e:
        error_result = {"success": False, "status": "FAILED", "field": field_name, "error": str(e)}
        log_operation(
            farmer_command=f"Irrigate {field_name}",
            tool_called="start_irrigation",
            tool_input={"field_name": field_name},
            tool_output=error_result,
            action="START_IRRIGATION",
            result="FAILED",
            status="FAILED",
            details=str(e),
            db_path=db_path
        )
        return error_result

def stop_irrigation(field_name: str, skip_safety: bool = False, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Tool: stop_irrigation
    Description: Triggers the automation adapter to validate safety conditions and stop irrigation for the specified field.
    Input: field_name (str) - e.g. 'Field A'
    """
    try:
        res = default_automation.execute_irrigation_action(field_name, "STOP_IRRIGATION", skip_safety=skip_safety, db_path=db_path)
        return res
    except Exception as e:
        error_result = {"success": False, "status": "FAILED", "field": field_name, "error": str(e)}
        log_operation(
            farmer_command=f"Stop irrigation in {field_name}",
            tool_called="stop_irrigation",
            tool_input={"field_name": field_name},
            tool_output=error_result,
            action="STOP_IRRIGATION",
            result="FAILED",
            status="FAILED",
            details=str(e),
            db_path=db_path
        )
        return error_result
