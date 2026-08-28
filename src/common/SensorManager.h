// Owns the load-switched sensor rail (VCC_SENS) and the sensor drivers behind it.
// Reused unchanged by the full node firmware.
//
// Precondition: board::init() has run (it configures MIC_ENA as an output).
//
// MegaCoreX Wire has no bus timeout and Wire.begin() cannot re-initialise the peripheral;
// if a sensor holds SDA low the MCU will hang in the next transaction. A GPIO-driven
// 9-clock recovery before Wire.begin() is planned for the node firmware.
//
// Note: on PCB rev 1.0 powerOff() does not fully de-power the sensors — the bus pull-ups
// keep VCC_SENS at ~2.7 V; the SHT41 may keep answering on I2C. Hardware fix for rev 2:
// move R3/R4 to VCC_SENS.
#pragma once
#include <Arduino.h>
#include "sensors/Sht41.h"
#include "sensors/Ens160.h"

class SensorManager {
public:
    // Time to wait after enabling VCC_SENS before touching the sensors.
    static constexpr uint16_t RAIL_SETTLE_MS = 50;

    // The I2C pull-ups on 3V3 back-feed VCC_SENS through the sensors' ESD diodes, so the
    // rail decays slowly after MIC_ENA goes low.
    static constexpr uint16_t RAIL_OFF_MIN_MS = 300;

    void powerOn();            // enable MIC94069, wait RAIL_SETTLE_MS
    void powerOff();           // disable MIC94069; sensors must be re-begun after powerOn()
    bool isPowered() const { return _powered; }

    // Initialise every sensor on the rail. Returns true if at least one answered.
    bool beginSensors();
    bool sht41Ok() const  { return _sht.ok(); }
    bool ens160Ok() const { return _ens.ok(); }

    Sht41&  sht41()  { return _sht; }
    Ens160& ens160() { return _ens; }

private:
    Sht41  _sht;
    Ens160 _ens;
    bool _powered = false;
    uint32_t _offSinceMs = 0;
};
