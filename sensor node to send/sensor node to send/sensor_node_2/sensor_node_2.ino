// SX1276 / MCCI LMIC sensor node (SHT41 + ENS160 + storage voltage) - NODE 2 keys (DevEUI 3609e0641306e11c).
// Server sees this board as sensor 2. Do not run it while a Heltec with the same keys is on.
// Network behaviour matches heltec_v3_node.ino: ADR off + SF7 after join, downlink
// loss counter, packet types 0x00 status / 0x01-0x03 command responses. The status packet
// layout is under PKT_STATUS; the ChirpStack decoder is chirpstack_codec.js one folder up.
//
// Build: Arduino IDE, MegaCoreX > ATmega4809, Pinout "48 pin standard", Clock "Internal 8 MHz",
// BOD "2.6V", EEPROM "retained", Programmer "JTAG2UPDI", flash with Sketch > Upload Using Programmer.
// Libraries: MCCI LoRaWAN LMIC library 6.0.1, Adafruit SHT4x Library 1.0.5,
// Rocket Scream LowPowerAVRZero 1.0.0. The ENS160 driver is ens160_min.h in this folder
// (register level over Wire, nothing to install).
// MCCI_LoRaWAN_LMIC_library/project_config/lmic_project_config.h must contain exactly:
//   #define CFG_eu868 1
//   #define CFG_sx1276_radio 1
//   #define LMIC_ENABLE_arbitrary_clock_error 1
//   #define DISABLE_PING
//   #define DISABLE_BEACONS
// Compile-tested 2026-10-28 with MegaCoreX 1.2.0 and the versions above; not yet run on a board
// with all three (SHT41, ENS160, divider) fitted.
//
// Join robustness. On 2026-10-19 a rev-2 board running from storage brown-out reset on every
// JoinRequest (reset flags 0x02): LMIC sends joins at 16 dBm on PA_BOOST and the AEM10330
// LOAD rail cannot carry that. Four measures, see TX_POWER_DBM, Settings and onEvent():
//  - every frame, joins included, is capped at the stored TX power cap (starts at TX_POWER_DBM);
//  - the cap learns: a brown-out reset that hits while the radio is transmitting lowers the
//    cap by TX_POWER_STEP_DB (floor TX_POWER_MIN_DBM) and the new cap is kept in EEPROM;
//  - the ENS160 (about 29 mA while gas sensing) sleeps until the join is accepted;
//  - the OTAA DevNonce continues from EEPROM across resets, so ChirpStack never sees a
//    JoinRequest with a nonce it already used (LMIC alone restarts from a random value).
// The OTAA keys are in secrets.h next to this file, which is kept out of git.
#include <Wire.h>
#include <EEPROM.h>
#include <lmic.h>
#include <hal/hal.h>
#include <RocketScream_LowPowerAVRZero.h>
#include <Adafruit_SHT4x.h>

#define DEBUG 1           // 0 for battery runs: no serial output and the UART pins are parked
#define USE_ENS160 1      // 0 = no ENS160 on the bus: gas bytes carry 0 ppb / 400 ppm / status 0xFF
#define RAIL_ALWAYS_ON 0  // 1 = keep VCC_SENS_A on between readings (see sensorRailOff)
#define VSTO_SENSE 1      // 0 = the storage divider on H5 pin 1 is not fitted, status packets send 0 mV

// With the ENS160 fitted the rail stays on: gas sensing restarts its 3 min warm-up after every
// power cycle, so switching it per reading would never give a valid value at a 60 s interval.
#define SWITCH_RAIL (!RAIL_ALWAYS_ON && !USE_ENS160)

#if USE_ENS160
#include "ens160_min.h"
#endif

#include "secrets.h"

#if !defined(CFG_eu868) || !defined(CFG_sx1276_radio)
#error "lmic_project_config.h must define CFG_eu868 and CFG_sx1276_radio (see the top of this sketch)"
#endif
#if !LMIC_ENABLE_arbitrary_clock_error
#error "lmic_project_config.h must define LMIC_ENABLE_arbitrary_clock_error 1, or LMIC cuts the 2 % clock error to 0.4 %"
#endif
#if F_CPU > 10000000L
#error "Select Tools > Clock > Internal 8 MHz: 16 MHz is outside the ATmega4809 safe operating area at 3.3 V"
#endif

#if DEBUG
#define DBG(...) Serial.print(__VA_ARGS__)
#define DBGLN(...) Serial.println(__VA_ARGS__)
#else
#define DBG(...) do {} while (0)
#define DBGLN(...) do {} while (0)
#endif

