#include <Servo.h>
Servo myServo;

int const potPin = A0;
int potVal;
int angle;

void setup() {
analogReadResolution(12);
myServo.attach(9);
Serial.begin(9600);

}

void loop() {
potVal = analogRead(potPin);
Serial.print("potVal: ");
Serial.print(potVal);

angle = map(potVal,0,4095,0,179);
Serial.print(", angle: ");
Serial.print(angle);

myServo.write(angle);
delay(15);

}