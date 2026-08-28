// sensor_test: bring-up firmware for the sensor rail, I2C bus, SHT41 and ENS160.
#include <Arduino.h>
#include "common/board.h"
#include "common/I2cScan.h"
#include "common/SensorManager.h"

static SensorManager sensors;

static void blink(uint8_t times, uint16_t periodMs) {
    for (uint8_t i = 0; i < times; ++i) {
        digitalWrite(board::PIN_LED, HIGH);
        delay(periodMs / 2);
        digitalWrite(board::PIN_LED, LOW);
        delay(periodMs / 2);
    }
}

static void runScan() {
    Serial.println(F("I2C scan:"));
    const uint8_t n = i2cScan(Serial);
    Serial.print(F("  -> ")); Serial.print(n); Serial.println(F(" device(s)"));
}

void setup() {
    board::init();
    delay(200);  // let the serial monitor attach
    Serial.println();
    Serial.println(F("=== SDP EH sensor node: sensor_test ==="));
    Serial.print(F("build: ")); Serial.print(F(__DATE__)); Serial.print(' '); Serial.println(F(__TIME__));
    blink(3, 200);

    Serial.println(F("Sensor rail: ON"));
    sensors.powerOn();
    runScan();
}

void loop() {
    digitalWrite(board::PIN_LED, HIGH);
    delay(500);
    digitalWrite(board::PIN_LED, LOW);
    delay(500);
}
