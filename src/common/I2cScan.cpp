#include "I2cScan.h"
#include "board.h"
#include <Wire.h>

bool i2cBusIdle() {
    return digitalRead(board::PIN_I2C_SDA) == HIGH && digitalRead(board::PIN_I2C_SCL) == HIGH;
}

uint8_t i2cScan(Print& out) {
    if (!i2cBusIdle()) {
        out.println(F("  (I2C bus not idle: SDA/SCL held low, scan skipped)"));
        return 0;
    }
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
