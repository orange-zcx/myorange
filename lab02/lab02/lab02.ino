// 定义LED引脚，ESP32通常板载LED连接在GPIO 2
const int ledPin = 2; 

void setup() {
  // 初始化串口通信，设置波特率为115200
  Serial.begin(115200);
  // 将LED引脚设置为输出模式
  pinMode(ledPin, OUTPUT);
}

void loop() {
  digitalWrite(ledPin, HIGH);  // 点亮LED
  Serial.println("LED ON");    // 串口输出提示
  delay(1000);                 // 保持1秒（1000毫秒）
  
  digitalWrite(ledPin, LOW);   // 熄灭LED
  Serial.println("LED OFF");   // 串口输出提示
  delay(1000);                 // 保持1秒
}