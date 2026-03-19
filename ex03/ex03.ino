const int ledPin = 2;
const unsigned long shortUnit = 200;
const unsigned long longUnit = 600;
const int stepCount = 18;
const boolean stepState[stepCount] = {
  HIGH, LOW, HIGH, LOW, HIGH, LOW,
  HIGH, LOW, HIGH, LOW, HIGH, LOW,
  HIGH, LOW, HIGH, LOW, HIGH, LOW
};
const unsigned long stepDuration[stepCount] = {
  shortUnit, shortUnit, shortUnit, shortUnit, shortUnit, shortUnit,
  longUnit,  longUnit,  longUnit,  longUnit,  longUnit,  longUnit,
  shortUnit, shortUnit, shortUnit, shortUnit, shortUnit, shortUnit
};
unsigned long previousMillis = 0;
int currentStep = 0;
int systemState = 0;
unsigned long intervalStart = 0;
const unsigned long sosInterval = 10000;

void setup() {
  Serial.begin(115200);
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);
  previousMillis = millis();
  currentStep = 0;
  systemState = 0;
  digitalWrite(ledPin, stepState[currentStep]);
  printStepInfo(currentStep);
}

void loop() {
  unsigned long currentMillis = millis();

  if (systemState == 0) {
    if (currentMillis - previousMillis >= stepDuration[currentStep]) {
      currentStep++;
      if (currentStep >= stepCount) {
        systemState = 1;
        intervalStart = currentMillis;
        digitalWrite(ledPin, LOW);
        Serial.println("--- SOS finished, waiting 10 seconds ---");
      } else {
        previousMillis = currentMillis;
        digitalWrite(ledPin, stepState[currentStep]);
        printStepInfo(currentStep);
      }
    }
  } 
  else if (systemState == 1) {
    if (currentMillis - intervalStart >= sosInterval) {
      systemState = 0;
      currentStep = 0;
      previousMillis = currentMillis;
      digitalWrite(ledPin, stepState[0]);
      printStepInfo(0);
      Serial.println("--- Restart SOS ---");
    }
  }
}

void printStepInfo(int step) {
  Serial.print("Step ");
  Serial.print(step);
  Serial.print(": LED ");
  Serial.println(stepState[step] == HIGH ? "ON" : "OFF");
}