Adafruit_SHT4x sht4 = Adafruit_SHT4x();

#if USE_ENS160
bool ens160Found = false;    // answered its part id at boot
bool ens160Sensing = false;  // in gas-sensing mode, which only starts after the join
#endif

void os_getArtEui(u1_t* buf) { memcpy_P(buf, APPEUI, 8); }
void os_getDevEui(u1_t* buf) { memcpy_P(buf, DEVEUI, 8); }
void os_getDevKey(u1_t* buf) { memcpy_P(buf, APPKEY, 16); }

// Board pins (PCB rev 2; the radio pins, PD6 and PD7 are the same on rev 1)
const uint8_t PIN_RAIL_A = PIN_PD6;  // U8 ENA: VCC_SENS_A on J3, I2C bus A (PA2/PA3)
const uint8_t PIN_RAIL_B = PIN_PC1;  // U8 ENB: VCC_SENS_B on J4, I2C bus B - unused, held off
const uint8_t PIN_LED = PIN_PD7;     // never use LED_BUILTIN: MegaCoreX maps it to PA7 = radio NSS
const uint8_t PIN_VSTO = PIN_PD0;    // H5 pin 1 = AIN0: storage voltage through the R1/R2 divider

// Pins this sketch does not drive: PMIC status PB2-PB4 (not read yet), I2C bus B on PC2/PC3,
// header H5 (PD0-PD4, PC7) and the unconnected ones. Their digital input buffers are switched
// off so a floating level cannot draw current. PD0 stays on the list: the ADC does not use the
// digital buffer, and a buffer sitting at half the storage voltage would draw current.
const uint8_t UNUSED_PINS[] = {
  PIN_PB0, PIN_PB1, PIN_PB2, PIN_PB3, PIN_PB4, PIN_PB5,
  PIN_PC0, PIN_PC2, PIN_PC3, PIN_PC4, PIN_PC5, PIN_PC6, PIN_PC7,
  PIN_PD0, PIN_PD1, PIN_PD2, PIN_PD3, PIN_PD4, PIN_PD5,
  PIN_PE0, PIN_PE1, PIN_PE2, PIN_PE3, PIN_PF0, PIN_PF1,
};

const lmic_pinmap lmic_pins = {
  .nss = PIN_PA7,
  .rxtx = LMIC_UNUSED_PIN,
  .rst = PIN_PF3,
  .dio = { PIN_PF2, PIN_PF4, PIN_PF5 },
};

static osjob_t sendjob;

// Seconds in power-down between status uplinks. A downlink command can only arrive after an
// uplink (Class A), so this is also the worst-case wait before the node sees a task.
// At least 10 s so the sleep clock's error (ULP oscillator, +-10 % over 0-70 C) can never push
// LMIC past the 1 % duty cycle; at most 1800 s so LMIC still notices micros() wrapping.
const uint16_t TX_INTERVAL = 60;
static_assert(TX_INTERVAL >= 10 && TX_INTERVAL <= 1800, "TX_INTERVAL must be 10..1800 s");

// Transmit power cap (dBm) for every frame, joins included. On rev 2 the whole 3.3 V rail is the
// AEM10330's LOAD output, which gives about 60 mA with the storage at 2.8-3.0 V and 72-76 mA
// at 3.1-3.6 V (DS v1.5.0 Table 6, Fig. 7). LMIC sends joins at 16 dBm on PA_BOOST, and the
// SX1276 draws 87 mA at 17 dBm, so the rail sagged and the chip brown-out reset on every
// JoinRequest (reset flags 0x02). TX_POWER_DBM is where the cap starts after a flash; a
// brown-out during a transmission then takes TX_POWER_STEP_DB off it, down to TX_POWER_MIN_DBM,
// and the result stays in EEPROM (see Settings). 10 dBm is a starting point, not a measured
// limit: PA_BOOST current per dBm on the Vollgo module is still to be measured with the PPK2.
// Changing TX_POWER_DBM restarts the learning from the new value. LMIC accepts 2..17 on PA_BOOST.
const int8_t TX_POWER_DBM = 10;
const int8_t TX_POWER_MIN_DBM = 2;
const int8_t TX_POWER_STEP_DB = 2;
static_assert(TX_POWER_DBM >= 2 && TX_POWER_DBM <= 17, "TX_POWER_DBM must be 2..17 dBm");
static_assert(TX_POWER_MIN_DBM >= 2 && TX_POWER_MIN_DBM <= TX_POWER_DBM, "TX_POWER_MIN_DBM must be 2..TX_POWER_DBM");
static_assert(TX_POWER_STEP_DB >= 1, "TX_POWER_STEP_DB must be at least 1 dB");

