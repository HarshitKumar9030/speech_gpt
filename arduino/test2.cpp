#include <SoftwareSerial.h> // Library for SoftwareSerial

// Ultrasonic sensor pins (existing)
const int trigPin = 9;
const int echoPin = 10;

// L298N motor driver pins
const int ENA = 5;  // Enable A - Right Motor
const int ENB = 6;  // Enable B - Left Motor
const int IN1 = 2;  // Right Motor control 1
const int IN2 = 3;  // Right Motor control 2
const int IN3 = 4;  // Left Motor control 1
const int IN4 = 7;  // Left Motor control 2

// LED indicators
const int frontLED = 8;
const int leftLED = 11;
const int rightLED = 12;

// Bluetooth module pins (connect these to the Bluetooth module)
const int bluetoothTX = 10; // Bluetooth TX to Arduino RX
const int bluetoothRX = 11; // Bluetooth RX to Arduino TX

// Constants
const float SAFE_DISTANCE = 20.0; // Safe distance in cm
const int MOTOR_SPEED = 200;      // Motor speed (0-255)

char bluetoothCommand;

// Initialize SoftwareSerial for Bluetooth communication
SoftwareSerial bluetooth(bluetoothRX, bluetoothTX); // RX, TX

void setup() {
  // Initialize Serial for debugging
  Serial.begin(9600);
  
  // Initialize Bluetooth communication
  bluetooth.begin(9600);
  
  // Ultrasonic sensor setup (existing)
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  
  // Motor control setup
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  
  // LED setup
  pinMode(frontLED, OUTPUT);
  pinMode(leftLED, OUTPUT);
  pinMode(rightLED, OUTPUT);
}

float getDistance() {
  // Existing ultrasonic code
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  long duration = pulseIn(echoPin, HIGH);
  float distanceCm = duration * 0.034 / 2;
  
  return distanceCm;
}

void moveForward() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
  analogWrite(ENA, MOTOR_SPEED);
  analogWrite(ENB, MOTOR_SPEED);
  digitalWrite(frontLED, HIGH);
  digitalWrite(leftLED, LOW);
  digitalWrite(rightLED, LOW);
}

void moveBackward() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
  analogWrite(ENA, MOTOR_SPEED);
  analogWrite(ENB, MOTOR_SPEED);
  digitalWrite(frontLED, HIGH);
  digitalWrite(leftLED, HIGH);
  digitalWrite(rightLED, HIGH);
}

void turnLeft() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
  analogWrite(ENA, MOTOR_SPEED);
  analogWrite(ENB, MOTOR_SPEED);
  digitalWrite(frontLED, LOW);
  digitalWrite(leftLED, HIGH);
  digitalWrite(rightLED, LOW);
}

void turnRight() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
  analogWrite(ENA, MOTOR_SPEED);
  analogWrite(ENB, MOTOR_SPEED);
  digitalWrite(frontLED, LOW);
  digitalWrite(leftLED, LOW);
  digitalWrite(rightLED, HIGH);
}

void stopMotors() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
  analogWrite(ENA, 0);
  analogWrite(ENB, 0);
  digitalWrite(frontLED, LOW);
  digitalWrite(leftLED, LOW);
  digitalWrite(rightLED, LOW);
}

void loop() {
  float distance = getDistance();
  Serial.println(distance); // Debug output
  
  // Check for Bluetooth commands
  if (bluetooth.available() > 0) {
    bluetoothCommand = bluetooth.read();
    
    // Process commands and check distance
    if (distance > SAFE_DISTANCE) {
      switch (bluetoothCommand) {
        case 'F': // Forward
          moveForward();
          break;
        case 'B': // Backward
          moveBackward();
          break;
        case 'L': // Left
          turnLeft();
          break;
        case 'R': // Right
          turnRight();
          break;
        case 'S': // Stop
          stopMotors();
          break;
      }
    } else {
      // If too close to an obstacle, only allow backward movement or stopping
      if (bluetoothCommand == 'B') {
        moveBackward();
      } else if (bluetoothCommand == 'S') {
        stopMotors();
      } else {
        stopMotors();
      }
    }
  }
  
  delay(50); // Small delay to prevent overwhelming the serial buffer
}
