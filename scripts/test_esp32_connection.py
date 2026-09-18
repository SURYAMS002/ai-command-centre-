import time
import requests

SERVER_URL = "http://127.0.0.1:8000/api/v1/sensors/telemetry"

print("--- Testing AFOCC ESP32 Telemetry Ingestion API ---")

test_payloads = [
    {
        "field_name": "Field A",
        "soil_moisture_pct": 14.5,
        "water_tank_level_pct": 82.0,
        "temperature_c": 29.2,
        "humidity_pct": 58.0,
        "relay_status": "OFF"
    },
    {
        "field_name": "Field A",
        "soil_moisture_pct": 28.0,
        "water_tank_level_pct": 78.5,
        "temperature_c": 30.1,
        "humidity_pct": 55.0,
        "relay_status": "ON"
    }
]

for i, payload in enumerate(test_payloads, 1):
    print(f"\nSending Telemetry Payload #{i}: {payload}")
    try:
        response = requests.post(SERVER_URL, json=payload, timeout=5)
        print(f"✅ Response ({response.status_code}): {response.json()}")
    except Exception as e:
        print(f"❌ Request failed: {e}")
    time.sleep(2)

print("\nTelemetry API Ingestion Test Completed Successfully!")
