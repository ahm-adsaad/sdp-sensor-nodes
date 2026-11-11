// small ENS160 driver over Wire, only the stuff the node needs.
// reg addresses and formats are the same as in the SparkFun ENS160 library
#pragma once
#include <Arduino.h>
#include <Wire.h>

const uint8_t ENS160_ADDR_LOW = 0x52;   // i2c addr w/ ADDR pin low (our breakout)
const uint8_t ENS160_ADDR_HIGH = 0x53;  // i2c addr w/ ADDR pin high
const uint16_t ENS160_PART_ID = 0x0160; // what the part id reg should read

// registers (2 byte ones are little-endian)
const uint8_t ENS160_REG_PART_ID = 0x00;        // 2 bytes
const uint8_t ENS160_REG_OPMODE = 0x10;
const uint8_t ENS160_REG_TEMP_IN = 0x13;        // 2 bytes, kelvin x 64
const uint8_t ENS160_REG_RH_IN = 0x15;          // 2 bytes, %RH x 512
const uint8_t ENS160_REG_DEVICE_STATUS = 0x20;
const uint8_t ENS160_REG_DATA_AQI = 0x21;       // bits 2:0 = AQI 1 (best) .. 5 (worst)
const uint8_t ENS160_REG_DATA_TVOC = 0x22;      // 2 bytes, ppb
const uint8_t ENS160_REG_DATA_ECO2 = 0x24;      // 2 bytes, ppm

// operating modes
const uint8_t ENS160_OPMODE_DEEP_SLEEP = 0x00;  // abt 10 uA
const uint8_t ENS160_OPMODE_IDLE = 0x01;
const uint8_t ENS160_OPMODE_STANDARD = 0x02;    // gas sensing, abt 29 mA, 1 sample per sec
const uint8_t ENS160_OPMODE_RESET = 0xF0;

// status reg bits
const uint8_t ENS160_STATUS_STATER = 0x40;       // sensor error
const uint8_t ENS160_STATUS_VALIDITY_gm = 0x0C;  // 0 normal, 1 warm-up, 2 start-up, 3 invalid
const uint8_t ENS160_STATUS_VALIDITY_gp = 2;     // shift for the validity bits
const uint8_t ENS160_STATUS_NEWDAT = 0x02;       // new sample is ready

static uint8_t ens160Addr = 0;  // addr the sensor was found at, 0 = not found

// write n bytes to a reg, true if the sensor ACKed
static inline bool ens160Write(uint8_t reg, const uint8_t *data, uint8_t n)
{
  Wire.beginTransmission(ens160Addr);
  Wire.write(reg);
  Wire.write(data, n);
  return Wire.endTransmission() == 0;
}

// read n bytes starting at a reg, true if it worked
static inline bool ens160Read(uint8_t reg, uint8_t *data, uint8_t n)
{
  Wire.beginTransmission(ens160Addr);
  Wire.write(reg);  // tell it which reg
  if (Wire.endTransmission() != 0)
    return false;  // no ACK
  if (Wire.requestFrom(ens160Addr, n) != n)
    return false;  // didnt get all the bytes
  for (uint8_t i = 0; i < n; i++)
    data[i] = Wire.read();
  return true;
}

static inline uint8_t ens160Address() { return ens160Addr; }

// look for the sensor at 0x52 then 0x53 by checking the part id
static inline bool ens160Probe()
{
  const uint8_t candidates[] = { ENS160_ADDR_LOW, ENS160_ADDR_HIGH };
  for (uint8_t i = 0; i < sizeof(candidates); i++)
  {
    ens160Addr = candidates[i];
    uint8_t id[2];
    if (ens160Read(ENS160_REG_PART_ID, id, 2) && (uint16_t)(id[0] | ((uint16_t)id[1] << 8)) == ENS160_PART_ID)
      return true;  // found it
  }
  ens160Addr = 0;  // not found
  return false;
}

static inline bool ens160SetMode(uint8_t mode) { return ens160Write(ENS160_REG_OPMODE, &mode, 1); }
static inline bool ens160GetMode(uint8_t &mode) { return ens160Read(ENS160_REG_OPMODE, &mode, 1); }

// give the sensor the real temp + hum so it can correct its gas readings (default is 25 C / 50 %)
static inline bool ens160SetCompensation(float tempC, float rh)
{
  uint16_t t = (uint16_t)((tempC + 273.15f) * 64.0f + 0.5f);  // C -> kelvin x 64
  uint16_t h = (uint16_t)(rh * 512.0f + 0.5f);                // %RH x 512
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

// read AQI, TVOC and eCO2 in 1 go (regs 0x21..0x25). reading them clears NEWDAT
static inline bool ens160ReadData(uint8_t &aqi, uint16_t &tvoc, uint16_t &eco2)
{
  uint8_t d[5];
  if (!ens160Read(ENS160_REG_DATA_AQI, d, 5))
    return false;
  aqi = d[0] & 0x07;                    // only bits 2:0
  tvoc = d[1] | ((uint16_t)d[2] << 8);  // little-endian
  eco2 = d[3] | ((uint16_t)d[4] << 8);
  return true;
}
