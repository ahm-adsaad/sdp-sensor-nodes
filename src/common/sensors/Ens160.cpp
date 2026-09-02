#include "Ens160.h"
#include <Wire.h>

bool Ens160::begin() {
    _ok = false;
    _addr = 0;
    _asleep = false;
    const uint8_t candidates[] = { ENS160_ADDRESS_HIGH, ENS160_ADDRESS_LOW };
    for (uint8_t addr : candidates) {
        if (_dev.begin(Wire, addr)) { _addr = addr; break; }
    }
    if (_addr == 0) return false;

    // _addr stays set from here on even if the mode-set calls below fail: the probe
    // succeeded, so callers can still report "found but init failed" instead of
    // "not found" (see Ens160::address()).
    if (!_dev.setOperatingMode(SFE_ENS160_RESET)) return false;
    delay(RESET_SETTLE_MS);
    if (!_dev.setOperatingMode(SFE_ENS160_STANDARD)) return false;
    _ok = true;
    return true;
}

bool Ens160::read(Ens160Reading& r) {
    if (!_ok || _asleep) return false;
    // NEWDAT clear = the DATA registers hold no fresh sample yet. Seen on the bench right
    // after wake(): they read as zeros with the validity flag still at NORMAL.
    if (!_dev.checkDataStatus()) return false;
    const uint8_t flags = _dev.getFlags();
    r.status = ens160StatusFromFlags(flags);
    if (r.status == Ens160Status::Error) return false;
    r.eco2_ppm = _dev.getECO2();
    r.tvoc_ppb = _dev.getTVOC();
    r.aqi_uba  = _dev.getAQI();
    return true;
}

bool Ens160::sleep() {
    if (!_ok) return false;
    if (_asleep) return true;
    if (!_dev.setOperatingMode(SFE_ENS160_DEEP_SLEEP)) return false;
    _asleep = true;
    return true;
}

bool Ens160::wake() {
    if (!_ok) return false;
    if (!_asleep) return true;
    // Deep sleep only answers an OPMODE write, and its only exit is IDLE (fig. 13).
    if (!_dev.setOperatingMode(SFE_ENS160_IDLE)) return false;
    delay(WAKE_SETTLE_MS);
    if (!_dev.setOperatingMode(SFE_ENS160_STANDARD)) return false;
    if (_dev.getOperatingMode() != SFE_ENS160_STANDARD) return false;
    _asleep = false;
    return true;
}
