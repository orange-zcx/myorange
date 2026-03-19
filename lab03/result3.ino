// 定义LED引脚
const int ledPin = 2;  

// 设置PWM属性
const int freq = 5000;          // 频率 5000Hz
const int resolution = 8;       // 分辨率 8位 (0-255)
const int pwmChannel = 0;       // 选择一个通道 (0-15)

void setup() {
  Serial.begin(115200);

  // 1.0.6 API：配置通道
  ledcSetup(pwmChannel, freq, resolution);
  // 将引脚绑定到通道
  ledcAttachPin(ledPin, pwmChannel);
}

void loop() {
  // 逐渐变亮
  for(int dutyCycle = 0; dutyCycle <= 255; dutyCycle++){   
    // 通过通道写入占空比
    ledcWrite(pwmChannel, dutyCycle);   
    delay(10);
  }

  // 逐渐变暗
  for(int dutyCycle = 255; dutyCycle >= 0; dutyCycle--){
    ledcWrite(pwmChannel, dutyCycle);   
    delay(10);
  }
  
  Serial.println("Breathing cycle completed");
}