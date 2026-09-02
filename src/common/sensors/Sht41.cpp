#include "Sht41.h"
#include <Wire.h>

bool Sht41::begin() {
    _ok = false;
    _serial = 0;
    _asleep = false;
    _dev.begin(Wire, I2C_ADDRESS);
    if (_dev.softReset() != 0) return false;
    delay(2);  // datasheet: soft reset completes within 1 ms
    if (_dev.serialNumber(_serial) != 0) return false;
    _ok = true;
    return true;
}

bool Sht41::read(float& tempC, float& rh) {
    if (!_ok || _asleep) return false;
    return _dev.measureHighPrecision(tempC, rh) == 0;
}

bool Sht41::sleep() {
    if (!_ok) return false;
    _asleep = true;
    return true;
}

bool Sht41::wake() {
    if (!_ok) return false;
    _asleep = false;
    return true;
}
