#define TOUCH_PIN 4
#define LED_PIN 2

int threshold = 20;

enum SpeedLevel {
  LEVEL_SLOW,
  LEVEL_MEDIUM,
  LEVEL_FAST
};

SpeedLevel currentLevel = LEVEL_SLOW;

const int maxBrightness = 255;
const int pwmFreq = 5000;
const int pwmResolution = 8;
const int pwmChannel = 0;

const unsigned long breathCycle[3] = {
  8000,
  4000,
  2000
};

unsigned long lastTouchTime = 0;
const unsigned long debounceDelay = 300;

unsigned long lastUpdateTime = 0;
float currentAngle = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  ledcSetup(pwmChannel, pwmFreq, pwmResolution);
  ledcAttachPin(LED_PIN, pwmChannel);
  ledcWrite(pwmChannel, 0);
  
  Serial.println("=== Touch Breathing Light ===");
  Serial.println("Touch the sensor to change speed level");
  showCurrentLevel();
}

void loop() {
  handleTouchInput();
  updateBreathingEffect();
  delay(10);
}

void handleTouchInput() {
  int touchValue = touchRead(TOUCH_PIN);
  
  if (touchValue < threshold) {
    if (millis() - lastTouchTime > debounceDelay) {
      lastTouchTime = millis();
      switchLevel();
      showCurrentLevel();
      blinkFeedback();
    }
  }
}

void switchLevel() {
  switch(currentLevel) {
    case LEVEL_SLOW:
      currentLevel = LEVEL_MEDIUM;
      break;
    case LEVEL_MEDIUM:
      currentLevel = LEVEL_FAST;
      break;
    case LEVEL_FAST:
      currentLevel = LEVEL_SLOW;
      break;
  }
  
  resetBreathingPhase();
}

void resetBreathingPhase() {
  int currentBrightness = ledcRead(pwmChannel);
  
  if (currentBrightness >= 0 && currentBrightness <= maxBrightness) {
    float ratio = (float)currentBrightness / maxBrightness;
    if (ratio >= 0.99) ratio = 0.99;
    
    currentAngle = asin(ratio);
    
    static int lastBrightness = 0;
    if (currentBrightness > lastBrightness) {
      currentAngle = currentAngle;
    } else {
      currentAngle = PI - currentAngle;
    }
    lastBrightness = currentBrightness;
  } else {
    currentAngle = 0;
  }
  
  lastUpdateTime = millis();
}

void updateBreathingEffect() {
  unsigned long currentTime = millis();
  unsigned long cycleDuration = breathCycle[currentLevel];
  
  unsigned long elapsed = (currentTime - lastUpdateTime) % cycleDuration;
  
  float angle = (float)elapsed / cycleDuration * PI;
  
  int brightness = (int)(sin(angle) * maxBrightness);
  
  ledcWrite(pwmChannel, brightness);
}

void blinkFeedback() {
  int currentBrightness = ledcRead(pwmChannel);
  
  ledcWrite(pwmChannel, maxBrightness);
  delay(50);
  
  ledcWrite(pwmChannel, currentBrightness);
}

void showCurrentLevel() {
  Serial.print("Current Level: ");
  switch(currentLevel) {
    case LEVEL_SLOW:
      Serial.print("1 (Slow)");
      Serial.print(" - Cycle: ");
      Serial.print(breathCycle[LEVEL_SLOW] / 1000);
      Serial.println(" seconds");
      break;
    case LEVEL_MEDIUM:
      Serial.print("2 (Medium)");
      Serial.print(" - Cycle: ");
      Serial.print(breathCycle[LEVEL_MEDIUM] / 1000);
      Serial.println(" seconds");
      break;
    case LEVEL_FAST:
      Serial.print("3 (Fast)");
      Serial.print(" - Cycle: ");
      Serial.print(breathCycle[LEVEL_FAST] / 1000);
      Serial.println(" seconds");
      break;
  }
}