// What survives a reset, in EEPROM at SETTINGS_ADDR. Written only when something changes:
// on first boot, on a brown-out during a transmission, and once per JoinRequest (DevNonce).
// A flash with Tools > EEPROM "retained" keeps it; "not retained" or a changed TX_POWER_DBM
// starts over.
struct Settings
{
  uint32_t magic;      // SETTINGS_MAGIC, anything else means blank or an older layout
  int8_t txPowerMax;   // the TX_POWER_DBM the cap was learned under
  int8_t txPowerCap;   // the cap in use, dBm
  uint8_t brownOuts;   // brown-out resets seen during a transmission, saturates at 255
  uint16_t devNonce;   // the next OTAA DevNonce
};
const uint32_t SETTINGS_MAGIC = 0x4E4F4431;  // "NOD1", layout 1
const int SETTINGS_ADDR = 0;
Settings settings;

// What the sketch was doing when the last reset hit. The .noinit section is not cleared at
// start-up, so this survives a brown-out, watchdog or software reset; after a power-on the
// magic is (almost surely) wrong and the record is ignored.
struct BootTrace
{
  uint32_t magic;
  uint8_t phase;
};
const uint32_t TRACE_MAGIC = 0x54524143;  // "TRAC"
const uint8_t PHASE_IDLE = 0;
const uint8_t PHASE_TX = 1;  // from EV_TXSTART until the radio is done transmitting
BootTrace bootTrace __attribute__((section(".noinit")));

uint8_t resetFlags = 0;  // RSTCTRL.RSTFR at boot: 0x01 power-on, 0x02 brown-out, 0x08 watchdog

// Storage voltage divider (rev-2 bodge, no PCB footprint): R1 from the + pin of the storage
// terminal U11 to H5 pin 1, R2 from H5 pin 1 to J4 pin 3 (GND). A ceramic cap across R2 is
// optional; electrolytics leak too much for a 500 kohm source. The LiC charges to 3.60 V under
// STO_CFG LLLH, above the 3.3 V rail, so it cannot go to the pin directly. Enter the measured
// resistances, then set VSTO_CAL once per board to (multimeter volts on the storage terminal
// screws) / (volts this sketch prints), measured at the same moment.
const uint32_t VSTO_R_TOP = 1000000;     // R1, ohms
const uint32_t VSTO_R_BOTTOM = 1000000;  // R2, ohms
const float VSTO_CAL = 1.000;
// R1 >= R2 keeps a full 3.8 V cell at or under 1.9 V on the pin, inside the 2.5 V reference
static_assert(VSTO_R_TOP >= VSTO_R_BOTTOM, "VSTO_R_TOP must be at least VSTO_R_BOTTOM");

const uint8_t DOWNLINK_PORT = 10;
const uint8_t CMD_HUMIDITY = 0x01;
const uint8_t CMD_TEMPERATURE = 0x02;
const uint8_t CMD_GAS = 0x03;

// Uplink packet types (first payload byte, uplinks on fPort 1):
//   PKT_STATUS (0x00) - routine periodic full reading. NOT a reply to a command,
//                       so the server does not treat it as "task done".
//   0x01 / 0x02 / 0x03 - response to a humidity / temperature / gas command.
//                       Only these mark the sensor as free again on the server.
// Status packet, 15 bytes, 16-bit values big-endian:
//   [0] 0x00, [1-2] TVOC ppb, [3-4] eCO2 ppm, [5-6] temperature x100 (C),
//   [7-8] humidity x100 (%RH), [9-10] storage voltage in mV (0 = not measured),
//   [11] AQI-UBA 1..5 (0 = none), [12] ENS160 status (see ENS_ABSENT),
//   [13] TX power cap in dBm, [14] reset flags of this boot (RSTCTRL.RSTFR).
// Bytes 0-10 are unchanged, so a decoder that stops at byte 10 keeps working.
// Gas reply, 7 bytes: [0] 0x03, [1-2] TVOC, [3-4] eCO2, [5] AQI-UBA, [6] ENS160 status.
const uint8_t PKT_STATUS = 0x00;

// Sent in place of temperature / humidity when the SHT41 does not answer (decodes as 327.67).
const int16_t NO_READING = 0x7FFF;

// ENS160 status byte in the packets: 0..3 is the sensor's own validity flag (0 normal,
// 1 warm-up, 2 initial start-up, 3 invalid output); the rest are the node's codes.
const uint8_t ENS_NO_SAMPLE = 0xFD;  // sensing, but no fresh sample yet (first second after start)
const uint8_t ENS_NO_ANSWER = 0xFE;  // found at boot, no I2C answer now
const uint8_t ENS_ABSENT = 0xFF;     // not fitted, not found at boot, or not started yet

