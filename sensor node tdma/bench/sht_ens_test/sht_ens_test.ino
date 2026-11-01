// Basic SHT41 + ENS160 test for the rev-2 node: no LoRa, no sleep, everything printed on Serial
// at 115200. Puts the radio to sleep, powers J3 and J4 with the same pulsed ramp the TDMA firmware
// uses (a plain switch-on of the ENS160 board browns the node out), finds each sensor on either
// header and prints temperature, humidity, TVOC, eCO2 and AQI every 2 s.
// Build: MegaCoreX, ATmega4809, 48 pin standard, internal 8 MHz, BOD 2.6 V, programmer JTAG2UPDI.
// Libraries: Adafruit SHT4x. ens160_min.h sits next to this file.
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_SHT4x.h>
#include "ens160_min.h"

const uint8_t PIN_RAIL_A = PIN_PD6;  // J3 enable, I2C on PA2/PA3
const uint8_t PIN_RAIL_B = PIN_PC1;  // J4 enable, I2C on PC2/PC3
const uint8_t PIN_RADIO_NSS = PIN_PA7;
const uint8_t PIN_RADIO_RST = PIN_PF3;
const uint8_t BUS_J3 = 0, BUS_J4 = 1;  // Wire.swap() states

Adafruit_SHT4x sht4;
bool shtFound = false, ensFound = false, ensSensing = false;
uint8_t shtBus = BUS_J3, ensBus = BUS_J3, currentBus = 0xFF;

void selectBus(uint8_t bus)
{
  if (bus == currentBus) return;
  Wire.end();
  Wire.swap(bus);  // only takes effect in Wire.begin()
  Wire.begin();
  currentBus = bus;
}

// SX1276 into sleep so it does not sit in standby (1.6 mA) during the test
void radioSleep()
{
  pinMode(PIN_RADIO_RST, INPUT);
  pinMode(PIN_RADIO_NSS, OUTPUT);
  digitalWrite(PIN_RADIO_NSS, HIGH);
  SPI.begin();
  delay(10);
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_RADIO_NSS, LOW);
  SPI.transfer(0x01 | 0x80);  // RegOpMode write
  SPI.transfer(0x00);         // sleep
  digitalWrite(PIN_RADIO_NSS, HIGH);
  SPI.endTransaction();
}

// Pulsed switch-on, same numbers as the TDMA firmware: on-times 50..800 us in 5 us steps, 20 us off
void railRamp(volatile uint8_t &out, uint8_t mask)
{
  for (uint16_t on = 50; on <= 800; on += 5)
  {
    out |= mask;
    delayMicroseconds(on);
    out &= ~mask;
    delayMicroseconds(20);
  }
  out |= mask;
}

void scanAndFind(uint8_t bus)
{
  selectBus(bus);
  const char* hdr = bus == BUS_J3 ? "J3" : "J4";
  Serial.print("I2C scan on ");
  Serial.print(hdr);
  Serial.print(":");
  for (uint8_t a = 1; a < 127; a++)
  {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) { Serial.print(" 0x"); Serial.print(a, HEX); }
  }
  Serial.println();

  if (!shtFound && sht4.begin())
  {
    shtFound = true;
    shtBus = bus;
    sht4.setPrecision(SHT4X_HIGH_PRECISION);
    sht4.setHeater(SHT4X_NO_HEATER);
    Serial.print("SHT41 found on ");
    Serial.print(hdr);
    Serial.print(", serial 0x");
    Serial.println(sht4.readSerial(), HEX);
  }
  if (!ensFound && ens160Probe())
  {
    ensFound = true;
    ensBus = bus;
    Serial.print("ENS160 found at 0x");
    Serial.print(ens160Address(), HEX);
    Serial.print(" on ");
    Serial.println(hdr);
  }
}

