OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_water_tank_status",
            "description": "Retrieves the current status of the farm's main water tank, including capacity, water level percentage, volume in litres, and pump status.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_soil_moisture",
            "description": "Retrieves soil moisture percentage, crop type, field area, and current irrigation status for a specific field.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "The target field name, e.g. 'Field A' or 'Field B'."
                    }
                },
                "required": ["field_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Retrieves ambient farm weather data including temperature (°C), relative humidity (%), and rainfall probability (%).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_farm_status",
            "description": "Retrieves comprehensive, aggregated status across all farm components (water tank, all fields, soil moisture, active irrigation, weather).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_irrigation_requirement",
            "description": "Evaluates whether a specific field requires irrigation using the explainable rule-based decision engine based on soil moisture, water tank availability, and rain probability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "The target field name, e.g. 'Field A' or 'Field B'."
                    }
                },
                "required": ["field_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_irrigation",
            "description": "Triggers the actuator layer to start irrigation for the specified field and updates persistent farm state to ON.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "The target field name, e.g. 'Field A' or 'Field B'."
                    }
                },
                "required": ["field_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_irrigation",
            "description": "Triggers the actuator layer to stop irrigation for the specified field and updates persistent farm state to OFF.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "The target field name, e.g. 'Field A' or 'Field B'."
                    }
                },
                "required": ["field_name"]
            }
        }
    }
]
