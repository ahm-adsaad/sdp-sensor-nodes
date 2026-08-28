#pragma once
#include <Arduino.h>

// True if SDA and SCL are both idle-high. False means a device is holding the bus low,
// which would hang a Wire transaction (MegaCoreX Wire has no bus timeout).
bool i2cBusIdle();

// Probe every 7-bit I2C address from 0x08 to 0x77 on Wire.
// Prints one line per responding device to `out` and returns how many responded.
uint8_t i2cScan(Print& out);
