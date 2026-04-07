#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "菠萝手机";
const char* password = "qwer1234";

const int TOUCH_PIN = 4;  // GPIO4 (T0)

WebServer server(80);

String makeHTML() {
  String html = R"rawliteral(
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>ESP32 触摸传感器实时监控</title>
  <style>
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background: linear-gradient(135deg, #1e2a3a, #0f1724);
      color: #fff;
      text-align: center;
      margin: 0;
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
    }
    .card {
      background: rgba(255,255,255,0.1);
      backdrop-filter: blur(10px);
      border-radius: 40px;
      padding: 40px 30px;
      box-shadow: 0 15px 35px rgba(0,0,0,0.3);
      width: 90%;
      max-width: 500px;
    }
    h1 {
      font-size: 2rem;
      margin-bottom: 10px;
      font-weight: 500;
    }
    .sub {
      font-size: 1rem;
      opacity: 0.8;
      margin-bottom: 40px;
    }
    .value-box {
      background: #00000055;
      border-radius: 60px;
      padding: 30px 20px;
      margin: 20px 0;
    }
    .sensor-value {
      font-size: 5rem;
      font-weight: bold;
      font-family: 'Courier New', monospace;
      letter-spacing: 4px;
      color: #ffd966;
      text-shadow: 0 0 10px #ffaa33;
    }
    .unit {
      font-size: 1.8rem;
      margin-left: 10px;
    }
    .note {
      margin-top: 30px;
      font-size: 0.85rem;
      opacity: 0.7;
    }
    .indicator {
      width: 20px;
      height: 20px;
      background-color: #2ecc71;
      border-radius: 50%;
      display: inline-block;
      animation: pulse 1.5s infinite;
      margin-right: 8px;
      vertical-align: middle;
    }
    @keyframes pulse {
      0% { opacity: 0.3; transform: scale(0.8);}
      100% { opacity: 1; transform: scale(1.2);}
    }
    footer {
      margin-top: 30px;
      font-size: 0.7rem;
      opacity: 0.5;
    }
  </style>
</head>
<body>
<div class="card">
  <h1>📡 电容触摸监控仪</h1>
  <div class="sub">靠近 GPIO4 引脚 · 数值实时变化</div>
  <div class="value-box">
    <span class="sensor-value" id="touchValue">---</span>
    <span class="unit">raw</span>
  </div>
  <div class="note">
    <span class="indicator"></span> 实时刷新中 (每秒10次)
  </div>
  <footer>ESP32 触摸传感器 | 数值越小 → 手指越近</footer>
</div>

<script>
  async function fetchTouchValue() {
    try {
      const response = await fetch('/api/touch');
      const data = await response.json();
      document.getElementById('touchValue').innerText = data.value;
    } catch (err) {
      console.error('获取数据失败', err);
      document.getElementById('touchValue').innerText = 'ERR';
    }
  }
  // 每 100ms 拉取一次，达到丝滑实时效果
  setInterval(fetchTouchValue, 100);
  fetchTouchValue();
</script>
</body>
</html>
)rawliteral";
  return html;
}

void handleRoot() {
  server.send(200, "text/html; charset=UTF-8", makeHTML());
}

void handleTouchAPI() {
  int touchVal = touchRead(TOUCH_PIN);
  String json = "{\"value\": " + String(touchVal) + "}";
  server.send(200, "application/json", json);
}

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  Serial.print("正在连接Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi 连接成功");
  Serial.print("ESP32 访问地址: http://");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.on("/api/touch", handleTouchAPI);

  server.begin();
  Serial.println("HTTP 服务器已启动");
}

void loop() {
  server.handleClient();
}