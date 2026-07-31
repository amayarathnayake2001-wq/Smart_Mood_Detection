
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <DHT.h>

// ─── WiFi Configuration ─────────────────────────────────────
const char* WIFI_SSID     = "Dialog 4G 291";
const char* WIFI_PASSWORD = "9F92c852";

// ─── mDNS Hostname ──────────────────────────────────────────
const char* MDNS_HOSTNAME = "sensor";  

// ─── Pin Definitions ────────────────────────────────────────
// Sound Sensor
#define SOUND_ANALOG_PIN   34   // A0 output (analog noise level)
#define SOUND_DIGITAL_PIN  26   // D0 output (digital threshold trigger)

// Light Sensor (LDR)
#define LIGHT_ANALOG_PIN   35   // A0 output (analog light level)
#define LIGHT_DIGITAL_PIN  27   // D0 output (digital threshold trigger)

// DHT11 Temperature & Humidity Sensor
#define DHT_PIN            15   // DATA pin
#define DHT_TYPE           DHT11

// ─── Sound Stream Configuration ─────────────────────────────
#define SOUND_STREAM_DURATION_MS   30000   // 30 seconds = 30000 ms
#define SOUND_SAMPLE_INTERVAL_MS   100     // sample every 100ms → 600 samples
#define SOUND_NOISE_THRESHOLD      2500    // analog level considered "noise event"

// ─── Objects ────────────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
WebServer server(80);

unsigned long bootTime;

// ─── Utility: Build CORS Headers ────────────────────────────
void setCorsHeaders() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

// ─── Utility: Send JSON Response ────────────────────────────
void sendJson(int code, String json) {
  setCorsHeaders();
  server.send(code, "application/json", json);
}

// ─── Read Sound Sensor (instant) ────────────────────────────
int readSoundAnalog() {
  return analogRead(SOUND_ANALOG_PIN);
}

bool readSoundDigital() {
  return digitalRead(SOUND_DIGITAL_PIN) == HIGH;
}

// ─── Read Light Sensor (instant) ─────────────────────────────
int readLightAnalog() {
  return analogRead(LIGHT_ANALOG_PIN);
}

bool readLightDigital() {
  return digitalRead(LIGHT_DIGITAL_PIN) == HIGH;
}

// ─── Read DHT11 ─────────────────────────────────────────────
float readTemperature() {
  float t = dht.readTemperature();   // Celsius
  return isnan(t) ? -999.0 : t;
}

float readHumidity() {
  float h = dht.readHumidity();
  return isnan(h) ? -999.0 : h;
}

// ═══════════════════════════════════════════════════════════
//  API HANDLERS
// ═══════════════════════════════════════════════════════════

// ─── GET /api/health ─────────────────────────────────────────
void handleHealth() {
  unsigned long uptimeSec = (millis() - bootTime) / 1000;
  String json = "{";
  json += "\"status\":\"ok\",";
  json += "\"device\":\"ESP32-Sensor\",";
  json += "\"uptime_seconds\":" + String(uptimeSec) + ",";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"hostname\":\"" + String(MDNS_HOSTNAME) + ".local\",";
  json += "\"free_heap\":" + String(ESP.getFreeHeap());
  json += "}";
  sendJson(200, json);
}

// ─── GET /api/sound ──────────────────────────────────────────
void handleSound() {
  int analogVal = readSoundAnalog();
  bool digitalVal = readSoundDigital();

  String json = "{";
  json += "\"sensor\":\"sound\",";
  json += "\"analog_level\":" + String(analogVal) + ",";
  json += "\"digital_trigger\":" + String(digitalVal ? "true" : "false") + ",";
  json += "\"max_analog\":4095";
  json += "}";
  sendJson(200, json);
}

// ─── GET /api/light ──────────────────────────────────────────
void handleLight() {
  int analogVal = readLightAnalog();
  bool digitalVal = readLightDigital();

  String json = "{";
  json += "\"sensor\":\"light\",";
  json += "\"analog_level\":" + String(analogVal) + ",";
  json += "\"digital_trigger\":" + String(digitalVal ? "true" : "false") + ",";
  json += "\"max_analog\":4095";
  json += "}";
  sendJson(200, json);
}

// ─── GET /api/climate ────────────────────────────────────────
void handleClimate() {
  float temp = readTemperature();
  float hum  = readHumidity();

  String json = "{";
  json += "\"sensor\":\"dht11\",";
  json += "\"temperature_c\":" + String(temp, 1) + ",";
  json += "\"humidity_pct\":" + String(hum, 1) + ",";
  json += "\"valid\":" + String((temp > -999 && hum > -999) ? "true" : "false");
  json += "}";
  sendJson(200, json);
}

