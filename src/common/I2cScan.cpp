#include "I2cScan.h"
#include <Wire.h>

uint8_t i2cScan(Print& out) {
    uint8_t found = 0;
    for (uint8_t addr = 0x08; addr <= 0x77; ++addr) {
        Wire.beginTransmission(addr);
        const uint8_t err = Wire.endTransmission();
        if (err == 0) {
            out.print(F("  found 0x"));
            if (addr < 0x10) out.print('0');
            out.println(addr, HEX);
            ++found;
        }
    }
    if (found == 0) out.println(F("  (no devices)"));
    return found;
}
