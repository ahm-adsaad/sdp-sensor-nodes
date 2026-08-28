#include "board.h"
#include <Wire.h>

namespace board {

void init() {
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    pinMode(PIN_MIC_ENA, OUTPUT);
    digitalWrite(PIN_MIC_ENA, LOW);   // sensor rail off until SensorManager::powerOn()

    pinMode(PIN_SX_NSS, OUTPUT);
    digitalWrite(PIN_SX_NSS, HIGH);   // keep the radio off the SPI bus
    pinMode(PIN_SX_RST, INPUT);       // leave SX1276 reset floating (internal pull-up) for now

    Serial.begin(SERIAL_BAUD);
    Wire.begin();
}

}  // namespace board
