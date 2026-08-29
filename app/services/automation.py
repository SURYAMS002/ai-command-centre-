from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

from app.services.safety import safety_validator
from app.services.actuator import default_actuator
from app.services.logging_service import log_operation

class AutomationAdapter(ABC):
    """
    Abstract Automation Adapter interface.
    Connects the Safety Layer to the actuator layer (local mock or remote n8n webhook in Phase 5).
    """
    @abstractmethod
    def execute_irrigation_action(
        self,
        field_name: str,
        action: str,  # "START_IRRIGATION" | "STOP_IRRIGATION"
        skip_safety: bool = False,
        db_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        pass

class MockAutomationAdapter(AutomationAdapter):
    """
    Local Mock Automation Adapter enforcing safety validation before calling actuator state mutation.
    """

    def execute_irrigation_action(
        self,
        field_name: str,
        action: str,
        skip_safety: bool = False,
        db_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        action_upper = action.upper()

        if not skip_safety:
            validation = safety_validator.validate_irrigation_request(field_name, action_upper, db_path=db_path)
            if not validation.valid:
                log_operation(
                    farmer_command=f"{action_upper} {field_name}",
                    tool_called=f"automation_adapter:{action_upper.lower()}",
                    tool_input={"field_name": field_name, "action": action_upper},
                    tool_output={"valid": False, "status": validation.status, "message": validation.message},
                    action=action_upper,
                    result="BLOCKED",
                    status="BLOCKED",
                    details=validation.message,
                    db_path=db_path
                )
                return {
                    "success": False,
                    "status": "BLOCKED",
                    "field": field_name,
                    "action": action_upper,
                    "message": validation.message
                }
            elif validation.status == "PENDING_CONFIRMATION":
                return {
                    "success": True,
                    "status": "PENDING_CONFIRMATION",
                    "field": field_name,
                    "action": action_upper,
                    "message": validation.message
                }

        # Execute physical/simulated actuator mutation
        if action_upper == "START_IRRIGATION":
            actuator_res = default_actuator.start_irrigation(field_name, db_path=db_path)
        elif action_upper == "STOP_IRRIGATION":
            actuator_res = default_actuator.stop_irrigation(field_name, db_path=db_path)
        else:
            raise ValueError(f"Unsupported action '{action}'")

        log_operation(
            farmer_command=f"{action_upper} {field_name}",
            tool_called=f"automation_adapter:{action_upper.lower()}",
            tool_input={"field_name": field_name, "action": action_upper},
            tool_output=actuator_res,
            action=action_upper,
            result="SUCCESS",
            status="SUCCESS",
            details=actuator_res["message"],
            db_path=db_path
        )

        return {
            "success": True,
            "status": "SUCCESS",
            "field": actuator_res["field"],
            "action": action_upper,
            "changed": actuator_res.get("changed", True),
            "irrigation_status": actuator_res["irrigation_status"],
            "message": actuator_res["message"]
        }

# Global default instance
default_automation = MockAutomationAdapter()