void setup()
{
  uint8_t flags = RSTCTRL.RSTFR;
  RSTCTRL.RSTFR = flags;
  Serial.begin(115200);
  delay(100);
  Serial.println();
  Serial.println("=== SHT41 + ENS160 test ===");
  Serial.print("Reset flags 0x");
  Serial.print(flags, HEX);
  Serial.println((flags & RSTCTRL_BORF_bm) && !(flags & RSTCTRL_PORF_bm) ? "  <- brown-out" : "");

  radioSleep();
  pinMode(PIN_RAIL_A, OUTPUT);
  pinMode(PIN_RAIL_B, OUTPUT);
  digitalWrite(PIN_RAIL_A, LOW);
  digitalWrite(PIN_RAIL_B, LOW);
  delay(200);

  Serial.println("Switching J3 on ...");
  Serial.flush();  // so a brown-out right after still shows which step it was
  railRamp(VPORTD.OUT, PIN6_bm);
  delay(20);
  Serial.println("Switching J4 on ...");
  Serial.flush();
  railRamp(VPORTC.OUT, PIN1_bm);
  delay(20);

  scanAndFind(BUS_J3);
  scanAndFind(BUS_J4);
  if (!shtFound) Serial.println("SHT41 not found on J3 or J4");
  if (!ensFound) Serial.println("ENS160 not found on J3 or J4");

  if (ensFound)
    ensStart();
  Serial.println("--- readings every 2 s ---");
}

// Starts gas sensing step by step and prints what each step returned, so a failure shows where
void ensStart()
{
  selectBus(ensBus);
  uint8_t mode = 0xFF, status = 0xFF;
  Serial.print("ENS160 mode before 0x");
  Serial.print(ens160GetMode(mode) ? mode : 0xEE, HEX);
  Serial.print(", status 0x");
  Serial.println(ens160ReadStatus(status) ? status : 0xEE, HEX);

  bool ok = ens160SetMode(ENS160_OPMODE_IDLE);
  delay(10);
  Serial.print("  IDLE write ");
  Serial.print(ok ? "ok" : "NACK");
  mode = 0xFF;
  Serial.print(", mode now 0x");
  Serial.println(ens160GetMode(mode) ? mode : 0xEE, HEX);

  Serial.println("  STANDARD write (heater on, up to 79 mA for <5 ms) ...");
  Serial.flush();
  ok = ens160SetMode(ENS160_OPMODE_STANDARD);
  delay(50);
  Serial.print("  STANDARD write ");
  Serial.print(ok ? "ok" : "NACK");
  mode = 0xFF;
  bool readOk = ens160GetMode(mode);
  Serial.print(", mode now 0x");
  Serial.print(readOk ? mode : 0xEE, HEX);
  Serial.print(", status 0x");
  Serial.print(ens160ReadStatus(status) ? status : 0xEE, HEX);
  Serial.print(", part id ");
  Serial.println(ens160Probe() ? "still answers" : "GONE (sensor reset or bus stuck)");
  ensSensing = readOk && mode == ENS160_OPMODE_STANDARD;
  Serial.println(ensSensing ? "ENS160 sensing (values settle after about 3 min)" : "ENS160 did not enter gas sensing, retrying in 10 s");
}

void loop()
{
  float t = NAN, h = NAN;
  if (shtFound)
  {
    selectBus(shtBus);
    sensors_event_t hum, temp;
    if (sht4.getEvent(&hum, &temp))
    {
      t = temp.temperature;
      h = hum.relative_humidity;
      Serial.print("T ");
      Serial.print(t, 2);
      Serial.print(" C, RH ");
      Serial.print(h, 2);
      Serial.print(" %");
    }
    else Serial.print("SHT41 read failed");
  }
  else Serial.print("no SHT41");
  Serial.print(" | ");

  if (ensSensing)
  {
    selectBus(ensBus);
    if (!isnan(t)) ens160SetCompensation(t, h);
    uint8_t status = 0, aqi = 0;
    uint16_t tvoc = 0, eco2 = 0;
    if (!ens160ReadStatus(status)) Serial.print("ENS160 not answering");
    else if (!(status & ENS160_STATUS_NEWDAT)) Serial.print("ENS160 no new sample");
    else if (ens160ReadData(aqi, tvoc, eco2))
    {
      static const char* const validity[] = { "ok", "warming up", "first hour", "invalid" };
      Serial.print("TVOC ");
      Serial.print(tvoc);
      Serial.print(" ppb, eCO2 ");
      Serial.print(eco2);
      Serial.print(" ppm, AQI ");
      Serial.print(aqi);
      Serial.print(" (");
      Serial.print(validity[(status & ENS160_STATUS_VALIDITY_gm) >> ENS160_STATUS_VALIDITY_gp]);
      Serial.print(")");
    }
    else Serial.print("ENS160 read failed");
  }
  else Serial.print("no ENS160");
  Serial.println();

  static uint8_t retryCount = 0;
  if (ensFound && !ensSensing && ++retryCount >= 5)
  {
    retryCount = 0;
    ensStart();
  }
  delay(2000);
}