struct Reading
{
  int16_t tempScaled;  // C x100
  int16_t humScaled;   // %RH x100
  uint16_t tvoc;       // ppb
  uint16_t eco2;       // ppm
  uint8_t aqi;         // AQI-UBA 1..5, 0 = none
  uint8_t ensStatus;
};
bool readSensors(Reading &r);  // declared here so the IDE's generated prototype does not land above the struct

uint8_t pendingCommand = 0;
bool sleepPending = false;  // an uplink cycle has finished and nothing else is queued

// Downlink loss tracking (same idea as the Heltec sketch): the network numbers
// every downlink, so a jump in the downlink counter means frames were missed.
int32_t lastDownlinkFCnt = -1;
uint32_t downlinksReceived = 0;
uint32_t downlinksMissed = 0;

// MegaCoreX's millis() counter (wiring.c). LMIC keeps time with micros(), which is built on it
// and stops in power-down, so deepSleep() adds the slept time back.
extern "C" volatile uint32_t timer_millis;

volatile uint16_t pitTicks = 0;

ISR(RTC_PIT_vect)
{
  RTC.PITINTFLAGS = RTC_PI_bm;
  pitTicks++;
}

void watchdogKick()
{
  __asm__ __volatile__("wdr");
}

uint16_t readPitTicks()
{
  noInterrupts();
  uint16_t ticks = pitTicks;
  interrupts();
  return ticks;
}

// Power-down for `seconds`, woken once a second by the RTC PIT, which runs from the 1.024 kHz
// ULP oscillator and is the only timer left running in power-down.
void deepSleep(uint16_t seconds)
{
#if DEBUG
  Serial.flush();
#endif
  noInterrupts();
  pitTicks = 0;
  interrupts();

  // The first tick lands anywhere inside the current second, so sleep one extra tick and
  // credit only the whole seconds: LMIC's clock then never runs ahead of real time.
  while (readPitTicks() <= seconds)
  {
    LowPower.powerDown();
    watchdogKick();  // the watchdog keeps counting in power-down
  }

  noInterrupts();
  timer_millis += (uint32_t)seconds * 1000UL;
  interrupts();
}

void saveSettings()
{
  EEPROM.put(SETTINGS_ADDR, settings);  // only bytes that changed are written
}

// Call after LMIC_reset(), which seeds LMIC.devNonce from the radio's noise: a blank EEPROM
// takes that as the first DevNonce.
void loadSettings()
{
  EEPROM.get(SETTINGS_ADDR, settings);
  bool valid = settings.magic == SETTINGS_MAGIC && settings.txPowerMax == TX_POWER_DBM &&
               settings.txPowerCap >= TX_POWER_MIN_DBM && settings.txPowerCap <= TX_POWER_DBM;
  if (valid)
    return;

  settings.magic = SETTINGS_MAGIC;
  settings.txPowerMax = TX_POWER_DBM;
  settings.txPowerCap = TX_POWER_DBM;
  settings.brownOuts = 0;
  settings.devNonce = LMIC.devNonce;
  saveSettings();
  DBGLN("Settings initialised in EEPROM");
}

// A brown-out reset while the radio was transmitting means the rail could not carry that
// frame, so the next ones go out with less power. Nothing raises the cap again except a new
// TX_POWER_DBM, so a marginal rail settles at the power it can carry instead of resetting on
// every JoinRequest. Brown-outs at other moments (sensor rail switch-on, ENS160 inrush) are
// reported in the status packet's reset flags but do not touch the cap.
void learnFromBrownOut()
{
  bool duringTx = bootTrace.magic == TRACE_MAGIC && bootTrace.phase == PHASE_TX;
  bootTrace.magic = TRACE_MAGIC;
  bootTrace.phase = PHASE_IDLE;

  // a power-on also raises the brown-out flag while VDD climbs through the BOD level
  if (!(resetFlags & RSTCTRL_BORF_bm) || (resetFlags & RSTCTRL_PORF_bm) || !duringTx)
    return;

  if (settings.brownOuts < 255)
    settings.brownOuts++;
  if (settings.txPowerCap - TX_POWER_STEP_DB >= TX_POWER_MIN_DBM)
    settings.txPowerCap -= TX_POWER_STEP_DB;
  else
    settings.txPowerCap = TX_POWER_MIN_DBM;
  saveSettings();

  DBG("Brown-out during a transmission (");
  DBG(settings.brownOuts);
  DBG(" so far): TX power cap now ");
  DBG(settings.txPowerCap);
  DBGLN(" dBm");
}

