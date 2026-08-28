#include "SensorManager.h"
#include "board.h"
#include "I2cScan.h"

void SensorManager::powerOn() {
    if (_offSinceMs != 0) {
        const uint32_t elapsed = millis() - _offSinceMs;
        if (elapsed < RAIL_OFF_MIN_MS) delay(RAIL_OFF_MIN_MS - elapsed);
    }
    digitalWrite(board::PIN_MIC_ENA, HIGH);
    delay(RAIL_SETTLE_MS);
    _powered = true;
}

void SensorManager::powerOff() {
    digitalWrite(board::PIN_MIC_ENA, LOW);
    _powered = false;
    _offSinceMs = millis();
    _sht.reset();    // drop stale "ok" state; begin() again after powerOn()
    _ens.reset();
}

bool SensorManager::beginSensors() {
    if (!_powered) return false;
    if (!i2cBusIdle()) return false;
    // both must run: `||` on the calls would short-circuit past _ens.begin()
    const bool shtOk = _sht.begin();
    const bool ensOk = _ens.begin();
    return shtOk || ensOk;
}
