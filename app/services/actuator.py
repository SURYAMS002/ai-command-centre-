from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from app.database.database import get_connection

class ActuatorInterface(ABC):
    """
    Abstract interface for field actuators and pump controllers.
    Allows replacing MockActuator with physical hardware (FPGA, ESP32, PLC) in future phases.
    """
    @abstractmethod
    def start_irrigation(self, field_name: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def stop_irrigation(self, field_name: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def set_water_pump(self, status: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
        pass

class MockActuator(ActuatorInterface):
    """
    Simulated actuator modifying SQLite database state for fields and water pumps.
    """

    def start_irrigation(self, field_name: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM fields WHERE LOWER(name) = LOWER(?);", (field_name,))
        field = cursor.fetchone()

        if not field:
            conn.close()
            raise ValueError(f"Field '{field_name}' does not exist in the farm database.")

        current_status = field["irrigation_status"]
        exact_field_name = field["name"]

        if current_status == "ON":
            conn.close()
            return {
                "success": True,
                "field": exact_field_name,
                "action": "START_IRRIGATION",
                "irrigation_status": "ON",
                "changed": False,
                "message": f"Irrigation for {exact_field_name} is already ON."
            }

        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE fields SET irrigation_status = 'ON', updated_at = ? WHERE id = ?;",
            (now, field["id"])
        )
        conn.commit()
        conn.close()

        return {
            "success": True,
            "field": exact_field_name,
            "action": "START_IRRIGATION",
            "irrigation_status": "ON",
            "changed": True,
            "message": f"Irrigation for {exact_field_name} has been successfully started (ON)."
        }

    def stop_irrigation(self, field_name: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM fields WHERE LOWER(name) = LOWER(?);", (field_name,))
        field = cursor.fetchone()

        if not field:
            conn.close()
            raise ValueError(f"Field '{field_name}' does not exist in the farm database.")

        current_status = field["irrigation_status"]
        exact_field_name = field["name"]

        if current_status == "OFF":
            conn.close()
            return {
                "success": True,
                "field": exact_field_name,
                "action": "STOP_IRRIGATION",
                "irrigation_status": "OFF",
                "changed": False,
                "message": f"Irrigation for {exact_field_name} is already OFF."
            }

        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE fields SET irrigation_status = 'OFF', updated_at = ? WHERE id = ?;",
            (now, field["id"])
        )
        conn.commit()
        conn.close()

        return {
            "success": True,
            "field": exact_field_name,
            "action": "STOP_IRRIGATION",
            "irrigation_status": "OFF",
            "changed": True,
            "message": f"Irrigation for {exact_field_name} has been successfully stopped (OFF)."
        }

    def set_water_pump(self, status: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
        status_upper = status.upper()
        if status_upper not in ["ON", "OFF"]:
            raise ValueError("Pump status must be 'ON' or 'OFF'.")

        conn = get_connection(db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE water_tank SET pump_status = ?, updated_at = ? WHERE farm_id = 1;",
            (status_upper, now)
        )
        conn.commit()
        conn.close()

        return {
            "success": True,
            "pump_status": status_upper,
            "message": f"Water pump status set to {status_upper}."
        }

# Default global actuator instance
default_actuator = MockActuator()
