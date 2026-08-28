// Owns the load-switched sensor rail (VCC_SENS) and, in later tasks, the sensor drivers.
// Reused unchanged by the full node firmware.
#pragma once
#include <Arduino.h>

class SensorManager {
public:
    // Time to wait after enabling VCC_SENS before touching the sensors.
    static constexpr uint16_t RAIL_SETTLE_MS = 50;

    void powerOn();            // enable MIC94069, wait RAIL_SETTLE_MS
    void powerOff();           // disable MIC94069
    bool isPowered() const { return _powered; }

private:
    bool _powered = false;
};
