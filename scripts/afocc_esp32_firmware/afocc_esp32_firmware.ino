/*
  =================================================================================
  AFOCC - AI Farm Operations Command Center (n8n Cloud AI Integration)
  Target Microcontroller: ESP32 Dev Module (NodeMCU ESP-WROOM-32)
  =================================================================================
  
  Sensors & Actuator Pin Mapping:
  - DHT11 / DHT22 Temp & Humidity : Signal -> GPIO 4
  - Capacitive Soil Moisture v1.2 : Signal -> GPIO 15 (ADC)
  - HC-SR04 Ultrasonic Tank Sensor: Trig   -> GPIO 5, Echo -> GPIO 0
  - 5V Relay Module (Pump Switch) : IN     -> GPIO 16 (Active LOW)
  
  Wi-Fi Telemetry Target:
  - Live n8n Cloud Webhook: https://msuryamuthu.app.n8n.cloud/webhook/afocc-telemetry
  =================================================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h> // Compatible with ArduinoJson v7.x
#include <DHT.h>

// --- Wi-Fi & SERVER CONFIGURATION ---
const char* WIFI_SSID     = "Surya";        // Your Wi-Fi Name
const char* WIFI_PASSWORD = "Suryaaaa";    // Your Wi-Fi Password

/// Live Direct AFOCC Laptop Telemetry Endpoint (Streams to local server on Wi-Fi)
const char* SERVER_URL    = "http://10.118.4.9:8000/api/v1/sensors/telemetry";

// --- PIN DEFINITIONS ---
#define DHT_PIN           4   // Digital Pin (DHT11/DHT22)
#define SOIL_MOISTURE_PIN 15  // Analog ADC Pin (Capacitive Soil Sensor)
#define DHT_TYPE          DHT11 // Change to DHT22 if using DHT22
#define ULTRASONIC_TRIG   5   // Digital Output (HC-SR04 Trig)
#define ULTRASONIC_ECHO   0   // Digital Input (HC-SR04 Echo)
#define RELAY_PIN         16  // Digital Output (5V Relay Control IN)

// Calibration Constants for Capacitive Soil Moisture Sensor v1.2
const int SOIL_DRY_ADC = 3200; // ADC value in dry air (0% moisture)
const int SOIL_WET_ADC = 1400; // ADC value fully submerged in water (100% moisture)

// Water Tank Height Constants (HC-SR04 Ultrasonic)
const float TANK_MAX_HEIGHT_CM = 20.0; // Distance from sensor to empty bottom (0%)
const float TANK_MIN_HEIGHT_CM = 4.0;  // Distance from sensor to full water level (100%)

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- Initializing AFOCC ESP32 Hardware Firmware (Direct Local Mode) ---");

  // Pin Modes
  pinMode(ULTRASONIC_TRIG, OUTPUT);
  pinMode(ULTRASONIC_ECHO, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // Turn Relay OFF initially (Active LOW)

  // Initialize DHT Sensor
  dht.begin();

  // Connect to Wi-Fi
  Serial.print("Connecting to Wi-Fi Network: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n✅ Wi-Fi Connected Successfully!");
  Serial.print("ESP32 IP Address: ");
  Serial.println(WiFi.localIP());
}

float readSoilMoisturePercentage() {
  int rawADC = analogRead(SOIL_MOISTURE_PIN);
  // Constrain ADC values
  rawADC = constrain(rawADC, SOIL_WET_ADC, SOIL_DRY_ADC);
  // Map ADC to Percentage (Inverted: Higher ADC = Dryer Soil)
  float percentage = map(rawADC, SOIL_DRY_ADC, SOIL_WET_ADC, 0, 100);
  
  Serial.print("[Soil Sensor] Raw ADC: ");
  Serial.print(rawADC);
  Serial.print(" | Moisture: ");
  Serial.print(percentage);
  Serial.println("%");
  
  return percentage;
}

float readWaterTankPercentage(float &distanceCm) {
  digitalWrite(ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG, LOW);

  long durationMicroSec = pulseIn(ULTRASONIC_ECHO, HIGH, 30000); // 30ms timeout
  if (durationMicroSec == 0) {
    distanceCm = 15.0; // Default fallback if no echo received
  } else {
    distanceCm = (durationMicroSec * 0.0343) / 2.0;
  }

  // Calculate Tank Percentage
  float pct = ((TANK_MAX_HEIGHT_CM - distanceCm) / (TANK_MAX_HEIGHT_CM - TANK_MIN_HEIGHT_CM)) * 100.0;
  pct = constrain(pct, 0.0, 100.0);

  Serial.print("[Ultrasonic Tank] Distance: ");
  Serial.print(distanceCm);
  Serial.print(" cm | Level: ");
  Serial.print(pct);
  Serial.println("%");

  return pct;
}

void sendTelemetryToAFOCCServer(float soilPct, float tankPct, float distCm, float tempC, float humidityPct, bool relayOn) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ Wi-Fi disconnected! Skipping HTTP send.");
    return;
  }

  WiFiClient client;
  HTTPClient http;
  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  // Create JSON Payload
  JsonDocument doc;
  doc["field_name"]             = "Field A";
  doc["soil_moisture_pct"]     = soilPct;
  doc["water_tank_level_pct"]   = tankPct;
  doc["water_tank_distance_cm"] = distCm;
  doc["temperature_c"]         = tempC;
  doc["humidity_pct"]          = humidityPct;
  doc["relay_status"]           = relayOn ? "ON" : "OFF";

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  Serial.print("Sending POST Telemetry to Local AFOCC Server -> ");
  Serial.println(jsonPayload);

  int httpCode = http.POST(jsonPayload);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.print("✅ AFOCC Server Response (HTTP ");
    Serial.print(httpCode);
    Serial.print("): ");
    Serial.println(response);

    // Parse Downlink Pump Command from AFOCC Agronomic Engine
    JsonDocument respDoc;
    DeserializationError err = deserializeJson(respDoc, response);
    if (!err && respDoc.containsKey("pump_command")) {
      const char* command = respDoc["pump_command"];
      if (strcmp(command, "ON") == 0) {
        Serial.println("⚡ [DOWNLINK COMMAND] ACTUATING RELAY -> MOTOR ON!");
        digitalWrite(RELAY_PIN, LOW); // Active LOW -> Relay ON, Green LED ON, Motor ON
      } else if (strcmp(command, "OFF") == 0) {
        Serial.println("🛑 [DOWNLINK COMMAND] DEACTIVATING RELAY -> MOTOR OFF!");
        digitalWrite(RELAY_PIN, HIGH); // Relay OFF, Green LED OFF, Motor OFF
      }
    }
  } else {
    Serial.print("❌ HTTP POST Failed! Error: ");
    Serial.println(http.errorToString(httpCode).c_str());
  }

  http.end();
}

void loop() {
  Serial.println("\n------------------------------------------------");
  
  // Read Sensors
  float soilMoisture = readSoilMoisturePercentage();
  
  float distanceCm = 0.0;
  float tankLevel = readWaterTankPercentage(distanceCm);
  
  float tempC = dht.readTemperature();
  float humidityPct = dht.readHumidity();
  
  if (isnan(tempC) || isnan(humidityPct)) {
    Serial.println("⚠️ DHT Sensor read error! Using benchtop fallback values.");
    tempC = 28.5;
    humidityPct = 60.0;
  } else {
    Serial.print("[DHT Microclimate] Temp: ");
    Serial.print(tempC);
    Serial.print(" °C | Humidity: ");
    Serial.print(humidityPct);
    Serial.println("%");
  }

  bool relayState = (digitalRead(RELAY_PIN) == LOW); // LOW = Relay ACTIVE / ON

  // Send Live Telemetry to AFOCC Laptop Server
  sendTelemetryToAFOCCServer(soilMoisture, tankLevel, distanceCm, tempC, humidityPct, relayState);

  // Wait 5 seconds before next sensor loop iteration
  delay(5000);
}