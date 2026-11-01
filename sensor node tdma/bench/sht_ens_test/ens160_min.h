// Minimal ENS160 driver over Wire: just what the node needs (probe, operating mode,
// temperature/humidity compensation, status, and the AQI / TVOC / eCO2 data registers).
// Register addresses, mode codes, status bits and the compensation formats were checked
// against the SparkFun ENS160 driver (sfe_ens160_regs.h, sfe_ens160.cpp) that the PlatformIO
// bring-up firmware used when this board's ENS160 was verified on the bench at 0x52.
// Reads follow that driver's pattern on MegaCoreX Wire: register pointer write with a STOP,
// then the read. The chip auto-increments the register address inside a multi-byte read.
#pragma once
#include <Arduino.h>
#include <Wire.h>

const uint8_t ENS160_ADDR_LOW = 0x52;   // ADDR pin low: the breakout on this board
const uint8_t ENS160_ADDR_HIGH = 0x53;
const uint16_t ENS160_PART_ID = 0x0160;

const uint8_t ENS160_REG_PART_ID = 0x00;        // 2 bytes, little-endian
const uint8_t ENS160_REG_OPMODE = 0x10;
const uint8_t ENS160_REG_TEMP_IN = 0x13;        // 2 bytes LE, kelvin x 64
const uint8_t ENS160_REG_RH_IN = 0x15;          // 2 bytes LE, %RH x 512
const uint8_t ENS160_REG_DEVICE_STATUS = 0x20;
const uint8_t ENS160_REG_DATA_AQI = 0x21;       // bits 2:0 = AQI-UBA 1 (excellent) .. 5 (unhealthy)
const uint8_t ENS160_REG_DATA_TVOC = 0x22;      // 2 bytes LE, ppb
const uint8_t ENS160_REG_DATA_ECO2 = 0x24;      // 2 bytes LE, ppm

const uint8_t ENS160_OPMODE_DEEP_SLEEP = 0x00;  // about 10 uA; its only exit is IDLE
const uint8_t ENS160_OPMODE_IDLE = 0x01;
const uint8_t ENS160_OPMODE_STANDARD = 0x02;    // gas sensing, about 29 mA, new sample every second
const uint8_t ENS160_OPMODE_RESET = 0xF0;

// DEVICE_STATUS bits
const uint8_t ENS160_STATUS_STATER = 0x40;       // the sensor reports an error
const uint8_t ENS160_STATUS_VALIDITY_gm = 0x0C;  // 0 normal, 1 warm-up, 2 initial start-up, 3 invalid output
const uint8_t ENS160_STATUS_VALIDITY_gp = 2;
const uint8_t ENS160_STATUS_NEWDAT = 0x02;       // a fresh sample sits in the DATA registers

static uint8_t ens160Addr = 0;

static inline bool ens160Write(uint8_t reg, const uint8_t *data, uint8_t n)
{
  Wire.beginTransmission(ens160Addr);
  Wire.write(reg);
  Wire.write(data, n);
  return Wire.endTransmission() == 0;
}

static inline bool ens160Read(uint8_t reg, uint8_t *data, uint8_t n)
{
  Wire.beginTransmission(ens160Addr);
  Wire.write(reg);
  if (Wire.endTransmission() != 0)
    return false;
  if (Wire.requestFrom(ens160Addr, n) != n)
    return false;
  for (uint8_t i = 0; i < n; i++)
    data[i] = Wire.read();
  return true;
}

static inline uint8_t ens160Address() { return ens160Addr; }

// Looks for the sensor at 0x52, then 0x53, by its part id. False if neither answers 0x0160.
static inline bool ens160Probe()
{
  const uint8_t candidates[] = { ENS160_ADDR_LOW, ENS160_ADDR_HIGH };
  for (uint8_t i = 0; i < sizeof(candidates); i++)
  {
    ens160Addr = candidates[i];
    uint8_t id[2];
    if (ens160Read(ENS160_REG_PART_ID, id, 2) && (uint16_t)(id[0] | ((uint16_t)id[1] << 8)) == ENS160_PART_ID)
      return true;
  }
  ens160Addr = 0;
  return false;
}

static inline bool ens160SetMode(uint8_t mode) { return ens160Write(ENS160_REG_OPMODE, &mode, 1); }
static inline bool ens160GetMode(uint8_t &mode) { return ens160Read(ENS160_REG_OPMODE, &mode, 1); }

// The ENS160 corrects its gas readings with the ambient temperature and humidity it is told,
// and assumes 25 C / 50 %RH until then. Fixed-point formats as in the SparkFun driver.
static inline bool ens160SetCompensation(float tempC, float rh)
{
  uint16_t t = (uint16_t)((tempC + 273.15f) * 64.0f + 0.5f);
  uint16_t h = (uint16_t)(rh * 512.0f + 0.5f);
  uint8_t buf[2];
  buf[0] = lowByte(t);
  buf[1] = highByte(t);
  if (!ens160Write(ENS160_REG_TEMP_IN, buf, 2))
    return false;
  buf[0] = lowByte(h);
  buf[1] = highByte(h);
  return ens160Write(ENS160_REG_RH_IN, buf, 2);
}

static inline bool ens160ReadStatus(uint8_t &status) { return ens160Read(ENS160_REG_DEVICE_STATUS, &status, 1); }

// AQI-UBA, TVOC and eCO2 in one read of 0x21..0x25. Reading the data registers clears NEWDAT.
// The outputs are only written when the whole read succeeded.
static inline bool ens160ReadData(uint8_t &aqi, uint16_t &tvoc, uint16_t &eco2)
{
  uint8_t d[5];
  if (!ens160Read(ENS160_REG_DATA_AQI, d, 5))
    return false;
  aqi = d[0] & 0x07;
  tvoc = d[1] | ((uint16_t)d[2] << 8);
  eco2 = d[3] | ((uint16_t)d[4] << 8);
  return true;
}
