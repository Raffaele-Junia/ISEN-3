const int sensorPin = A0;
const float baselineTemp = 24.0;
int sensorval = 0;

void setup() {
  Serial.begin(9600);

  for (int pinNumber = 5; pinNumber < 8; pinNumber++) {
    pinMode(pinNumber, OUTPUT);
    digitalWrite(pinNumber, LOW);
  }
}

void loop() {
  sensorval = analogRead(sensorPin);

  Serial.print("Sensor Value: ");
  Serial.print(sensorval);

  float voltage = (sensorval / 1024.0) * 5.0;

  Serial.print(", Volt: ");
  Serial.print(voltage);

  float temperature = (voltage - 0.5) * 100;

  Serial.print(", degrees C: ");
  Serial.println(temperature);

  if (temperature < baselineTemp + 2) {
    digitalWrite(5, LOW);
    digitalWrite(6, LOW);
    digitalWrite(7, LOW);
  }
  else if (temperature < baselineTemp + 4) {
    digitalWrite(5, HIGH);
    digitalWrite(6, LOW);
    digitalWrite(7, LOW);
  }
  else if (temperature < baselineTemp + 6) {
    digitalWrite(5, HIGH);
    digitalWrite(6, HIGH);
    digitalWrite(7, LOW);
  }
  else {
    digitalWrite(5, HIGH);
    digitalWrite(6, HIGH);
    digitalWrite(7, HIGH);
  }

  delay(1000);
}