void sensorRailOn()
{
  digitalWriteFast(PIN_RAIL_A, HIGH);
  delay(5);  // load-switch soft start and SHT41 power-up (1 ms max)
  LowPower.enablePinISC(PIN_PA2);
  LowPower.enablePinISC(PIN_PA3);
  Wire.begin();
}

// On rev 2 the bus pull-ups R9-R12 sit on the always-on 3V3, so a sensor whose rail is off is
// back-fed through SDA/SCL (estimated 0.3-0.5 mA, not measured). Whether switching the rail off
// beats leaving it on (power LED and regulator on the breakout) needs a PPK2 measurement of both.
void sensorRailOff()
{
  Wire.end();
  LowPower.disablePinISC(PIN_PA2);  // also clears the internal pull-ups Wire.begin() set
  LowPower.disablePinISC(PIN_PA3);
  digitalWriteFast(PIN_RAIL_A, LOW);
}

#if USE_ENS160
// Deep sleep -> idle -> gas sensing (deep sleep only exits to idle). The hot plate then needs
// about 3 min before the readings mean anything (status 1, warm-up); a sensor in its first
// hour of life reports 2 (initial start-up) instead.
void ens160Start()
{
  if (!ens160Found || ens160Sensing)
    return;
  if (!ens160SetMode(ENS160_OPMODE_IDLE))
  {
    DBGLN("ENS160 did not answer the wake-up");
    return;
  }
  delay(10);
  uint8_t mode = 0xFF;
  ens160Sensing = ens160SetMode(ENS160_OPMODE_STANDARD) && ens160GetMode(mode) && mode == ENS160_OPMODE_STANDARD;
  DBGLN(ens160Sensing ? "ENS160 gas sensing started, warming up" : "ENS160 did not enter gas-sensing mode");
}
#endif

// Fresh SHT41 reading, plus the ENS160's latest sample when it is sensing. Returns false when
// the SHT41 did not answer; temperature and humidity are then NO_READING. The gas fields
// always hold something the server can decode (see ENS_ABSENT and friends).
bool readSensors(Reading &r)
{
#if SWITCH_RAIL
  sensorRailOn();
#endif

  sensors_event_t humEvent, tempEvent;
  bool ok = sht4.getEvent(&humEvent, &tempEvent);
  r.tempScaled = ok ? (int16_t)(tempEvent.temperature * 100) : NO_READING;
  r.humScaled = ok ? (int16_t)(humEvent.relative_humidity * 100) : NO_READING;

  // the values the server already got when no gas sensor is fitted
  r.tvoc = 0;
  r.eco2 = 400;
  r.aqi = 0;
  r.ensStatus = ENS_ABSENT;

#if USE_ENS160
  if (ens160Sensing)
  {
    if (ok)
      ens160SetCompensation(tempEvent.temperature, humEvent.relative_humidity);

    uint8_t status;
    if (!ens160ReadStatus(status))
      r.ensStatus = ENS_NO_ANSWER;
    else if (!(status & ENS160_STATUS_NEWDAT))
      r.ensStatus = ENS_NO_SAMPLE;  // a sample arrives every second once sensing; only the first cycle sees this
    else if (ens160ReadData(r.aqi, r.tvoc, r.eco2))
      r.ensStatus = (status & ENS160_STATUS_VALIDITY_gm) >> ENS160_STATUS_VALIDITY_gp;
    else
      r.ensStatus = ENS_NO_ANSWER;
  }
#endif

#if SWITCH_RAIL
  sensorRailOff();
#endif
  return ok;
}