// ─── GET /api/sensors ────────────────────────────────────────
void handleAllSensors() {
  int soundAnalog   = readSoundAnalog();
  bool soundDigital = readSoundDigital();
  int lightAnalog   = readLightAnalog();
  bool lightDigital = readLightDigital();
  float temp        = readTemperature();
  float hum         = readHumidity();

  String json = "{";
  
  // Sound
  json += "\"sound\":{";
  json += "\"analog_level\":" + String(soundAnalog) + ",";
  json += "\"digital_trigger\":" + String(soundDigital ? "true" : "false");
  json += "},";

  // Light
  json += "\"light\":{";
  json += "\"analog_level\":" + String(lightAnalog) + ",";
  json += "\"digital_trigger\":" + String(lightDigital ? "true" : "false");
  json += "},";

  // Climate
  json += "\"climate\":{";
  json += "\"temperature_c\":" + String(temp, 1) + ",";
  json += "\"humidity_pct\":" + String(hum, 1) + ",";
  json += "\"valid\":" + String((temp > -999 && hum > -999) ? "true" : "false");
  json += "},";

  // Metadata
  json += "\"timestamp_ms\":" + String(millis());
  json += "}";
  
  sendJson(200, json);
}

// ─── GET /api/sound/stream ───────────────────────────────────
//  Streams a 30-second .wav file (8kHz, 8-bit, mono) directly.
void handleSoundStream() {
  Serial.println("[STREAM] Client connected. Capturing 30s .wav file...");

  const int sampleRate = 8000;
  const unsigned long sampleIntervalUs = 1000000UL / sampleRate; // 125 us
  const int durationSeconds = 30;
  const uint32_t totalSamples = sampleRate * durationSeconds; 

  WiFiClient client = server.client();
  
  // HTTP Headers
  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: audio/wav");
  client.println("Content-Disposition: attachment; filename=\"capture.wav\"");
  client.print("Content-Length: ");
  client.println(44 + totalSamples);
  client.println("Connection: close");
  client.println();

  // WAV Header (44 bytes)
  uint8_t wavHeader[44] = {
    'R', 'I', 'F', 'F',
    0, 0, 0, 0, // ChunkSize (filled later)
    'W', 'A', 'V', 'E',
    'f', 'm', 't', ' ',
    16, 0, 0, 0, // Subchunk1Size
    1, 0,        // AudioFormat (PCM)
    1, 0,        // NumChannels
    0, 0, 0, 0,  // SampleRate (filled later)
    0, 0, 0, 0,  // ByteRate (filled later)
    1, 0,        // BlockAlign
    8, 0,        // BitsPerSample
    'd', 'a', 't', 'a',
    0, 0, 0, 0   // Subchunk2Size (filled later)
  };

  uint32_t chunkSize = 36 + totalSamples;
  wavHeader[4] = (uint8_t)(chunkSize & 0xFF);
  wavHeader[5] = (uint8_t)((chunkSize >> 8) & 0xFF);
  wavHeader[6] = (uint8_t)((chunkSize >> 16) & 0xFF);
  wavHeader[7] = (uint8_t)((chunkSize >> 24) & 0xFF);

  wavHeader[24] = (uint8_t)(sampleRate & 0xFF);
  wavHeader[25] = (uint8_t)((sampleRate >> 8) & 0xFF);
  wavHeader[26] = (uint8_t)((sampleRate >> 16) & 0xFF);
  wavHeader[27] = (uint8_t)((sampleRate >> 24) & 0xFF);

  wavHeader[28] = wavHeader[24];
  wavHeader[29] = wavHeader[25];
  wavHeader[30] = wavHeader[26];
  wavHeader[31] = wavHeader[27];

  wavHeader[40] = (uint8_t)(totalSamples & 0xFF);
  wavHeader[41] = (uint8_t)((totalSamples >> 8) & 0xFF);
  wavHeader[42] = (uint8_t)((totalSamples >> 16) & 0xFF);
  wavHeader[43] = (uint8_t)((totalSamples >> 24) & 0xFF);

  client.write(wavHeader, 44);

  const int bufferSize = 1024;
  uint8_t buffer[bufferSize];
  int bufferIndex = 0;

  unsigned long lastSampleTime = micros();
  unsigned long samplesSent = 0;

  while (client.connected() && samplesSent < totalSamples) {
    unsigned long now = micros();
    if (now - lastSampleTime >= sampleIntervalUs) {
      lastSampleTime += sampleIntervalUs;

      // Read 12-bit ADC (0-4095), map to 8-bit (0-255)
      int val = analogRead(SOUND_ANALOG_PIN);
      buffer[bufferIndex++] = (uint8_t)(val >> 4);
      samplesSent++;

      if (bufferIndex >= bufferSize) {
        client.write(buffer, bufferSize);
        bufferIndex = 0;
        yield(); // Feed watchdog and keep WiFi alive
      }
    }
  }

  // Send any remaining bytes
  if (bufferIndex > 0 && client.connected()) {
    client.write(buffer, bufferIndex);
  }

  client.stop();
  Serial.println("[STREAM] WAV file sent successfully. Sent " + String(samplesSent) + " audio samples.");
}


