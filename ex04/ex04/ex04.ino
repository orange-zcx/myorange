#define TOUCH_PIN 4
#define LED_PIN 2
#define THRESHOLD 20
#define DEBOUNCE_TIME 200 

volatile bool ledState = false;
volatile unsigned long lastTouchTime = 0;

void gotTouch() {
  unsigned long now = millis();
  
  if (now - lastTouchTime > DEBOUNCE_TIME) {
    lastTouchTime = now;
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  touchAttachInterrupt(TOUCH_PIN, gotTouch, THRESHOLD);
}

void loop() {
  delay(100);
}