const int ledPin = 2;         
int ledState = LOW;            
unsigned long previousMillis = 0; 
const long interval = 500;    

void setup() {
  Serial.begin(115200);       
  pinMode(ledPin, OUTPUT);     
}

void loop() {
  unsigned long currentMillis = millis();  

  
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;  

    
    if (ledState == LOW) {
      ledState = HIGH;
      Serial.println("LED ON");
    } else {
      ledState = LOW;
      Serial.println("LED OFF");
    }
    digitalWrite(ledPin, ledState); 
  }

}