// ─── OPTIONS handler (CORS preflight) ────────────────────────
void handleOptions() {
  setCorsHeaders();
  server.send(204);
}

// ─── 404 Not Found ───────────────────────────────────────────
void handleNotFound() {
  String json = "{\"error\":\"not_found\",\"message\":\"Endpoint not found\"}";
  sendJson(404, json);
}

// ═══════════════════════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println();
  Serial.println("============================================");
  Serial.println("  ESP32 Sensor REST API Server");
  Serial.println("============================================");

  // ── Initialize Pins ────────────────────────────────────
  pinMode(SOUND_ANALOG_PIN,  INPUT);
  pinMode(SOUND_DIGITAL_PIN, INPUT);
  pinMode(LIGHT_ANALOG_PIN,  INPUT);
  pinMode(LIGHT_DIGITAL_PIN, INPUT);
  // DHT pin is managed by the DHT library

  // ── Initialize DHT Sensor ─────────────────────────────
  dht.begin();
  Serial.println("[INIT] DHT11 sensor initialized on GPIO " + String(DHT_PIN));

  // ── Connect to WiFi ───────────────────────────────────
  Serial.print("[WIFI] Connecting to ");
  Serial.print(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" Connected!");
    Serial.println("[WIFI] IP Address: " + WiFi.localIP().toString());
    Serial.println("[WIFI] Signal Strength: " + String(WiFi.RSSI()) + " dBm");
  } else {
    Serial.println(" FAILED!");
    Serial.println("[WIFI] Could not connect. Check SSID/password.");
    Serial.println("[WIFI] Restarting in 5 seconds...");
    delay(5000);
    ESP.restart();
  }

  // ── Setup mDNS ────────────────────────────────────────
  if (MDNS.begin(MDNS_HOSTNAME)) {
    Serial.println("[MDNS] Hostname: http://" + String(MDNS_HOSTNAME) + ".local");
    MDNS.addService("http", "tcp", 80);
  } else {
    Serial.println("[MDNS] Failed to start mDNS responder.");
  }

  // ── Register API Routes ───────────────────────────────
  // Health check
  server.on("/api/health",   HTTP_GET, handleHealth);

  // Individual sensor endpoints
  server.on("/api/sound",    HTTP_GET, handleSound);
  server.on("/api/light",    HTTP_GET, handleLight);
  server.on("/api/climate",  HTTP_GET, handleClimate);

  // All sensors at once
  server.on("/api/sensors",  HTTP_GET, handleAllSensors);

  // 1-minute sound stream capture
  server.on("/api/sound/stream", HTTP_GET, handleSoundStream);

  // CORS preflight
  server.on("/api/health",       HTTP_OPTIONS, handleOptions);
  server.on("/api/sound",        HTTP_OPTIONS, handleOptions);
  server.on("/api/light",        HTTP_OPTIONS, handleOptions);
  server.on("/api/climate",      HTTP_OPTIONS, handleOptions);
  server.on("/api/sensors",      HTTP_OPTIONS, handleOptions);
  server.on("/api/sound/stream", HTTP_OPTIONS, handleOptions);

  // 404
  server.onNotFound(handleNotFound);

  // ── Start Server ──────────────────────────────────────
  server.begin();
  bootTime = millis();

  Serial.println();
  Serial.println("============================================");
  Serial.println("  Server is RUNNING on port 80");
  Serial.println("  http://" + WiFi.localIP().toString());
  Serial.println("  http://" + String(MDNS_HOSTNAME) + ".local");
  Serial.println("============================================");
  Serial.println();
  Serial.println("Available endpoints:");
  Serial.println("  GET /api/health        — Server status");
  Serial.println("  GET /api/sensors       — All sensor data");
  Serial.println("  GET /api/sound         — Sound sensor (instant)");
  Serial.println("  GET /api/light         — Light sensor (instant)");
  Serial.println("  GET /api/climate       — DHT11 temp & humidity");
  Serial.println("  GET /api/sound/stream  — 1-min sound capture");
  Serial.println();
}

// ═══════════════════════════════════════════════════════════
//  LOOP
// ═══════════════════════════════════════════════════════════
void loop() {
  server.handleClient();
  delay(2);  // small delay to avoid watchdog reset
}