// Storage voltage in mV (0 with VSTO_SENSE off). The reference is the internal 2.5 V one, not
// VDD: the AEM10330 lets the 3.3 V rail wander from 3.15 to 3.34 V (DS v1.5.0 Table 10), and the
// 2.5 V reference is allowed down to VDD = 3.0 V (ATmega4809 DS Table 32-22). Takes about 3 ms,
// so call it while the radio is idle.
uint16_t readVstoMv()
{
#if VSTO_SENSE
  ADC0.CTRLA |= ADC_ENABLE_bm;  // off the rest of the time, see setup()
  analogReference(INTERNAL2V5);
  // 8 MHz / 32 = 250 kHz: the core's 125 kHz is under the 200 kHz minimum for 10-bit results
  // (DS Table 32-26). Longest sampling window, 33 ADC clocks = 132 us, so the 500 kohm divider
  // can charge the sample-and-hold capacitor even without a cap on the pin.
  ADC0.CTRLC = (ADC0.CTRLC & ~ADC_PRESC_gm) | ADC_PRESC_DIV32_gc;
  ADC0.SAMPCTRL = 31;
  delayMicroseconds(100);  // internal reference start-up is 25 us
  analogRead(PIN_VSTO);    // the first result after enabling is thrown away

  uint32_t sum = 0;
  for (uint8_t i = 0; i < 16; i++)
    sum += analogRead(PIN_VSTO);
  ADC0.CTRLA &= ~ADC_ENABLE_bm;

  // RES = 1023 x VIN / VREF (DS 29.3.2.5), then undo the divider
  float pinVolts = sum / 16.0 * 2.5 / 1023.0;
  float vsto = pinVolts * (VSTO_R_TOP + VSTO_R_BOTTOM) / VSTO_R_BOTTOM * VSTO_CAL;
  return (uint16_t)(vsto * 1000.0 + 0.5);
#else
  return 0;
#endif
}

void do_send(osjob_t* j)
{
  if (LMIC.opmode & OP_TXRXPEND)
  {
    DBGLN("OP_TXRXPEND, not sending");
    os_setTimedCallback(j, os_getTime() + ms2osticks(200), do_send);
    return;
  }

  uint16_t vstoMv = readVstoMv();  // first, while the radio is off

  Reading r;
  if (!readSensors(r))
    DBGLN("SHT41 did not answer, sending 0x7FFF for temperature and humidity");

  uint8_t payload[15];
  uint8_t len = 0;

  if (pendingCommand == CMD_HUMIDITY)
  {
    payload[0] = CMD_HUMIDITY;
    payload[1] = highByte(r.humScaled);
    payload[2] = lowByte(r.humScaled);
    len = 3;

    DBG("Sending humidity only: ");
    DBG(r.humScaled / 100.0);
    DBGLN(" %");
  }
  else if (pendingCommand == CMD_TEMPERATURE)
  {
    payload[0] = CMD_TEMPERATURE;
    payload[1] = highByte(r.tempScaled);
    payload[2] = lowByte(r.tempScaled);
    len = 3;

    DBG("Sending temperature only: ");
    DBG(r.tempScaled / 100.0);
    DBGLN(" C");
  }
  else if (pendingCommand == CMD_GAS)
  {
    payload[0] = CMD_GAS;
    payload[1] = highByte(r.tvoc);
    payload[2] = lowByte(r.tvoc);
    payload[3] = highByte(r.eco2);
    payload[4] = lowByte(r.eco2);
    payload[5] = r.aqi;
    payload[6] = r.ensStatus;
    len = 7;

    DBG("Sending gas/CO2 only: TVOC ");
    DBG(r.tvoc);
    DBG(" ppb, eCO2 ");
    DBG(r.eco2);
    DBG(" ppm, AQI ");
    DBG(r.aqi);
    DBG(", ENS160 status 0x");
    DBGLN(r.ensStatus, HEX);
  }
  else
  {
    // No command pending: send a status packet (full reading)
    payload[0] = PKT_STATUS;
    payload[1] = highByte(r.tvoc);
    payload[2] = lowByte(r.tvoc);
    payload[3] = highByte(r.eco2);
    payload[4] = lowByte(r.eco2);
    payload[5] = highByte(r.tempScaled);
    payload[6] = lowByte(r.tempScaled);
    payload[7] = highByte(r.humScaled);
    payload[8] = lowByte(r.humScaled);
    payload[9] = highByte(vstoMv);
    payload[10] = lowByte(vstoMv);
    payload[11] = r.aqi;
    payload[12] = r.ensStatus;
    payload[13] = (uint8_t)settings.txPowerCap;
    payload[14] = resetFlags;
    len = 15;

    DBG("Sending status packet: ");
    DBG(r.tempScaled / 100.0);
    DBG(" C, ");
    DBG(r.humScaled / 100.0);
    DBG(" %, TVOC ");
    DBG(r.tvoc);
    DBG(" ppb, eCO2 ");
    DBG(r.eco2);
    DBG(" ppm, AQI ");
    DBG(r.aqi);
    DBG(", ENS160 status 0x");
    DBG(r.ensStatus, HEX);
    DBG(", storage ");
    DBG(vstoMv);
    DBG(" mV, TX cap ");
    DBG(settings.txPowerCap);
    DBGLN(" dBm");
  }

  if (LMIC_setTxData2(1, payload, len, 0) != LMIC_ERROR_SUCCESS)
  {
    // keep pendingCommand so the reply goes out on the next cycle
    DBGLN("LMIC_setTxData2 failed, retrying next cycle");
    sleepPending = true;
    return;
  }

  pendingCommand = 0;
}

