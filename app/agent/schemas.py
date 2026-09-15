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
            "description": "Retrieves ambient farm weather data including temperature (°C), relative humidity (%), and rainfall probability (%). Optionally accepts a location name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Optional location/city name, e.g. 'Bangalore', 'London'."
                    }
                },
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
    },
    {
        "type": "function",
        "function": {
            "name": "get_soil_crop_parameters",
            "description": "Retrieves comprehensive FAO-56 dynamic agronomic parameters for a field: soil type, crop, growth stage, NPK, pH, wilting point, field capacity, and optimal moisture depletion threshold.",
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
            "name": "update_field_agronomic_profile",
            "description": "Updates the agronomic classification profile for a field (soil type, crop, growth stage, pH) and automatically recalculates dynamic moisture thresholds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "The target field name, e.g. 'Field A' or 'Field B'."
                    },
                    "soil_type": {
                        "type": "string",
                        "description": "Soil type: 'Clay', 'Sandy', 'Loamy', 'Silt', 'Peat', 'Saline'."
                    },
                    "crop": {
                        "type": "string",
                        "description": "Crop type: 'Tomato', 'Wheat', 'Rice', 'Cotton', 'Maize', 'Sugarcane'."
                    },
                    "growth_stage": {
                        "type": "string",
                        "description": "Crop growth stage: 'Initial/Vegetative', 'Flowering', 'Yield Formation', 'Maturity'."
                    }
                },
                "required": ["field_name"]
            }
        }
    }
]
