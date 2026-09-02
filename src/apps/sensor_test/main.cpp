// sensor_test: bring-up firmware for the sensor rail, I2C bus, SHT41 and ENS160.
#include <Arduino.h>
#include "common/board.h"
#include "common/I2cScan.h"
#include "common/SensorManager.h"

static constexpr uint32_t READ_PERIOD_MS = 2000;

static SensorManager sensors;
static uint32_t lastReadMs = 0;

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

static void initSensors() {
    sensors.beginSensors();
    Serial.print(F("SHT41:  "));
    if (sensors.sht41Ok()) {
        Serial.print(F("OK  serial=0x")); Serial.println(sensors.sht41().serialNumber(), HEX);
    } else {
        Serial.println(F("NOT FOUND"));
    }
    Serial.print(F("ENS160: "));
    if (sensors.ens160().address() == 0) {
        Serial.println(F("NOT FOUND"));
    } else if (!sensors.ens160Ok()) {
        Serial.print(F("FOUND at 0x")); Serial.print(sensors.ens160().address(), HEX);
        Serial.println(F(" but init failed"));
    } else {
        Serial.print(F("OK  addr=0x")); Serial.println(sensors.ens160().address(), HEX);
    }
}

static void printReadings() {
    Serial.print(F("t=")); Serial.print(millis() / 1000.0f, 1); Serial.print(F("s | SHT41: "));
    float t = 0, h = 0;
    if (sensors.sht41().asleep()) {
        Serial.print(F("asleep"));
    } else if (sensors.sht41().read(t, h)) {
        Serial.print(t, 2); Serial.print(F(" C ")); Serial.print(h, 1); Serial.print(F(" %RH"));
    } else {
        Serial.print(F("--"));
    }

    Serial.print(F(" | ENS160: "));
    Ens160Reading r;
    if (sensors.ens160().asleep()) {
        Serial.print(F("asleep"));
    } else if (sensors.ens160().read(r)) {
        Serial.print(F("eCO2=")); Serial.print(r.eco2_ppm); Serial.print(F(" ppm TVOC="));
        Serial.print(r.tvoc_ppb); Serial.print(F(" ppb AQI=")); Serial.print(r.aqi_uba);
        Serial.print(F(" status=")); Serial.print(ens160StatusName(r.status));
    } else {
        Serial.print(F("--"));
    }
    Serial.println();
}

static void printHelp() {
    Serial.println(F("commands:  p = toggle sensor rail power   s = I2C scan"));
    Serial.println(F("           t = SHT41 sleep/wake   e = ENS160 sleep/wake   ? = help"));
}

// Toggle one sensor between awake and asleep while the rail stays on.
template <typename Sensor>
static void toggleSleep(const __FlashStringHelper* name, Sensor& s) {
    Serial.print(name); Serial.print(F(": "));
    if (!s.ok()) {
        Serial.println(F("not initialised"));
    } else if (s.asleep()) {
        Serial.println(s.wake() ? F("awake") : F("wake FAILED"));
    } else {
        Serial.println(s.sleep() ? F("asleep") : F("sleep FAILED"));
    }
}

static void handleCommand(char c) {
    switch (c) {
        case 'p':
            if (sensors.isPowered()) {
                sensors.powerOff();
                Serial.println(F("Sensor rail: OFF"));
            } else {
                Serial.println(F("Sensor rail: ON"));
                sensors.powerOn();
                initSensors();
            }
            break;
        case 's':
            runScan();
            break;
        case 't':
            toggleSleep(F("SHT41"), sensors.sht41());
            break;
        case 'e':
            toggleSleep(F("ENS160"), sensors.ens160());
            break;
        case '?':
            printHelp();
            break;
        case '\r':
        case '\n':
        case ' ':
            break;  // ignore line endings from the terminal
        default:
            Serial.print(F("unknown command '")); Serial.print(c); Serial.println(F("' (try ?)"));
            break;
    }
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
    initSensors();
    printHelp();
    lastReadMs = millis();
}

void loop() {
    while (Serial.available() > 0) {
        handleCommand(static_cast<char>(Serial.read()));
    }

    const uint32_t now = millis();
    if (now - lastReadMs >= READ_PERIOD_MS) {
        lastReadMs = now;
        static bool ledOn = false;
        ledOn = !ledOn;
        digitalWrite(board::PIN_LED, ledOn ? HIGH : LOW);
        if (sensors.isPowered()) {
            printReadings();
        } else {
            Serial.print(F("t=")); Serial.print(now / 1000.0f, 1); Serial.println(F("s | rail OFF"));
        }
    }
}
