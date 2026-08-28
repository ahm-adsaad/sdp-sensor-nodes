#include "Ens160.h"
#include <Wire.h>

bool Ens160::begin() {
    _ok = false;
    _addr = 0;
    const uint8_t candidates[] = { ENS160_ADDRESS_HIGH, ENS160_ADDRESS_LOW };
    for (uint8_t addr : candidates) {
        if (_dev.begin(Wire, addr)) { _addr = addr; break; }
    }
    if (_addr == 0) return false;

    if (!_dev.setOperatingMode(SFE_ENS160_RESET)) return false;
    delay(RESET_SETTLE_MS);
    if (!_dev.setOperatingMode(SFE_ENS160_STANDARD)) return false;
    _ok = true;
    return true;
}

bool Ens160::read(Ens160Reading& r) {
    if (!_ok) return false;
    const uint8_t flags = _dev.getFlags();
    r.status = ens160StatusFromFlags(flags);
    if (r.status == Ens160Status::Error) return false;
    r.eco2_ppm = _dev.getECO2();
    r.tvoc_ppb = _dev.getTVOC();
    r.aqi_uba  = _dev.getAQI();
    return true;
}
