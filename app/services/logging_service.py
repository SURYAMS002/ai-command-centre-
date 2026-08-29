import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import settings
from app.database.database import get_connection
from app.database.models import OperationLogModel

def log_operation(
    farmer_command: str,
    status: str,  # "SUCCESS" | "FAILED" | "BLOCKED" | "PENDING_CONFIRMATION"
    detected_intent: Optional[str] = None,
    tool_called: Optional[str] = None,
    tool_input: Optional[Dict[str, Any]] = None,
    tool_output: Optional[Dict[str, Any]] = None,
    decision: Optional[str] = None,
    action: Optional[str] = None,
    result: Optional[str] = None,
    details: Optional[str] = None,
    db_path: Optional[Path] = None
) -> OperationLogModel:
    """
    Logs every operational command and tool execution into the operation_logs SQLite table for auditability.
    """
    now = datetime.now().isoformat()
    tool_input_str = json.dumps(tool_input) if tool_input is not None else None
    tool_output_str = json.dumps(tool_output) if tool_output is not None else None

    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO operation_logs (
            timestamp, farmer_command, detected_intent, tool_called,
            tool_input, tool_output, decision, action, result, status, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            now,
            farmer_command,
            detected_intent,
            tool_called,
            tool_input_str,
            tool_output_str,
            decision,
            action,
            result,
            status,
            details
        )
    )
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return OperationLogModel(
        id=log_id,
        timestamp=now,
        farmer_command=farmer_command,
        detected_intent=detected_intent,
        tool_called=tool_called,
        tool_input=tool_input_str,
        tool_output=tool_output_str,
        decision=decision,
        action=action,
        result=result,
        status=status,
        details=details
    )
