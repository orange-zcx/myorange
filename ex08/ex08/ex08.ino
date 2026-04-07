#include <WiFi.h>
#include <WebServer.h>

const int LED_PIN = 2;
const int TOUCH_PIN = 4;

const char* ssid = "菠萝手机";
const char* password = "qwer1234";

bool armed = false;
bool alarmActive = false;

unsigned long lastBlink = 0;
const unsigned long blinkInterval = 200;
bool ledState = false;

const int TOUCH_THRESHOLD = 30;

WebServer server(80);

bool isTouched() {
  int touchValue = touchRead(TOUCH_PIN);
  return (touchValue < TOUCH_THRESHOLD);
}

void handleLED() {
  if (alarmActive) {
    unsigned long now = millis();
    if (now - lastBlink >= blinkInterval) {
      lastBlink = now;
      ledState = !ledState;
      digitalWrite(LED_PIN, ledState ? HIGH : LOW);
    }
  } else {
    digitalWrite(LED_PIN, LOW);
    ledState = false;
  }
}

String makePage() {
  String statusText;
  if (alarmActive) {
    statusText = "⚠️ 报警中！请撤防 ⚠️";
  } else if (armed) {
    statusText = "🔒 已布防 (触碰将触发报警)";
  } else {
    statusText = "🔓 已撤防 (安全模式)";
  }

  String html = R"rawliteral(
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ESP32 安防主机</title>
  <style>
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      text-align: center;
      margin-top: 60px;
      background-color: #f4f6f9;
    }
    .container {
      background: white;
      max-width: 400px;
      margin: 0 auto;
      padding: 30px 20px;
      border-radius: 25px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    h1 {
      color: #2c3e50;
      margin-bottom: 10px;
    }
    .status {
      font-size: 1.3rem;
      padding: 15px;
      margin: 20px 0;
      border-radius: 40px;
      background: #ecf0f1;
      font-weight: bold;
    }
    button {
      background-color: #3498db;
      border: none;
      color: white;
      padding: 12px 28px;
      margin: 10px 12px;
      font-size: 1.1rem;
      border-radius: 50px;
      cursor: pointer;
      transition: 0.2s;
      box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    button.arm {
      background-color: #27ae60;
    }
    button.arm:hover {
      background-color: #2ecc71;
    }
    button.disarm {
      background-color: #e67e22;
    }
    button.disarm:hover {
      background-color: #f39c12;
    }
    footer {
      margin-top: 30px;
      font-size: 0.8rem;
      color: #7f8c8d;
    }
  </style>
</head>
<body>
<div class="container">
  <h1>🛡️ ESP32 安防系统</h1>
  <div class="status" id="statusText">)rawliteral" + statusText + R"rawliteral(</div>
  <button class="arm" id="armBtn">🔒 布防</button>
  <button class="disarm" id="disarmBtn">🔓 撤防</button>
  <footer>布防后触碰金属引脚 → LED高频闪烁锁定报警<br>只有点击撤防才能停止</footer>
</div>

<script>
  function updateStatus() {
    fetch('/state')
      .then(response => response.json())
      .then(data => {
        const statusDiv = document.getElementById('statusText');
        if (data.alarmActive) {
          statusDiv.innerHTML = '⚠️ 报警中！请撤防 ⚠️';
        } else if (data.armed) {
          statusDiv.innerHTML = '🔒 已布防 (触碰将触发报警)';
        } else {
          statusDiv.innerHTML = '🔓 已撤防 (安全模式)';
        }
      })
      .catch(err => console.error('状态获取失败', err));
  }

  document.getElementById('armBtn').addEventListener('click', () => {
    fetch('/arm', { method: 'POST' })
      .then(() => updateStatus())
      .catch(err => console.error('布防失败', err));
  });

  document.getElementById('disarmBtn').addEventListener('click', () => {
    fetch('/disarm', { method: 'POST' })
      .then(() => updateStatus())
      .catch(err => console.error('撤防失败', err));
  });

  setInterval(updateStatus, 1000);
  updateStatus();
</script>
</body>
</html>
)rawliteral";
  return html;
}

void handleRoot() {
  server.send(200, "text/html; charset=UTF-8", makePage());
}

void handleArm() {
  armed = true;
  alarmActive = false;
  digitalWrite(LED_PIN, LOW);
  Serial.println("系统已布防");
  server.send(200, "text/plain", "Armed");
}

void handleDisarm() {
  armed = false;
  alarmActive = false;
  digitalWrite(LED_PIN, LOW);
  Serial.println("系统已撤防");
  server.send(200, "text/plain", "Disarmed");
}

void handleState() {
  String json = "{\"armed\":";
  json += armed ? "true" : "false";
  json += ",\"alarmActive\":";
  json += alarmActive ? "true" : "false";
  json += "}";
  server.send(200, "application/json", json);
}

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  WiFi.begin(ssid, password);
  Serial.print("正在连接Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi连接成功");
  Serial.print("访问地址: http://");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.on("/arm", HTTP_POST, handleArm);
  server.on("/disarm", HTTP_POST, handleDisarm);
  server.on("/state", handleState);

  server.begin();
  Serial.println("HTTP服务器已启动");
}

void loop() {
  server.handleClient();

  if (armed && !alarmActive) {
    if (isTouched()) {
      alarmActive = true;
      Serial.println("⚠️ 触摸触发报警！LED开始闪烁，请撤防 ⚠️");
    }
  }

  handleLED();
}