void onEvent(ev_t ev)
{
  switch (ev)
  {
    case EV_JOINING:
      DBGLN("EV_JOINING");
      break;

    case EV_JOIN_TXCOMPLETE:
      bootTrace.phase = PHASE_IDLE;
      DBGLN("EV_JOIN_TXCOMPLETE (no JoinAccept yet)");
      break;

    case EV_JOINED:
      bootTrace.phase = PHASE_IDLE;
      DBGLN("EV_JOINED");
      LMIC_setLinkCheckMode(0);
      // ADR off + fixed SF7 (DR5): no ADR downlinks from ChirpStack, short uplinks.
      // Uplink channels are limited to 868.1/868.3/868.5 by ChirpStack (no CFList).
      LMIC_setAdrMode(0);
      LMIC_setDrTxpow(DR_SF7, settings.txPowerCap);
#if USE_ENS160
      ens160Start();  // kept asleep until now so its 29 mA never overlaps a JoinRequest
#endif
      do_send(&sendjob);
      break;

    case EV_TXSTART:
      // LMIC has just picked this frame's power (16 dBm for a join) and starts the radio right
      // after this event returns, so this is the last place to cap it
      if (LMIC.radio.txpow > settings.txPowerCap)
        LMIC.radio.txpow = settings.txPowerCap;

      if (LMIC.opmode & OP_JOINING)
      {
        // LMIC.frame already carries this JoinRequest's DevNonce and LMIC.devNonce has moved
        // on to the next one. Store it before the radio goes on: if this frame browns the
        // node out, the next boot must not repeat a nonce ChirpStack has already accepted.
        settings.devNonce = LMIC.devNonce;
        saveSettings();
      }

      bootTrace.phase = PHASE_TX;
      break;

    case EV_RXSTART:
      bootTrace.phase = PHASE_IDLE;  // the transmission is over once a receive window opens
      break;

    case EV_JOIN_FAILED:
      // LMIC keeps retrying on its own
      bootTrace.phase = PHASE_IDLE;
      DBGLN("EV_JOIN_FAILED");
      break;

    case EV_TXCOMPLETE:
      bootTrace.phase = PHASE_IDLE;
      DBGLN("EV_TXCOMPLETE");

      if (LMIC.txrxFlags & (TXRX_DNW1 | TXRX_DNW2))
      {
        // a downlink was received; seqnoDn is now the next expected counter
        int32_t fcnt = (int32_t)LMIC.seqnoDn - 1;
        downlinksReceived++;
        if (fcnt - lastDownlinkFCnt - 1 > 0)
        {
          downlinksMissed += fcnt - lastDownlinkFCnt - 1;
          DBG("  !! MISSED ");
          DBG(fcnt - lastDownlinkFCnt - 1);
          DBGLN(" downlink(s) before this one");
        }
        lastDownlinkFCnt = fcnt;
        DBG("  downlinks received ");
        DBG(downlinksReceived);
        DBG(", missed ");
        DBGLN(downlinksMissed);
      }

      if (LMIC.dataLen > 0)
      {
        bool onCorrectPort = true;

        if (LMIC.txrxFlags & TXRX_PORT)
        {
          uint8_t port = LMIC.frame[LMIC.dataBeg - 1];
          onCorrectPort = (port == DOWNLINK_PORT);
          DBG("Downlink on port: ");
          DBGLN(port);
        }

        if (onCorrectPort)
        {
          uint8_t cmd = LMIC.frame[LMIC.dataBeg];
          DBG("Downlink command received: 0x");
          DBGLN(cmd, HEX);

          if (cmd == CMD_HUMIDITY || cmd == CMD_TEMPERATURE || cmd == CMD_GAS)
          {
            pendingCommand = cmd;
          }
        }
      }

      if (pendingCommand)
      {
        // answer the task straight away; LMIC holds the uplink until the duty cycle allows it
        os_setCallback(&sendjob, do_send);
      }
      else
      {
        sleepPending = true;
      }
      break;

    case EV_TXCANCELED:
      bootTrace.phase = PHASE_IDLE;
      DBGLN("EV_TXCANCELED");
      sleepPending = true;
      break;

    default:
      break;
  }
}

