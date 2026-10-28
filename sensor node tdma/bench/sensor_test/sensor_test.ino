// Sensor-only bench test for the rev-2 PCB: no LoRa, no sleep. Puts the radio in sleep, powers
// both sensor headers (J3 rail A on PD6, J4 rail B on PC1), finds the SHT41 and the ENS160 on
// either header and prints temperature, humidity, TVOC, eCO2, AQI and the storage voltage every
// 2 s. It tells apart "the sensor board browns the node out by itself" from "only together with
// the radio". Flash the TDMA node sketch back afterwards.
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_SHT4x.h>
#include "ens160_min.h"

const uint8_t PIN_RAIL_A = PIN_PD6;  // J3
const uint8_t PIN_RAIL_B = PIN_PC1;  // J4
const uint8_t PIN_VSTO = PIN_PD0;    // H5 pin 1, storage voltage through the 1 M / 1 M divider
const uint8_t PIN_RADIO_NSS = PIN_PA7;
const uint8_t PIN_RADIO_RST = PIN_PF3;
const uint8_t BUS_J3 = 0, BUS_J4 = 1;  // Wire.swap() states: PA2/PA3, PC2/PC3

Adafruit_SHT4x sht4;
bool shtFound = false, ensFound = false, ensSensing = false;
uint8_t shtBus = BUS_J3, ensBus = BUS_J3, currentBus = 0xFF;

void selectBus(uint8_t bus)
{
  if (bus == currentBus) return;
  Wire.end();
  Wire.swap(bus);
  Wire.begin();
  currentBus = bus;
}

// SX1276 into sleep (RegOpMode 0x01 = 0x00), so it draws about 1 uA instead of standby's 1.6 mA
void radioSleep()
{
  pinMode(PIN_RADIO_RST, INPUT);
  pinMode(PIN_RADIO_NSS, OUTPUT);
  digitalWrite(PIN_RADIO_NSS, HIGH);
  SPI.begin();
  delay(10);
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_RADIO_NSS, LOW);
  SPI.transfer(0x01 | 0x80);
  SPI.transfer(0x00);
  digitalWrite(PIN_RADIO_NSS, HIGH);
  SPI.endTransaction();
}

uint16_t readVstoMv()
{
  analogReference(INTERNAL2V5);
  ADC0.CTRLC = (ADC0.CTRLC & ~ADC_PRESC_gm) | ADC_PRESC_DIV32_gc;
  ADC0.SAMPCTRL = 31;
  delayMicroseconds(100);
  analogRead(PIN_VSTO);
  uint32_t sum = 0;
  for (uint8_t i = 0; i < 16; i++) sum += analogRead(PIN_VSTO);
  return (uint16_t)(sum / 16.0 * 2.5 / 1023.0 * 2.0 * 1000.0 + 0.5);  // x2: 1 M / 1 M divider
}

void railOn(uint8_t pin, const char* name)
{
  Serial.print("Switching ");
  Serial.print(name);
  Serial.println(" on ...");
  Serial.flush();  // so a brown-out right after still shows which one it was
  digitalWrite(pin, HIGH);
  delay(50);
  Serial.print(name);
  Serial.print(" on, storage ");
  Serial.print(readVstoMv());
  Serial.println(" mV");
}

void setup()
{
  uint8_t flags = RSTCTRL.RSTFR;
  RSTCTRL.RSTFR = flags;
  Serial.begin(115200);
  delay(100);
  Serial.println();
  Serial.println("=== Sensor test: no LoRa, both headers on ===");
  Serial.print("Reset flags 0x");
  Serial.print(flags, HEX);
  Serial.println(flags & RSTCTRL_BORF_bm && !(flags & RSTCTRL_PORF_bm) ? "  <- BROWN-OUT: the last step above browned the node out" : "");
  Serial.print("Storage ");
  Serial.print(readVstoMv());
  Serial.println(" mV");

  radioSleep();
  pinMode(PIN_RAIL_A, OUTPUT);
  pinMode(PIN_RAIL_B, OUTPUT);
  digitalWrite(PIN_RAIL_A, LOW);
  digitalWrite(PIN_RAIL_B, LOW);
  delay(200);

  railOn(PIN_RAIL_A, "J3");
  railOn(PIN_RAIL_B, "J4");

  for (uint8_t bus = BUS_J3; bus <= BUS_J4; bus++)
  {
    selectBus(bus);
    const char* hdr = bus == BUS_J3 ? "J3" : "J4";
    Serial.print("I2C on ");
    Serial.print(hdr);
    Serial.print(":");
    for (uint8_t a = 1; a < 127; a++)
    {
      Wire.beginTransmission(a);
      if (Wire.endTransmission() == 0) { Serial.print(" 0x"); Serial.print(a, HEX); }
    }
    Serial.println();
    if (!ensFound && ens160Probe())
    {
      ensFound = true;
      ensBus = bus;
      Serial.print("ENS160 at 0x");
      Serial.print(ens160Address(), HEX);
      Serial.print(" on ");
      Serial.println(hdr);
    }
    if (!shtFound && sht4.begin())
    {
      shtFound = true;
      shtBus = bus;
      sht4.setPrecision(SHT4X_HIGH_PRECISION);
      sht4.setHeater(SHT4X_NO_HEATER);
      Serial.print("SHT41 on ");
      Serial.println(hdr);
    }
  }
  if (!shtFound) Serial.println("SHT41 not found on J3 or J4");
  if (!ensFound) Serial.println("ENS160 not found on J3 or J4");

  if (ensFound)
  {
    selectBus(ensBus);
    Serial.println("Starting ENS160 gas sensing (its heater draws about 29 mA) ...");
    Serial.flush();
    ens160SetMode(ENS160_OPMODE_IDLE);
    delay(10);
    uint8_t mode = 0xFF;
    ensSensing = ens160SetMode(ENS160_OPMODE_STANDARD) && ens160GetMode(mode) && mode == ENS160_OPMODE_STANDARD;
    Serial.println(ensSensing ? "ENS160 sensing, warming up (3 min before values settle)" : "ENS160 did not enter gas sensing");
  }
  Serial.println("--- readings every 2 s ---");
}

void loop()
{
  Serial.print("storage ");
  Serial.print(readVstoMv());
  Serial.print(" mV | ");

  float t = NAN, h = NAN;
  if (shtFound)
  {
    selectBus(shtBus);
    sensors_event_t hum, temp;
    if (sht4.getEvent(&hum, &temp))
    {
      t = temp.temperature;
      h = hum.relative_humidity;
      Serial.print(t, 2); Serial.print(" C, "); Serial.print(h, 2); Serial.print(" %");
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
      Serial.print("TVOC "); Serial.print(tvoc); Serial.print(" ppb, eCO2 "); Serial.print(eco2);
      Serial.print(" ppm, AQI "); Serial.print(aqi); Serial.print(" (");
      Serial.print(validity[(status & ENS160_STATUS_VALIDITY_gm) >> ENS160_STATUS_VALIDITY_gp]);
      Serial.print(")");
    }
    else Serial.print("ENS160 read failed");
  }
  else Serial.print("no ENS160");
  Serial.println();
  delay(2000);
}
