const int ledPin1 = 22;
const int ledPin2 = 23;

const int freq = 5000;
const int resolution = 8;

int channel1 = 0;
int channel2 = 1;

void setup() {
  Serial.begin(115200);

  ledcSetup(channel1, freq, resolution);
  ledcSetup(channel2, freq, resolution);

  ledcAttachPin(ledPin1, channel1);
  ledcAttachPin(ledPin2, channel2);
}

void loop() {
  for(int dutyCycle = 0; dutyCycle <= 255; dutyCycle++){   
    ledcWrite(channel1, dutyCycle);
    ledcWrite(channel2, 255 - dutyCycle);
    delay(10);
  }

  for(int dutyCycle = 255; dutyCycle >= 0; dutyCycle--){
    ledcWrite(channel1, dutyCycle);
    ledcWrite(channel2, 255 - dutyCycle);
    delay(10);
  }
  
  Serial.println("Breathing cycle completed");
}