void setup()
{
  // Watchdog first, 8 s, kicked from loop() and on every wake while asleep. It catches an I2C
  // hang (MegaCoreX Wire has no timeout) and LMIC's hal_failed() endless loop.
  _PROTECTED_WRITE(WDT.CTRLA, WDT_PERIOD_8KCLK_gc);

  resetFlags = RSTCTRL.RSTFR;
  RSTCTRL.RSTFR = resetFlags;  // flags clear by writing 1

  ADC0.CTRLA &= ~ADC_ENABLE_bm;  // the core enables the ADC; readVstoMv() turns it on only to read

  for (uint8_t i = 0; i < sizeof(UNUSED_PINS); i++)
    LowPower.disablePinISC(UNUSED_PINS[i]);

  pinMode(PIN_LED, OUTPUT);
  digitalWriteFast(PIN_LED, LOW);
  pinMode(PIN_RAIL_B, OUTPUT);
  digitalWriteFast(PIN_RAIL_B, LOW);
  pinMode(PIN_RAIL_A, OUTPUT);
  digitalWriteFast(PIN_RAIL_A, LOW);

#if DEBUG
  Serial.begin(115200);
  PORTA.PIN1CTRL |= PORT_PULLUPEN_bm;  // RX0 floats when the USB-serial adapter is unplugged
  Serial.println("SHT41 + ENS160 LoRaWAN node - power-down between uplinks, downlink task support");
  Serial.print("Reset flags 0x");  // 0x02 = brown-out, 0x08 = watchdog reset
  Serial.println(resetFlags, HEX);
#else
  LowPower.disablePinISC(PIN_PA0);
  LowPower.disablePinISC(PIN_PA1);
#endif

  // RTC PIT: 1.024 kHz from the internal ULP oscillator, one interrupt per second
  while (RTC.STATUS > 0) {}
  RTC.CLKSEL = RTC_CLKSEL_INT1K_gc;
  RTC.PITINTCTRL = RTC_PI_bm;
  while (RTC.PITSTATUS > 0) {}
  RTC.PITCTRLA = RTC_PERIOD_CYC1024_gc | RTC_PITEN_bm;

  // printed at boot too, so calibration does not have to wait for the join
  DBG("Storage voltage ");
  DBG(readVstoMv());
  DBGLN(" mV");

  sensorRailOn();

#if USE_ENS160
  ens160Found = ens160Probe();
  if (ens160Found)
  {
    DBG("ENS160 found at 0x");
    DBGLN(ens160Address(), HEX);
    // Reset it, then park it in deep sleep (about 10 uA) until the join is through: gas
    // sensing draws about 29 mA, which the LOAD rail cannot spare next to a JoinRequest.
    ens160SetMode(ENS160_OPMODE_RESET);
    delay(100);
    watchdogKick();
    if (!ens160SetMode(ENS160_OPMODE_DEEP_SLEEP))
      DBGLN("ENS160 did not answer after reset");
  }
  else
    DBGLN("Could not find ENS160, check wiring!");
#endif

  if (!sht4.begin())
    DBGLN("Could not find SHT41, check wiring!");
  else
  {
    DBGLN("SHT41 found!");
    sht4.setPrecision(SHT4X_HIGH_PRECISION);
    sht4.setHeater(SHT4X_NO_HEATER);
  }

#if SWITCH_RAIL
  sensorRailOff();
#endif

  os_init();
  LMIC_reset();
  // The internal oscillator is only good to +-2 % over 0-70 C (ATmega4809 datasheet,
  // OSC20M total error), so the receive windows are widened to match.
  LMIC_setClockError(MAX_CLOCK_ERROR * 2 / 100);
  PORTA.PIN5CTRL |= PORT_PULLUPEN_bm;  // MISO floats while the radio is deselected

  loadSettings();  // after LMIC_reset(): a blank EEPROM takes LMIC's random DevNonce
  learnFromBrownOut();
  LMIC.devNonce = settings.devNonce;
  DBG("TX power cap ");
  DBG(settings.txPowerCap);
  DBG(" dBm, brown-outs during TX ");
  DBG(settings.brownOuts);
  DBG(", next DevNonce ");
  DBGLN(settings.devNonce);

  LMIC_startJoining();
}

void loop()
{
  watchdogKick();
  os_runloop_once();

  if (sleepPending && !(LMIC.opmode & OP_TXRXPEND))
  {
    sleepPending = false;
    DBG("Sleeping ");
    DBG(TX_INTERVAL);
    DBGLN(" s");
    deepSleep(TX_INTERVAL);
    os_setCallback(&sendjob, do_send);
  }
  else
  {
    // Idle keeps the 1 ms millis tick running, so LMIC's receive-window timing still holds.
    LowPower.idle();
  }
}
