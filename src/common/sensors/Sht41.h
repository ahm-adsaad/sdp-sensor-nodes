// Thin wrapper over the Sensirion SHT4x driver for the SHT41 at 0x44.
#pragma once
#include <Arduino.h>
#include <SensirionI2cSht4x.h>

class Sht41 {
public:
    static constexpr uint8_t I2C_ADDRESS = SHT41_I2C_ADDR_44;

    // Soft-reset the sensor and read its serial number to prove it is present.
    // Returns true if the sensor answered. Safe to call again after a power cycle.
    bool begin();

    // Single-shot high-precision measurement (~10 ms). Returns false on I2C/CRC error.
    bool read(float& tempC, float& rh);

    bool ok() const { return _ok; }
    uint32_t serialNumber() const { return _serial; }

private:
    SensirionI2cSht4x _dev;
    uint32_t _serial = 0;
    bool _ok = false;
};
