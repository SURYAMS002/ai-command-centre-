import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import openai
from openai import OpenAI

from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.schemas import OPENAI_TOOLS
from app.services.safety import safety_validator
from app.services.automation import default_automation
from app.tools import (
    get_water_tank_status,
    get_soil_moisture,
    get_weather,
    get_farm_status,
    check_irrigation_requirement,
    start_irrigation,
    stop_irrigation
)

class AFOCCAgent:
    """
    AI Farm Operations Command Center (AFOCC) AI Agent.
    Orchestrates natural language commands via OpenAI tool calling & safety validation layer with farmer confirmation.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.tools_map = {
            "get_water_tank_status": get_water_tank_status,
            "get_soil_moisture": get_soil_moisture,
            "get_weather": get_weather,
            "get_farm_status": get_farm_status,
            "check_irrigation_requirement": check_irrigation_requirement,
            "start_irrigation": start_irrigation,
            "stop_irrigation": stop_irrigation,
        }

    def _extract_field_name(self, text: str) -> str:
        match = re.search(r"field\s+([a-z0-9]+)", text, re.IGNORECASE)
        if match:
            return f"Field {match.group(1).upper()}"
        return "Field A"

    def _fallback_intent_router(
        self,
        farmer_command: str,
        pending_action: Optional[Dict[str, str]] = None,
        db_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        cmd_lower = farmer_command.lower().strip()
        tools_called = []

        # Handle Farmer Confirmation ("Yes" / "Confirm" / "Proceed")
        if cmd_lower in ["yes", "y", "confirm", "proceed", "start"] and pending_action:
            field = pending_action.get("field_name", "Field A")
            action = pending_action.get("action", "START_IRRIGATION")
            res = default_automation.execute_irrigation_action(field, action, skip_safety=True, db_path=db_path)
            tools_called.append({"tool": "automation_adapter", "args": {"field": field, "action": action}, "output": res})
            
            action_past = "started" if action == "START_IRRIGATION" else "stopped"
            return {
                "command": farmer_command,
                "response": f"{field} irrigation has been {action_past} successfully.",
                "tools_called": tools_called,
                "status": "SUCCESS",
                "mode": "CONFIRMED_ACTION_EXECUTED"
            }

        if "water tank" in cmd_lower or "check tank" in cmd_lower or "tank level" in cmd_lower:
            res = get_water_tank_status(db_path=db_path)
            tools_called.append({"tool": "get_water_tank_status", "args": {}, "output": res})
            response_text = f"Water Tank Status: {res.get('summary')}"
            return {
                "command": farmer_command,
                "response": response_text,
                "tools_called": tools_called,
                "status": "SUCCESS"
            }

        elif "should i irrigate" in cmd_lower or "irrigation requirement" in cmd_lower or "need water" in cmd_lower:
            field = self._extract_field_name(farmer_command)
            res = check_irrigation_requirement(field, db_path=db_path)
            tools_called.append({"tool": "check_irrigation_requirement", "args": {"field_name": field}, "output": res})
            response_text = res.get("summary", f"Irrigation evaluation complete for {field}.")
            return {
                "command": farmer_command,
                "response": response_text,
                "tools_called": tools_called,
                "status": "SUCCESS"
            }

        elif "stop irrigation" in cmd_lower or "turn off irrigation" in cmd_lower:
            field = self._extract_field_name(farmer_command)
            safety_res = safety_validator.validate_irrigation_request(field, "STOP_IRRIGATION", db_path=db_path)
            if not safety_res.valid:
                return {
                    "command": farmer_command,
                    "response": safety_res.message,
                    "tools_called": [],
                    "status": "BLOCKED"
                }

            return {
                "command": farmer_command,
                "response": f"{field} is currently irrigating. Do you want me to stop irrigation?",
                "tools_called": [],
                "status": "PENDING_CONFIRMATION",
                "pending_action": {"field_name": field, "action": "STOP_IRRIGATION"}
            }

        elif "irrigate" in cmd_lower or "start irrigation" in cmd_lower or "turn on irrigation" in cmd_lower:
            field = self._extract_field_name(farmer_command)
            safety_res = safety_validator.validate_irrigation_request(field, "START_IRRIGATION", db_path=db_path)
            if not safety_res.valid:
                return {
                    "command": farmer_command,
                    "response": safety_res.message,
                    "tools_called": [],
                    "status": "BLOCKED"
                }

            return {
                "command": farmer_command,
                "response": safety_res.message,
                "tools_called": [],
                "status": "PENDING_CONFIRMATION",
                "pending_action": {"field_name": field, "action": "START_IRRIGATION"}
            }

        elif "soil" in cmd_lower or "moisture" in cmd_lower:
            field = self._extract_field_name(farmer_command)
            res = get_soil_moisture(field, db_path=db_path)
            tools_called.append({"tool": "get_soil_moisture", "args": {"field_name": field}, "output": res})
            response_text = res.get("summary", f"Soil moisture fetched for {field}.")
            return {
                "command": farmer_command,
                "response": response_text,
                "tools_called": tools_called,
                "status": "SUCCESS"
            }

        elif "weather" in cmd_lower or "temperature" in cmd_lower or "rain" in cmd_lower:
            res = get_weather(db_path=db_path)
            tools_called.append({"tool": "get_weather", "args": {}, "output": res})
            response_text = f"Weather Status: {res.get('summary')}"
            return {
                "command": farmer_command,
                "response": response_text,
                "tools_called": tools_called,
                "status": "SUCCESS"
            }

        else:
            res = get_farm_status(db_path=db_path)
            tools_called.append({"tool": "get_farm_status", "args": {}, "output": res})
            response_text = res.get("summary", "Farm status retrieved.")
            return {
                "command": farmer_command,
                "response": response_text,
                "tools_called": tools_called,
                "status": "SUCCESS"
            }

    def run_command(
        self,
        farmer_command: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        pending_action: Optional[Dict[str, str]] = None,
        db_path: Optional[Path] = None,
        model: str = "gpt-4o-mini"
    ) -> Dict[str, Any]:
        # Handle Pending Action Confirmation directly
        cmd_clean = farmer_command.strip().lower()
        if cmd_clean in ["yes", "y", "confirm", "proceed", "start", "do it"] and pending_action:
            field = pending_action.get("field_name", "Field A")
            action = pending_action.get("action", "START_IRRIGATION")
            res = default_automation.execute_irrigation_action(field, action, skip_safety=True, db_path=db_path)
            action_past = "started" if action == "START_IRRIGATION" else "stopped"
            return {
                "command": farmer_command,
                "response": f"{field} irrigation has been {action_past} successfully.",
                "tools_called": [{"tool": "automation_adapter", "args": {"field": field, "action": action}, "output": res}],
                "status": "SUCCESS"
            }

        if not self.api_key:
            return self._fallback_intent_router(farmer_command, pending_action=pending_action, db_path=db_path)

        try:
            client = OpenAI(api_key=self.api_key)
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": farmer_command})

            tools_called = []
            max_iterations = 5
            iteration = 0

            while iteration < max_iterations:
                iteration += 1
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=OPENAI_TOOLS,
                    tool_choice="auto",
                    temperature=0.2
                )
                assistant_message = response.choices[0].message
                messages.append(assistant_message)

                if assistant_message.tool_calls:
                    for tool_call in assistant_message.tool_calls:
                        fn_name = tool_call.function.name
                        fn_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                        # Intercept start_irrigation / stop_irrigation for Safety Validation & Confirmation
                        if fn_name in ["start_irrigation", "stop_irrigation"]:
                            field = fn_args.get("field_name", "Field A")
                            action_type = "START_IRRIGATION" if fn_name == "start_irrigation" else "STOP_IRRIGATION"
                            safety_res = safety_validator.validate_irrigation_request(field, action_type, db_path=db_path)

                            if not safety_res.valid:
                                return {
                                    "command": farmer_command,
                                    "response": safety_res.message,
                                    "tools_called": tools_called,
                                    "status": "BLOCKED"
                                }

                            return {
                                "command": farmer_command,
                                "response": safety_res.message,
                                "tools_called": tools_called,
                                "status": "PENDING_CONFIRMATION",
                                "pending_action": {"field_name": field, "action": action_type}
                            }

                        if fn_name in self.tools_map:
                            target_fn = self.tools_map[fn_name]
                            tool_result = target_fn(**fn_args, db_path=db_path) if db_path else target_fn(**fn_args)
                        else:
                            tool_result = {"error": f"Tool '{fn_name}' is not registered."}

                        tools_called.append({"tool": fn_name, "args": fn_args, "output": tool_result})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": fn_name,
                            "content": json.dumps(tool_result)
                        })
                else:
                    return {
                        "command": farmer_command,
                        "response": assistant_message.content,
                        "tools_called": tools_called,
                        "status": "SUCCESS"
                    }

            return {
                "command": farmer_command,
                "response": assistant_message.content or "Completed tool execution loop.",
                "tools_called": tools_called,
                "status": "MAX_ITERATIONS_REACHED"
            }

        except (openai.RateLimitError, openai.OpenAIError, Exception):
            return self._fallback_intent_router(farmer_command, pending_action=pending_action, db_path=db_path)

# Global default agent instance
default_agent = AFOCCAgent()
