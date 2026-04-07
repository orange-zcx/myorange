// 触摸引脚 (T0对应GPIO4)
#define TOUCH_PIN 4
// LED引脚 (ESP32 DevKit板载LED通常是GPIO2)
#define LED_PIN 2

// 触摸阈值（通过串口监视器观察调整，未触摸时数值较大，触摸时变小）
int threshold = 30;

// 速度档位变量（1~3）
int speedLevel = 1;        // 当前档位
const int maxLevel = 3;    // 最大档位

// 呼吸灯参数
int dutyCycle = 0;          // 当前占空比 (0~255)
int direction = 1;          // 1=递增，-1=递减
int step = 1;               // 每次变化的步长（固定为1）
int delayTime = 10;         // 当前档位对应的延时(ms)

// 触摸检测相关变量
bool lastTouchState = false;        // 上一次触摸状态
unsigned long lastDebounceTime = 0; // 防抖时间记录
const unsigned long debounceDelay = 50; // 防抖延时(ms)

// PWM 通道设置（旧版 API）
const int pwmChannel = 0;     // 使用通道 0
const int pwmFreq = 5000;     // 频率 5000Hz
const int pwmResolution = 8;  // 分辨率 8位 (0-255)

// 根据档位更新呼吸灯参数（这里只改变延时时间）
void updateSpeedParameters() {
  switch (speedLevel) {
    case 1:
      delayTime = 10;   // 慢速呼吸
      break;
    case 2:
      delayTime = 5;    // 中速呼吸
      break;
    case 3:
      delayTime = 2;    // 快速呼吸
      break;
    default:
      delayTime = 10;
      break;
  }
  Serial.print("Speed level changed to ");
  Serial.print(speedLevel);
  Serial.print(", delayTime = ");
  Serial.println(delayTime);
}

// 非阻塞触摸检测：返回true表示有效触摸按下瞬间，同时进行防抖
bool checkTouch() {
  // 读取当前触摸值
  int touchValue = touchRead(TOUCH_PIN);
  bool currentTouchState = (touchValue < threshold);  // 触摸时数值变小

  bool validTouch = false;

  // 检测上升沿：上一次未触摸，当前已触摸
  if (currentTouchState && !lastTouchState) {
    unsigned long now = millis();
    // 防抖：确保在防抖间隔后才确认
    if (now - lastDebounceTime >= debounceDelay) {
      lastDebounceTime = now;
      validTouch = true;
    }
  }

  // 更新上一次触摸状态
  lastTouchState = currentTouchState;

  return validTouch;
}

void setup() {
  Serial.begin(115200);
  delay(1000);   // 等待串口稳定

  // 旧版 PWM 初始化：配置通道并绑定引脚
  ledcSetup(pwmChannel, pwmFreq, pwmResolution);
  ledcAttachPin(LED_PIN, pwmChannel);

  // 初始化LED状态（呼吸灯从灭开始）
  ledcWrite(pwmChannel, dutyCycle);
  
  // 输出初始档位信息
  updateSpeedParameters();
}

void loop() {
  // 1. 检测触摸事件，若有效则切换档位
  if (checkTouch()) {
    // 循环切换档位：1->2->3->1...
    speedLevel++;
    if (speedLevel > maxLevel) speedLevel = 1;
    updateSpeedParameters();  // 更新呼吸灯延时参数
  }

  // 2. 呼吸灯渐变逻辑
  dutyCycle += step * direction;

  // 边界检查并反转方向
  if (dutyCycle >= 255) {
    dutyCycle = 255;
    direction = -1;
  } else if (dutyCycle <= 0) {
    dutyCycle = 0;
    direction = 1;
  }

  // 输出当前占空比（通过通道写入）
  ledcWrite(pwmChannel, dutyCycle);

  // 根据当前档位的延时时间等待（使呼吸节奏变化）
  delay(delayTime);

  // 可选：每500ms打印一次触摸值（调试用，不影响主循环）
  static unsigned long lastPrintTime = 0;
  if (millis() - lastPrintTime >= 500) {
    int touchValue = touchRead(TOUCH_PIN);
    Serial.print("Touch value: ");
    Serial.println(touchValue);
    lastPrintTime = millis();
  }
}