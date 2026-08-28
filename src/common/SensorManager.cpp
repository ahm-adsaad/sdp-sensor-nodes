#include "SensorManager.h"
#include "board.h"

void SensorManager::powerOn() {
    digitalWrite(board::PIN_MIC_ENA, HIGH);
    delay(RAIL_SETTLE_MS);
    _powered = true;
}

void SensorManager::powerOff() {
    digitalWrite(board::PIN_MIC_ENA, LOW);
    _powered = false;
}
