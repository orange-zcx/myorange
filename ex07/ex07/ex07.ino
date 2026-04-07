#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "菠萝手机";
const char* password = "qwer1234";

const int LED_PIN = 2;
const int PWM_CHANNEL = 0;
const int PWM_FREQ = 5000;
const int PWM_RESOLUTION = 8;

int currentBrightness = 0;

WebServer server(80);

void setBrightness(int value) {
  if (value < 0) value = 0;
  if (value > 255) value = 255;
  currentBrightness = value;
  ledcWrite(PWM_CHANNEL, currentBrightness);
  Serial.print("亮度设置为: ");
  Serial.println(currentBrightness);
}

String makePage() {
  String html = R"rawliteral(
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>ESP32 PWM LED 控制</title>
  <style>
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      text-align: center;
      margin-top: 50px;
      background-color: #f0f0f0;
    }
    .container {
      background: white;
      max-width: 500px;
      margin: 0 auto;
      padding: 30px 20px;
      border-radius: 20px;
      box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    h1 {
      color: #2c3e50;
      font-size: 1.8rem;
    }
    .status {
      font-size: 1.2rem;
      margin: 20px 0;
      padding: 10px;
      background: #ecf0f1;
      border-radius: 30px;
    }
    .brightness-value {
      font-weight: bold;
      color: #e67e22;
      font-size: 1.4rem;
    }
    input[type="range"] {
      width: 80%;
      margin: 20px auto;
      -webkit-appearance: none;
      background: #ddd;
      height: 8px;
      border-radius: 5px;
      outline: none;
    }
    input[type="range"]::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 25px;
      height: 25px;
      background: #3498db;
      border-radius: 50%;
      cursor: pointer;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    button {
      background-color: #3498db;
      border: none;
      color: white;
      padding: 10px 25px;
      margin: 10px 8px;
      font-size: 1rem;
      border-radius: 40px;
      cursor: pointer;
      transition: 0.2s;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    button:hover {
      background-color: #2980b9;
      transform: scale(1.02);
    }
    button.off {
      background-color: #95a5a6;
    }
    button.off:hover {
      background-color: #7f8c8d;
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
  <h1>✨ PWM 亮度控制 ✨</h1>
  <div class="status">
    💡 当前亮度: <span id="brightnessDisplay" class="brightness-value">)rawliteral" + String(currentBrightness) + R"rawliteral(</span> / 255
  </div>
  <input type="range" id="brightnessSlider" min="0" max="255" value=")rawliteral" + String(currentBrightness) + R"rawliteral(" step="1">
  <br>
  <button id="onBtn">🔆 最亮 (255)</button>
  <button id="offBtn" class="off">💤 熄灭 (0)</button>
  <footer>拖动滑动条 → 实时改变LED亮度</footer>
</div>

<script>
  const slider = document.getElementById('brightnessSlider');
  const display = document.getElementById('brightnessDisplay');
  const onBtn = document.getElementById('onBtn');
  const offBtn = document.getElementById('offBtn');

  async function setBrightness(value) {
    try {
      const response = await fetch('/set?value=' + value);
      if (response.ok) {
        console.log('亮度已更新:', value);
      } else {
        console.error('服务器响应错误');
      }
    } catch (err) {
      console.error('网络错误:', err);
    }
  }

  slider.addEventListener('input', (e) => {
    const val = e.target.value;
    display.innerText = val;
    setBrightness(val);
  });

  onBtn.addEventListener('click', () => {
    slider.value = 255;
    display.innerText = '255';
    setBrightness(255);
  });

  offBtn.addEventListener('click', () => {
    slider.value = 0;
    display.innerText = '0';
    setBrightness(0);
  });
</script>
</body>
</html>
)rawliteral";
  return html;
}

void handleRoot() {
  server.send(200, "text/html; charset=UTF-8", makePage());
}

void handleOn() {
  setBrightness(255);
  server.send(200, "text/plain", "OK");
}

void handleOff() {
  setBrightness(0);
  server.send(200, "text/plain", "OK");
}

void handleSet() {
  if (server.hasArg("value")) {
    int val = server.arg("value").toInt();
    setBrightness(val);
    server.send(200, "text/plain", "OK");
  } else {
    server.send(400, "text/plain", "Missing value");
  }
}

void setup() {
  Serial.begin(115200);

  ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(LED_PIN, PWM_CHANNEL);
  setBrightness(0);

  WiFi.begin(ssid, password);
  Serial.print("正在连接WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi连接成功");
  Serial.print("ESP32 访问地址: http://");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.on("/on", handleOn);
  server.on("/off", handleOff);
  server.on("/set", handleSet);

  server.begin();
  Serial.println("HTTP服务器已启动");
}

void loop() {
  server.handleClient();
}