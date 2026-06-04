#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

// ===== WiFi =====
const char* ssid = "yourwifissid";
const char* password = "yourwifipassword";

// ===== Pins =====
#define TOUCH_PIN 4
#define BUZZER_PIN 18

AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

// ===== HTML (Terminal UI) =====
const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Door Bell Console</title>

<style>
body {
  background: #0d0d0d;
  color: #00ff88;
  font-family: monospace;
}

h2 {
  color: #00bfff;
}

#terminal {
  height: 300px;
  overflow-y: auto;
  background: #111;
  padding: 10px;
  border: 1px solid #00ff88;
}

.line {
  margin: 2px 0;
}

</style>
</head>

<body>

<h2>🚪 Door Bell Terminal</h2>

<input type="file" id="soundFile" accept="audio/*">
<audio id="ding"></audio>

<div id="terminal"></div>

<script>

let terminal = document.getElementById("terminal");

function log(msg) {
  let div = document.createElement("div");
  div.className = "line";
  div.innerText = msg;
  terminal.appendChild(div);
  terminal.scrollTop = terminal.scrollHeight;
}

let audio = document.getElementById("ding");

// user sound
document.getElementById("soundFile").addEventListener("change", function(e) {
  let file = e.target.files[0];
  audio.src = URL.createObjectURL(file);
  log("🔊 Sound loaded");
});

// WebSocket with auto reconnect
let ws;

function connect() {

  log("⏳ Connecting...");

  ws = new WebSocket("ws://" + location.host + "/ws");

  ws.onopen = () => {
    log("🟢 Connected");
  };

  ws.onclose = () => {
    log("🔴 Disconnected → reconnecting...");
    setTimeout(connect, 1000);
  };

  ws.onmessage = (event) => {

    if(event.data === "down") {
      log("👆 TOUCH START");

      audio.currentTime = 0;
      audio.play();
    }

    if(event.data === "up") {
      log("👇 TOUCH END");

      audio.pause();
      audio.currentTime = 0;
    }

    if(event.data === "ping") {
      log("💓 alive");
    }
  };
}

connect();

</script>

</body>
</html>
)rawliteral";

// ===== state =====
bool lastState = LOW;
unsigned long lastHeartbeat = 0;

// ===== setup =====
void setup() {
  Serial.begin(115200);

  pinMode(TOUCH_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  // Static IP
  IPAddress local_IP(192, 168, 1, 50);
  IPAddress gateway(192, 168, 1, 1);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.config(local_IP, gateway, subnet);

  WiFi.begin(ssid, password);

  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected!");
  Serial.println(WiFi.localIP());

  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send_P(200, "text/html", index_html);
  });

  ws.onEvent([](AsyncWebSocket *server,
                AsyncWebSocketClient *client,
                AwsEventType type,
                void *arg,
                uint8_t *data,
                size_t len) {});

  server.addHandler(&ws);
  server.begin();
}

// ===== loop =====
void loop() {

  ws.cleanupClients();

  bool state = digitalRead(TOUCH_PIN);

  // =========================
  // BUZZER (better sound)
  // =========================
  if (state == HIGH) {

    tone(BUZZER_PIN, 2000);
    delay(40);
    noTone(BUZZER_PIN);
    delay(40);
    tone(BUZZER_PIN, 2000);

  } else {
    noTone(BUZZER_PIN);
  }

  // =========================
  // STATE SYNC (fix lag + reconnect safety)
  // =========================
  if (state != lastState) {
    ws.textAll(state ? "down" : "up");
    lastState = state;
  }

  // =========================
  // HEARTBEAT (keeps connection alive)
  // =========================
  if (millis() - lastHeartbeat > 3000) {
    ws.textAll("ping");
    lastHeartbeat = millis();
  }
}

