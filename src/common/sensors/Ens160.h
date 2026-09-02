// Thin wrapper over the SparkFun ENS160 driver. Probes 0x53 then 0x52.
#pragma once
#include <Arduino.h>
#include <SparkFun_ENS160.h>
#include "Ens160Status.h"

struct Ens160Reading {
    uint16_t eco2_ppm = 0;
    uint16_t tvoc_ppb = 0;
    uint8_t  aqi_uba  = 0;   // 1 (excellent) .. 5 (unhealthy)
    Ens160Status status = Ens160Status::Error;
};

class Ens160 {
public:
    // Find the sensor (0x53, then 0x52), reset it and put it in STANDARD gas-sensing mode.
    // Returns true if found. Safe to call again after a power cycle.
    bool begin();

    // Read validity flag + eCO2/TVOC/AQI. Returns false if the sensor is absent, asleep, or the
    // status register could not be read. Values are still filled in when status != Normal;
    // callers decide whether to trust them via ens160StatusIsValid(r.status).
    // Does not wait for NEWDAT; the node firmware should call `_dev.checkDataStatus()`
    // (or poll) before trusting a sample taken right after wake.
    bool read(Ens160Reading& r);

    // Per-sensor power control while VCC_SENS stays on (datasheet table 3 / fig. 13):
    // STANDARD draws ~29 mA, DEEP SLEEP ~10 uA. sleep() writes OPMODE 0x00. The hot plate
    // cools, so after wake() the sensor reports WARMUP again and needs ~3 min before its
    // outputs are valid, exactly like a power-up. wake() steps DEEP SLEEP -> IDLE -> STANDARD
    // (IDLE is the only exit from deep sleep) and reads OPMODE back to prove the part answered.
    // Both return false if the sensor is absent or did not ACK; read() is refused while asleep.
    bool sleep();
    bool wake();
    bool asleep() const { return _asleep; }

    bool ok() const { return _ok; }
    uint8_t address() const { return _addr; }

    // forget presence state after a rail power cycle; begin() re-binds the driver
    void reset() { _addr = 0; _ok = false; _asleep = false; }

    Ens160() = default;
    Ens160(const Ens160&) = delete;
    Ens160& operator=(const Ens160&) = delete;

private:
    static constexpr uint16_t RESET_SETTLE_MS = 100;
    static constexpr uint16_t WAKE_SETTLE_MS  = 10;   // dwell in IDLE before STANDARD; datasheet gives no figure
    SparkFun_ENS160 _dev;
    uint8_t _addr = 0;
    bool _ok = false;
    bool _asleep = false;
};
