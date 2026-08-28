// Owns the load-switched sensor rail (VCC_SENS) and the sensor drivers behind it.
// Reused unchanged by the full node firmware.
#pragma once
#include <Arduino.h>
#include "sensors/Sht41.h"

class SensorManager {
public:
    // Time to wait after enabling VCC_SENS before touching the sensors.
    static constexpr uint16_t RAIL_SETTLE_MS = 50;

    void powerOn();            // enable MIC94069, wait RAIL_SETTLE_MS
    void powerOff();           // disable MIC94069; sensors must be re-begun after powerOn()
    bool isPowered() const { return _powered; }

    // Initialise every sensor on the rail. Returns true if at least one answered.
    bool beginSensors();
    bool sht41Ok() const { return _sht.ok(); }

    Sht41& sht41() { return _sht; }

private:
    Sht41 _sht;
    bool _powered = false;
};
