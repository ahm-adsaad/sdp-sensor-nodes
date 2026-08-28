// ENS160 data-validity status, decoded from the DEVICE_STATUS register's VALIDITY_FLAG.
// Pure header: no Arduino dependency so it can be unit-tested on the host.
#pragma once
#include <stdint.h>

enum class Ens160Status : uint8_t {
    Normal         = 0,    // outputs valid
    Warmup         = 1,    // first ~3 min after power-up: outputs settling
    InitialStartup = 2,    // first 1 h of the sensor's life: outputs not trustworthy
    Invalid        = 3,    // sensor reports invalid output
    Error          = 0xFF  // I2C read failed or unknown code
};

inline Ens160Status ens160StatusFromFlags(uint8_t flags) {
    switch (flags) {
        case 0:  return Ens160Status::Normal;
        case 1:  return Ens160Status::Warmup;
        case 2:  return Ens160Status::InitialStartup;
        case 3:  return Ens160Status::Invalid;
        default: return Ens160Status::Error;
    }
}

inline const char* ens160StatusName(Ens160Status s) {
    switch (s) {
        case Ens160Status::Normal:         return "NORMAL";
        case Ens160Status::Warmup:         return "WARMUP";
        case Ens160Status::InitialStartup: return "STARTUP";
        case Ens160Status::Invalid:        return "INVALID";
        case Ens160Status::Error:          return "ERROR";
    }
    return "ERROR";  // unreachable: all enumerators handled above
}

inline bool ens160StatusIsValid(Ens160Status s) { return s == Ens160Status::Normal; }
