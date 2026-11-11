// TDMA sensor node 4 (ATmega4809 + SX1276 w/ LMIC). SHT41 + ENS160 + storage voltage.
// DevEUI 1d911ad99f920e37, the server sees this board as sensor 4. Keys are in secrets.h.
// Dont run 2 devices w/ the same keys at the same time.
// Same code as node 1 except temp / hum come from a DHT11 on J3 (USE_DHT11) instead of the SHT41.
//
// How it works (short version):
//  - time is split into frames, each node gets 1 slot per frame and only tx's in its own slot
//  - every TDMA downlink (fPort 20) has the schedule + maybe a task:
//      6 bytes: [0] cmd  [1] slot idx  [2] num slots  [3] frame len (s)  [4..5] slot correction (ms)
//      8 bytes (frames > 65 s): [0..2] same  [3..4] frame len (s)  [5..7] slot correction (ms)
//      cmd: 0x00 nothing (just sync), 0x01 hum, 0x02 temp, 0x03 gas, 0x10 battery refill (ignored)
//      bit 7 of byte [1] set = the correction is signed (can be negative, down to -half a frame)
//  - no downlink yet -> node runs on DEFAULT_SLOTS / DEFAULT_SLOT_MS
//  - a task is answered in the NEXT slot, not right away
//  - last 2 bytes of every uplink = energy (0..ENERGY_CAPACITY), calculated from the storage voltage
//  - w/ SKIP_UNAFFORDABLE_TASKS 1: not enough energy for a task -> skip it and send a status pkt
//  - sensors only get power when a task needs them, mcu is in power-down between slots
//
// Build: Arduino IDE, MegaCoreX > ATmega4809, pinout "48 pin standard", clock "Internal 8 MHz",
// BOD "2.6V", EEPROM "retained", programmer "JTAG2UPDI", flash w/ Sketch > Upload Using Programmer.
// Libs: MCCI LoRaWAN LMIC library 6.0.1, Adafruit SHT4x Library 1.0.5,
// Rocket Scream LowPowerAVRZero 1.0.0. ENS160 driver is ens160_min.h in this folder.
// MCCI_LoRaWAN_LMIC_library/project_config/lmic_project_config.h has to be exactly:
//   #define CFG_eu868 1
//   #define CFG_sx1276_radio 1
//   #define LMIC_ENABLE_arbitrary_clock_error 1
//   #define DISABLE_PING
//   #define DISABLE_BEACONS
#include <Wire.h>
#include <SPI.h>
#include <EEPROM.h>
#include <lmic.h>
#include <hal/hal.h>
#include <RocketScream_LowPowerAVRZero.h>
#include <Adafruit_SHT4x.h>

#define DEBUG 1           // 1 = serial prints, 0 = no prints (use 0 on battery)
#define USE_ENS160 1      // 0 = no ENS160 connected, gas reply is 0 ppb / 400 ppm / status 0xFF
#define USE_DHT11 1       // node 4: DHT11 on J3 (data on PA2) does temp / hum instead of the SHT41,
                          // and the ENS160 is only looked for on J4
#define VSTO_SENSE 1      // 0 = no voltage divider on H5 pin 1, voltage is sent as 0 mV
#define NODE_NUMBER 4     // sensor number on the server, also picks the default slot
#define SKIP_UNAFFORDABLE_TASKS 0  // 0 = do every task no matter the energy, 1 = skip a task that
                                   // costs more than the energy left. energy is sent either way

// EXPERIMENTAL, not tested on hardware yet. set to 0 to turn off
#define I2C_TIMEOUT_GUARD 1                // stop a sensor i2c access that takes more than 3 s
#define WATCHDOG_COUNTS_AS_SENSOR_FAULT 1  // watchdog reset during a sensor access = that sensor's
                                           // fault, same as a brown-out there

#if USE_ENS160
#include "ens160_min.h"
#endif

#include "secrets.h"

// stop the build if the lmic config or the clock is wrong
#if !defined(CFG_eu868) || !defined(CFG_sx1276_radio)
#error "lmic_project_config.h must define CFG_eu868 and CFG_sx1276_radio (see the top of this sketch)"
#endif
#if !LMIC_ENABLE_arbitrary_clock_error
#error "lmic_project_config.h must define LMIC_ENABLE_arbitrary_clock_error 1, or LMIC cuts the 2 % clock error to 0.4 %"
#endif
#if F_CPU > 10000000L
#error "Select Tools > Clock > Internal 8 MHz: 16 MHz is outside the ATmega4809 safe operating area at 3.3 V"
#endif

// debug prints, they turn into nothing when DEBUG is 0
#if DEBUG
#define DBG(...) Serial.print(__VA_ARGS__)
#define DBGLN(...) Serial.println(__VA_ARGS__)
#else
#define DBG(...) do {} while (0)
#define DBGLN(...) do {} while (0)
#endif

Adafruit_SHT4x sht4 = Adafruit_SHT4x();  // temp + hum sensor

#if USE_ENS160
bool ens160Found = false;    // true once the ENS160 answered
bool gasWarming = false;     // true while the ENS160 is on and heating for a gas task
uint32_t gasSince = 0;       // millis() when the heating started
#endif

// lmic calls these to get the keys (from secrets.h)
void os_getArtEui(u1_t* buf) { memcpy_P(buf, APPEUI, 8); }
void os_getDevEui(u1_t* buf) { memcpy_P(buf, DEVEUI, 8); }
void os_getDevKey(u1_t* buf) { memcpy_P(buf, APPKEY, 16); }

// board pins (PCB rev 2)
const uint8_t PIN_RAIL_A = PIN_PD6;  // power enable for header J3 (i2c on PA2/PA3)
const uint8_t PIN_RAIL_B = PIN_PC1;  // power enable for header J4 (i2c on PC2/PC3)
const uint8_t PIN_LED = PIN_PD7;     // dont use LED_BUILTIN, on MegaCoreX thats PA7 = radio NSS
const uint8_t PIN_VSTO = PIN_PD0;    // adc pin for the storage voltage (through the divider)

// the mcu has 1 i2c, it can be on J3 (default pins) or J4 (Wire.swap(1))
const uint8_t BUS_J3 = 0;   // Wire.swap() value for J3
const uint8_t BUS_J4 = 1;   // Wire.swap() value for J4
uint8_t currentBus = 0xFF;  // which header the i2c is on rn, 0xFF = none
uint8_t shtBus = BUS_J3;    // header the SHT41 was found on
uint8_t ensBus = BUS_J3;    // header the ENS160 was found on
bool shtFound = false;      // true once the SHT41 answered
bool shtSearched = false;   // alrd looked for the SHT41 this boot (only search once)
bool ensSearched = false;   // alrd looked for the ENS160 this boot

// pins we dont use, their input buffers get turned off to save power
const uint8_t UNUSED_PINS[] = {
  PIN_PB0, PIN_PB1, PIN_PB2, PIN_PB3, PIN_PB4, PIN_PB5,
  PIN_PC0, PIN_PC4, PIN_PC5, PIN_PC6, PIN_PC7,
  PIN_PD0, PIN_PD1, PIN_PD2, PIN_PD3, PIN_PD4, PIN_PD5,
  PIN_PE0, PIN_PE1, PIN_PE2, PIN_PE3, PIN_PF0, PIN_PF1,
};

// radio pins for lmic
const lmic_pinmap lmic_pins = {
  .nss = PIN_PA7,
  .rxtx = LMIC_UNUSED_PIN,
  .rst = PIN_PF3,
  .dio = { PIN_PF2, PIN_PF4, PIN_PF5 },
};

static osjob_t sendjob;  // lmic job that runs do_send

// ---- TDMA schedule ----
// defaults until the 1st downlink, keep same as TDMA_SLOTS / TDMA_SLOT_S in TaskGenerator.py
const uint8_t DEFAULT_SLOTS = 4;         // 4 nodes, 1 slot each
const uint32_t DEFAULT_SLOT_MS = 15000;  // 15 s per slot -> 60 s frame
static_assert(NODE_NUMBER >= 1 && NODE_NUMBER <= DEFAULT_SLOTS,
              "NODE_NUMBER has no slot in the default schedule");
const uint32_t MIN_FRAME_MS = 10000;   // shortest frame we accept (duty cycle)
const uint32_t MAX_FRAME_MS = 600000;  // longest frame we accept (10 min)

uint8_t slotIndex = NODE_NUMBER - 1;                 // our slot, 0 based
uint8_t numSlots = DEFAULT_SLOTS;                    // slots per frame
uint32_t frameMs = DEFAULT_SLOTS * DEFAULT_SLOT_MS;  // frame length in ms
uint32_t nextSlotAt = 0;          // millis() of our next slot
uint32_t txStartedAt = 0;         // millis() when our last data uplink started tx
bool dataFrameInFlight = false;   // true while OUR uplink is being sent (not lmic's own MAC one)
bool synced = false;              // got a schedule from the server at least once
uint32_t slotsUsed = 0, resyncs = 0, tasksSkipped = 0;  // counters for the debug prints

// sleep timer: RTC PIT from the 1.024 kHz ULP clock / 64 = 16 ticks per sec
const uint16_t PIT_TICKS_PER_S = 16;
// pitTicks is 16 bit so the longest sleep has to fit in it
static_assert(((2UL * MAX_FRAME_MS / 1000UL + 1UL) * PIT_TICKS_PER_S) < 65535UL,
              "pitTicks (16 bits) would overflow in the longest sleep");

// length of 1 PIT tick in us, measured in setup() bc the ULP clock is only +-10 % accurate
uint32_t usPerTick = 1000000UL / PIT_TICKS_PER_S;

// tx power limit in dBm for every frame (joins too). the 3.3 V rail cant give enough current for
// full power so we start at 10 and go lower if a tx causes a brown-out
const int8_t TX_POWER_DBM = 10;      // starting limit
const int8_t TX_POWER_MIN_DBM = 2;   // never go below this
const int8_t TX_POWER_STEP_DB = 2;   // how much to lower after a brown-out during tx
static_assert(TX_POWER_DBM >= 2 && TX_POWER_DBM <= 17, "TX_POWER_DBM must be 2..17 dBm");
static_assert(TX_POWER_MIN_DBM >= 2 && TX_POWER_MIN_DBM <= TX_POWER_DBM, "TX_POWER_MIN_DBM must be 2..TX_POWER_DBM");
static_assert(TX_POWER_STEP_DB >= 1, "TX_POWER_STEP_DB must be at least 1 dB");

// stuff saved in EEPROM so it survives a reset
struct Settings
{
  uint32_t magic;      // SETTINGS_MAGIC if the data is valid
  int8_t txPowerMax;   // the TX_POWER_DBM this was saved with
  int8_t txPowerCap;   // current tx power limit, dBm
  uint8_t brownOuts;   // num of brown-outs during tx (max 255)
  uint16_t devNonce;   // next join nonce
};
const uint32_t SETTINGS_MAGIC = 0x4E4F4431;  // "NOD1"
const int SETTINGS_ADDR = 0;                 // EEPROM address
Settings settings;

// what the node was doing when it reset. .noinit = not cleared at startup, so it survives a
// brown-out / watchdog reset (not a power cycle)
struct BootTrace
{
  uint32_t magic;       // TRACE_MAGIC if the data is valid
  uint8_t phase;        // PHASE_* below
  uint8_t brownOutRun;  // brown-outs in a row
  uint8_t culprits;     // CULPRIT_* bits: parts that caused brown-outs and stay off
  uint8_t gasOn;        // 1 while the ENS160 heater is on
  uint8_t fails[3];     // brown-outs in a row caused by J3, J4, gas heater
};
const uint32_t TRACE_MAGIC = 0x54524143;  // "TRAC"
const uint8_t PHASE_IDLE = 0;    // nothing special
const uint8_t PHASE_TX = 1;      // radio is transmitting
const uint8_t PHASE_RAIL_A = 2;  // J3 is being turned on / used
const uint8_t PHASE_RAIL_B = 3;  // J4 is being turned on / used
const uint8_t PHASE_GAS_READ = 4;  // reading the ENS160 in the reply slot (experimental)
BootTrace bootTrace __attribute__((section(".noinit")));
uint8_t bootPrevPhase = PHASE_IDLE;  // phase at the last reset
bool bootPrevValid = false;          // true if bootTrace had valid data at boot

// which part gets blamed for a brown-out. after CULPRIT_AFTER in a row that part stays off
const uint8_t CULPRIT_RAIL_A = 0x01;  // J3
const uint8_t CULPRIT_RAIL_B = 0x02;  // J4
const uint8_t CULPRIT_GAS = 0x04;     // ENS160 heater
const uint8_t CULPRIT_AFTER = 3;
const char* const CULPRIT_NAMES[3] = { "J3 (switching it on)", "J4 (switching it on)", "ENS160 gas sensing (its heater)" };

uint8_t resetFlags = 0;  // reset reason: 0x01 power-on, 0x02 brown-out, 0x08 watchdog

// after a brown-out the node sleeps before doing anything so the storage can charge.
// the wait doubles every time until the max
const uint16_t BROWNOUT_WAIT_S = 30;            // 1st wait
const uint16_t BROWNOUT_WAIT_MAX_S = 480;       // longest wait
const uint32_t SENSOR_RETRY_MS = 3600000UL;     // retry the turned off parts after 1 h
const uint8_t GOOD_UPLINKS = 3;                 // this many ok uplinks = brown-out count cleared
uint8_t goodUplinks = 0;

// storage voltage divider: R1 from storage + to H5 pin 1, R2 from H5 pin 1 to gnd.
// VSTO_CAL = multimeter voltage / printed voltage, set once per board
const uint32_t VSTO_R_TOP = 1000000;     // R1 in ohms
const uint32_t VSTO_R_BOTTOM = 1000000;  // R2 in ohms
const float VSTO_CAL = 1.000;
static_assert(VSTO_R_TOP >= VSTO_R_BOTTOM, "VSTO_R_TOP must be at least VSTO_R_BOTTOM");

// ---- energy sent to the server ----
// energy = ENERGY_CAPACITY x (V^2 - Vempty^2) / (Vfull^2 - Vempty^2), bc E = C V^2 / 2
// capacity and costs have to match TaskGenerator.py on the server
const uint16_t VSTO_FULL_MV = 3600;   // storage full
const uint16_t VSTO_EMPTY_MV = 2800;  // PMIC cuts the board off below this
const uint16_t ENERGY_CAPACITY = 200;
const uint16_t COST_HUMIDITY = 10;
const uint16_t COST_TEMPERATURE = 10;
const uint16_t COST_GAS = 30;
static_assert(VSTO_EMPTY_MV < VSTO_FULL_MV, "VSTO_EMPTY_MV must be below VSTO_FULL_MV");

const uint8_t DOWNLINK_PORT = 20;       // TDMA downlinks come on this port
const uint8_t CMD_NONE = 0x00;          // no task, sync only
const uint8_t CMD_HUMIDITY = 0x01;
const uint8_t CMD_TEMPERATURE = 0x02;
const uint8_t CMD_GAS = 0x03;
const uint8_t CMD_RESET_ENERGY = 0x10;  // for the Heltec nodes, ignored here
const uint8_t TDMA_DOWNLINK_LEN = 6;       // short downlink
const uint8_t TDMA_DOWNLINK_LONG_LEN = 8;  // long downlink (frames > 65 s)
const uint8_t SIGNED_CORRECTION_FLAG = 0x80;  // bit 7 of byte 1: correction is signed
const uint32_t GAS_WARMUP_MS = 60000;      // ENS160 heats this long before the gas reply
bool gasStartPending = false;              // gas task waiting for its warm-up to start

// uplink pkts (fPort 1), 16 bit values are big-endian:
//   status, 15 bytes: [0] 0x00, [1-2] TVOC ppb, [3-4] eCO2 ppm, [5-6] temp x100, [7-8] hum x100,
//     [9-10] storage mV, [11] AQI, [12] ENS160 status, [13] tx power cap dBm, [14] reset flags
//   hum / temp reply, 3 bytes: [0] 0x01 / 0x02, [1-2] value x100
//   gas reply, 7 bytes: [0] 0x03, [1-2] TVOC, [3-4] eCO2, [5] AQI, [6] ENS160 status
//   + 2 bytes of energy at the end of every pkt
const uint8_t PKT_STATUS = 0x00;

const int16_t NO_READING = 0x7FFF;    // sent when the SHT41 didnt answer
const int16_t NOT_MEASURED = 0x7FFE;  // sent when temp / hum wasnt measured (status pkt)

// ENS160 status byte in the pkts: 0..3 is from the sensor, the rest are ours
const uint8_t ENS_NOT_MEASURED = 0xFC;  // no gas reading asked (status pkt)
const uint8_t ENS_NO_SAMPLE = 0xFD;     // sensor on but no new sample
const uint8_t ENS_NO_ANSWER = 0xFE;     // was found before but no i2c answer now
const uint8_t ENS_ABSENT = 0xFF;        // not connected / not found

// 1 set of sensor values
struct Reading
{
  int16_t tempScaled;  // C x100
  int16_t humScaled;   // %RH x100
  uint16_t tvoc;       // ppb
  uint16_t eco2;       // ppm
  uint8_t aqi;         // 1..5, 0 = none
  uint8_t ensStatus;
};
void readTask(uint8_t cmd, Reading &r);  // prototype here so the IDE doesnt put its own above the struct

uint8_t pendingCommand = 0;  // task to answer in the next slot, 0 = none
bool sleepPending = false;   // uplink is done, ok to sleep until the next slot

// true if lmic still has smth to send (our data, a join, or its own MAC reply).
// dont sleep or send while this is true or lmic gets stuck
static bool lmicTxBusy()
{
  return (LMIC.opmode & (OP_TXRXPEND | OP_TXDATA | OP_POLL | OP_JOINING)) != 0;
}

// downlink counters, a jump in the frame counter = we missed some
int32_t lastDownlinkFCnt = -1;
uint32_t downlinksReceived = 0;
uint32_t downlinksMissed = 0;

// the core's millis counter. it stops in power-down so sleepUntil() adds the slept time back
extern "C" volatile uint32_t timer_millis;

volatile uint16_t pitTicks = 0;  // counts PIT ticks, changed in the ISR

// ---- i2c timeout (EXPERIMENTAL, not tested on hardware yet) ----
// Wire has no timeout, so a stuck sensor hangs the node until the watchdog resets it.
// between i2cGuardStart() and i2cGuardStop() the PIT ISR counts ticks, and after 3 s it ends
// the stuck transfer so the read just fails normally
extern "C" void TWI_MasterTransactionFinished(uint8_t result);  // from MegaCoreX Wire (twi.c)
const uint8_t TWI_RESULT_FAIL = 0x06;                             // TWIM_RESULT_FAIL in twi.h
const uint8_t I2C_GUARD_TICKS = 3 * 16;                           // 3 s in PIT ticks
volatile bool i2cGuard = false;       // true while a sensor access is being timed
volatile bool i2cGuardFired = false;  // true if the timeout happened
volatile uint8_t i2cGuardTicks = 0;   // ticks since i2cGuardStart()

// PIT interrupt, wakes the mcu and counts 1 tick
ISR(RTC_PIT_vect)
{
  RTC.PITINTFLAGS = RTC_PI_bm;  // clear the flag
  pitTicks++;
#if I2C_TIMEOUT_GUARD
  if (i2cGuard && ++i2cGuardTicks >= I2C_GUARD_TICKS)
  {
    TWI_MasterTransactionFinished(TWI_RESULT_FAIL);  // took too long, end the i2c transfer
    i2cGuardTicks = I2C_GUARD_TICKS;                 // stay at the limit (no overflow)
    i2cGuardFired = true;
  }
#endif
}

// start timing a sensor access
void i2cGuardStart()
{
  noInterrupts();
  i2cGuardTicks = 0;
  i2cGuardFired = false;
  i2cGuard = true;
  interrupts();
}

// stop timing, print if it timed out
void i2cGuardStop()
{
  i2cGuard = false;
  if (i2cGuardFired)
    DBGLN("I2C timed out: sensor access aborted (EXPERIMENTAL guard)");
}

// reset the watchdog timer
void watchdogKick()
{
  __asm__ __volatile__("wdr");
}

// read pitTicks w/ interrupts off (its 16 bit on an 8 bit mcu)
uint16_t readPitTicks()
{
  noInterrupts();
  uint16_t ticks = pitTicks;
  interrupts();
  return ticks;
}

// measure how long 1 PIT tick really is, using micros(). takes abt 4 s
uint32_t measurePitTick()
{
  const uint16_t TICKS = 4 * PIT_TICKS_PER_S;  // measure over 64 ticks
  uint16_t t = readPitTicks();
  while (readPitTicks() == t) { LowPower.idle(); watchdogKick(); }  // wait for a tick edge
  uint32_t start = micros();  // start time
  t = readPitTicks();
  while ((uint16_t)(readPitTicks() - t) < TICKS) { LowPower.idle(); watchdogKick(); }  // wait 64 ticks
  return (micros() - start) / TICKS;  // avg us per tick
}

// sleep until millis() == target. power-down for most of it, then idle for the last bit
// so we wake up at the exact ms
void sleepUntil(uint32_t target)
{
#if DEBUG
  Serial.flush();  // finish printing before sleeping
#endif
  static uint32_t usCarry = 0;  // leftover us (< 1 ms) from the last sleep

  // wait for a tick edge so we count whole ticks
  uint16_t t = readPitTicks();
  while (readPitTicks() == t && (int32_t)(target - millis()) > 0)
  {
    LowPower.idle();
    watchdogKick();
  }

  int32_t left = (int32_t)(target - millis());  // ms left to sleep
  uint32_t ticks = left > 0 ? (uint32_t)left * 1000UL / usPerTick : 0;  // same thing in ticks
  if (ticks > 0)
  {
    ticks--;  // 1 tick less so we dont wake up late
    noInterrupts();
    pitTicks = 0;  // start counting from 0
    interrupts();
    while (readPitTicks() < ticks)
    {
      LowPower.powerDown();  // sleep, the PIT wakes us every tick
      watchdogKick();        // watchdog still runs in power-down
    }
    uint32_t us = ticks * usPerTick + usCarry;  // time we slept in us
    usCarry = us % 1000UL;                      // keep the part under 1 ms for next time
    noInterrupts();
    timer_millis += us / 1000UL;  // add the slept time to millis()
    interrupts();
  }

  // idle for whats left (millis runs in idle)
  while ((int32_t)(target - millis()) > 0)
  {
    LowPower.idle();
    watchdogKick();
  }
}

// storage voltage (mV) -> energy units
uint16_t energyUnits(uint16_t mv)
{
  if (mv == 0)
    return ENERGY_CAPACITY;  // no measurement (VSTO_SENSE off), say full
  if (mv <= VSTO_EMPTY_MV)
    return 0;  // empty
  if (mv >= VSTO_FULL_MV)
    return ENERGY_CAPACITY;  // full
  float empty2 = (float)VSTO_EMPTY_MV * VSTO_EMPTY_MV;       // Vempty^2
  float usable = (float)mv * mv - empty2;                    // V^2 - Vempty^2
  float full = (float)VSTO_FULL_MV * VSTO_FULL_MV - empty2;  // Vfull^2 - Vempty^2
  return (uint16_t)(ENERGY_CAPACITY * usable / full + 0.5);  // scale + round
}

// energy cost of a task
uint16_t taskCost(uint8_t cmd)
{
  if (cmd == CMD_HUMIDITY)
    return COST_HUMIDITY;
  if (cmd == CMD_TEMPERATURE)
    return COST_TEMPERATURE;
  if (cmd == CMD_GAS)
    return COST_GAS;
  return 0;
}

// read the schedule from a downlink. next slot = uplink time + 1 frame + correction.
// the correction can be negative (signed flag) for a node that came in late
void applySchedule(const uint8_t* d, uint8_t len, uint32_t uplinkAt)
{
  slotIndex = d[1] & 0x7F;                        // low 7 bits = slot idx
  bool isSigned = d[1] & SIGNED_CORRECTION_FLAG;  // bit 7 = correction is signed
  numSlots = d[2];
  uint32_t frame;
  int32_t correction;
  if (len >= TDMA_DOWNLINK_LONG_LEN)
  {
    // long format: 16 bit frame (s), 24 bit correction (ms)
    frame = (((uint32_t)d[3] << 8) | d[4]) * 1000UL;
    uint32_t raw = ((uint32_t)d[5] << 16) | ((uint32_t)d[6] << 8) | d[7];
    correction = (isSigned && (raw & 0x800000UL)) ? (int32_t)raw - 0x1000000L : (int32_t)raw;  // 24 bit two's complement
  }
  else
  {
    // short format: 8 bit frame (s), 16 bit correction (ms)
    frame = (uint32_t)d[3] * 1000UL;
    uint16_t raw = ((uint16_t)d[4] << 8) | d[5];
    correction = isSigned ? (int32_t)(int16_t)raw : (int32_t)raw;
  }
  if (frame >= MIN_FRAME_MS && frame <= MAX_FRAME_MS)
    frameMs = frame;  // only use it if its in range
  // ok range: up to 1 frame later or half a frame earlier, anything else = bad data
  if (correction > (int32_t)frameMs || correction < -(int32_t)(frameMs / 2))
    correction = 0;
  nextSlotAt = uplinkAt + frameMs + (uint32_t)correction;
  resyncs++;
  synced = true;

  DBG("  TDMA sync: slot ");
  DBG(slotIndex);
  DBG("/");
  DBG(numSlots);
  DBG(", frame ");
  DBG(frameMs / 1000);
  DBG(" s, correction ");
  DBG(correction);
  DBGLN(" ms");
}

// save settings to EEPROM (put only writes the bytes that changed)
void saveSettings()
{
  EEPROM.put(SETTINGS_ADDR, settings);
}

// load settings from EEPROM, or make new ones if its empty / old. call after LMIC_reset()
void loadSettings()
{
  EEPROM.get(SETTINGS_ADDR, settings);
  bool valid = settings.magic == SETTINGS_MAGIC && settings.txPowerMax == TX_POWER_DBM &&
               settings.txPowerCap >= TX_POWER_MIN_DBM && settings.txPowerCap <= TX_POWER_DBM;
  if (valid)
    return;  // alrd good

  settings.magic = SETTINGS_MAGIC;
  settings.txPowerMax = TX_POWER_DBM;
  settings.txPowerCap = TX_POWER_DBM;
  settings.brownOuts = 0;
  settings.devNonce = LMIC.devNonce;  // lmic's random nonce as the 1st one
  saveSettings();
  DBGLN("Settings initialised in EEPROM");
}

// if the last reset was a brown-out during tx, lower the tx power limit and save it
void learnFromBrownOut()
{
  bool duringTx = bootPrevValid && bootPrevPhase == PHASE_TX;  // was the radio transmitting?
  bootTrace.magic = TRACE_MAGIC;
  bootTrace.phase = PHASE_IDLE;

  // only for a real brown-out (power-on also sets the brown-out flag) that happened during tx
  if (!(resetFlags & RSTCTRL_BORF_bm) || (resetFlags & RSTCTRL_PORF_bm) || !duringTx)
    return;

  if (settings.brownOuts < 255)
    settings.brownOuts++;
  if (settings.txPowerCap - TX_POWER_STEP_DB >= TX_POWER_MIN_DBM)
    settings.txPowerCap -= TX_POWER_STEP_DB;  // 1 step lower
  else
    settings.txPowerCap = TX_POWER_MIN_DBM;  // alrd at the min
  saveSettings();

  DBG("Brown-out during a transmission (");
  DBG(settings.brownOuts);
  DBG(" so far): TX power cap now ");
  DBG(settings.txPowerCap);
  DBGLN(" dBm");
}

// put the radio to sleep right at boot (it starts in standby, abt 1.6 mA) w/o waiting for lmic.
// just reads RegOpMode and writes it back w/ the mode bits = 000 (sleep)
void radioSleepEarly()
{
  const uint8_t SX1276_REG_OPMODE = 0x01;      // RegOpMode address
  const uint8_t SX1276_OPMODE_MODE_gm = 0x07;  // mode bits, 000 = sleep

  // NSS high first, then make it an output
  PORT_t* nssPort = digitalPinToPortStruct(lmic_pins.nss);
  uint8_t nssMask = digitalPinToBitMask(lmic_pins.nss);
  nssPort->OUTSET = nssMask;
  nssPort->DIRSET = nssMask;
  PORTA.PIN5CTRL |= PORT_PULLUPEN_bm;  // pull-up on MISO so it doesnt float
  SPI.begin();
  delay(10);  // radio needs 10 ms after power-on before spi works

  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(lmic_pins.nss, LOW);
  SPI.transfer(SX1276_REG_OPMODE & 0x7F);  // bit 7 = 0 -> read
  uint8_t opMode = SPI.transfer(0x00);     // current value
  digitalWrite(lmic_pins.nss, HIGH);
  digitalWrite(lmic_pins.nss, LOW);
  SPI.transfer(SX1276_REG_OPMODE | 0x80);  // bit 7 = 1 -> write
  SPI.transfer((uint8_t)(opMode & ~SX1276_OPMODE_MODE_gm));  // same value but mode = sleep
  digitalWrite(lmic_pins.nss, HIGH);
  SPI.endTransaction();
}

// runs at boot: counts brown-outs in a row, blames a part if it can, then sleeps so the
// storage can charge. has to run before learnFromBrownOut()
void brownOutBackOff()
{
  bool brownOut = (resetFlags & RSTCTRL_BORF_bm) && !(resetFlags & RSTCTRL_PORF_bm);  // real brown-out?
  bootPrevValid = bootTrace.magic == TRACE_MAGIC;  // is the trace valid?
  bootPrevPhase = bootTrace.phase;                 // what we were doing at the reset

  // power-on or new flash -> forget everything, try all sensors again
  if (!bootPrevValid || (resetFlags & (RSTCTRL_PORF_bm | RSTCTRL_UPDIRF_bm)))
  {
    bootTrace.culprits = 0;
    bootTrace.fails[0] = bootTrace.fails[1] = bootTrace.fails[2] = 0;
  }

  // experimental: a watchdog reset while talking to a sensor (stuck i2c) counts like a brown-out
  bool sensorHang = WATCHDOG_COUNTS_AS_SENSOR_FAULT && (resetFlags & RSTCTRL_WDRF_bm) &&
                    !(resetFlags & RSTCTRL_PORF_bm) &&
                    (bootPrevPhase == PHASE_RAIL_A || bootPrevPhase == PHASE_RAIL_B ||
                     bootPrevPhase == PHASE_GAS_READ);

  // find which part was on when the reset happened
  uint8_t culprit = 0, idx = 0;
  if (bootPrevValid && (brownOut || sensorHang))
  {
    if (bootPrevPhase == PHASE_RAIL_A)
      culprit = CULPRIT_RAIL_A, idx = 0;  // J3
    else if (bootPrevPhase == PHASE_RAIL_B)
      culprit = CULPRIT_RAIL_B, idx = 1;  // J4
    else if (bootTrace.gasOn || bootPrevPhase == PHASE_GAS_READ)
      culprit = CULPRIT_GAS, idx = 2;     // gas sensor
  }
  if (culprit)
  {
    if (bootTrace.fails[idx] < 255)
      bootTrace.fails[idx]++;
    DBG(brownOut ? "Brown-out pinned on " : "Watchdog reset (sensor hang) pinned on ");
    DBG(CULPRIT_NAMES[idx]);
    DBG(", ");
    DBG(bootTrace.fails[idx]);
    DBG(" of ");
    DBG(CULPRIT_AFTER);
    DBGLN(bootTrace.fails[idx] >= CULPRIT_AFTER ? ": leaving it off" : ": will try again");
    if (bootTrace.fails[idx] >= CULPRIT_AFTER)
      bootTrace.culprits |= culprit;  // too many times, keep it off
  }
  bootTrace.gasOn = 0;  // heater is off after a reset

  // count brown-outs in a row that we couldnt blame on a part
  if (!bootPrevValid || !brownOut)
    bootTrace.brownOutRun = 0;
  else if (!culprit && bootTrace.brownOutRun < 255)
    bootTrace.brownOutRun++;
  // make the trace valid now so the next boot can use it even if we brown out early
  if (!bootPrevValid)
  {
    bootTrace.magic = TRACE_MAGIC;
    bootTrace.phase = PHASE_IDLE;
    bootTrace.gasOn = 0;
  }

  // print what is turned off
  if (bootTrace.culprits)
  {
    DBG("Left off after brown-outs:");
    if (bootTrace.culprits & CULPRIT_RAIL_A) DBG(" J3 (switching it on)");
    if (bootTrace.culprits & CULPRIT_RAIL_B) DBG(" J4 (switching it on)");
    if (bootTrace.culprits & CULPRIT_GAS) DBG(" ENS160 gas sensing (its heater)");
    DBGLN(" - power-cycle to try again");
  }

  uint8_t run = culprit ? 1 : bootTrace.brownOutRun;  // a blamed one still waits once
  if (run == 0)
    return;  // no brown-out, no wait
  uint32_t wait = (uint32_t)BROWNOUT_WAIT_S << (run - 1 < 5 ? run - 1 : 5);  // 30, 60, 120... s
  if (wait > BROWNOUT_WAIT_MAX_S)
    wait = BROWNOUT_WAIT_MAX_S;

  DBG("Brown-out reset ");
  DBG(run);
  DBG(" in a row: sleeping ");
  DBG(wait);
  DBGLN(" s so the storage can recharge");
#if DEBUG
  Serial.flush();
#endif
  uint32_t restTicks = wait * PIT_TICKS_PER_S;  // wait in PIT ticks
  noInterrupts();
  pitTicks = 0;
  interrupts();
  while (readPitTicks() < restTicks)
  {
    LowPower.powerDown();  // sleep
    watchdogKick();
  }
}

// move the i2c to header J3 or J4 (swap only works w/ a new Wire.begin())
void selectBus(uint8_t bus)
{
  if (bus == currentBus)
    return;  // alrd there
  Wire.end();
  Wire.swap(bus);
  Wire.begin();
  currentBus = bus;
}

// ---- sensor power ----
// turning a header on in 1 go browns the node out, so the enable pin is pulsed w/ longer and
// longer on times (50 us up to 800 us) to charge the sensor board slowly. takes abt 70 ms.
// test results are in bench/sequence_test
const uint16_t RAMP_FROM_US = 50;   // 1st on time
const uint16_t RAMP_TO_US = 800;    // last on time
const uint8_t RAMP_STEP_US = 5;     // on time grows by this each pulse
const uint8_t RAMP_OFF_US = 20;     // off time between pulses

// pulse an enable pin on, out = port register, mask = pin bit
void railRamp(volatile uint8_t &out, uint8_t mask)
{
  for (uint16_t on = RAMP_FROM_US; on <= RAMP_TO_US; on += RAMP_STEP_US)
  {
    out |= mask;   // on
    delayMicroseconds(on);
    out &= ~mask;  // off
    delayMicroseconds(RAMP_OFF_US);
  }
  out |= mask;  // stay on
}

// turn a header on and put the i2c on it. returns false if that header is kept off
bool headerOn(uint8_t bus)
{
  bool j3 = bus == BUS_J3;
  if (bootTrace.culprits & (j3 ? CULPRIT_RAIL_A : CULPRIT_RAIL_B))
    return false;  // this header caused brown-outs, leave it off
  bootTrace.phase = j3 ? PHASE_RAIL_A : PHASE_RAIL_B;  // remember it in case we brown out
  if (j3)
    railRamp(VPORTD.OUT, PIN6_bm);  // PD6 = J3 enable
  else
    railRamp(VPORTC.OUT, PIN1_bm);  // PC1 = J4 enable
  delay(5);  // let the sensor power up
  LowPower.enablePinISC(j3 ? PIN_PA2 : PIN_PC2);  // turn the i2c pins back on
  LowPower.enablePinISC(j3 ? PIN_PA3 : PIN_PC3);
  currentBus = 0xFF;  // force a new Wire.begin()
  selectBus(bus);
  return true;
}

// turn a header off and park its i2c pins
void headerOff(uint8_t bus)
{
  bool j3 = bus == BUS_J3;
  Wire.end();
  currentBus = 0xFF;
  LowPower.disablePinISC(j3 ? PIN_PA2 : PIN_PC2);  // i2c pins off (also removes the pull-ups)
  LowPower.disablePinISC(j3 ? PIN_PA3 : PIN_PC3);
  if (j3)
    digitalWriteFast(PIN_RAIL_A, LOW);
  else
    digitalWriteFast(PIN_RAIL_B, LOW);
  bootTrace.phase = PHASE_IDLE;
  bootTrace.fails[j3 ? 0 : 1] = 0;  // it worked, reset its brown-out count
}

// look for a sensor on J3 then J4. sht = true looks for the SHT41, false for the ENS160.
// w/ USE_DHT11 only J4 is searched, bc the DHT11 data pin on J3 shouldnt get i2c traffic
void findSensor(bool sht)
{
  if (sht)
    shtSearched = true;
  else
    ensSearched = true;
  // try each header until the sensor is found
  for (uint8_t bus = USE_DHT11 ? BUS_J4 : BUS_J3; bus <= BUS_J4 && !(sht ? shtFound : ens160Found);
       bus++)
  {
#if USE_ENS160
    bool alreadyOn = gasWarming && bus == ensBus;  // header alrd on for a gas task, dont touch its power
#else
    bool alreadyOn = false;
#endif
    if (alreadyOn)
      selectBus(bus);
    else if (!headerOn(bus))
      continue;  // header is kept off, skip it
    watchdogKick();
    i2cGuardStart();  // time the i2c access
#if USE_ENS160
    // is the ENS160 on this header?
    if (!ens160Found && ens160Probe())
    {
      ens160Found = true;
      ensBus = bus;
      DBG("ENS160 found at 0x");
      DBG(ens160Address(), HEX);
      DBGLN(bus == BUS_J3 ? " on J3" : " on J4");
    }
#endif
    // is the SHT41 on this header?
    if (!shtFound && sht4.begin())
    {
      shtFound = true;
      shtBus = bus;
      DBGLN(bus == BUS_J3 ? "SHT41 found on J3" : "SHT41 found on J4");
      sht4.setPrecision(SHT4X_HIGH_PRECISION);
      sht4.setHeater(SHT4X_NO_HEATER);
    }
    i2cGuardStop();
    if (!alreadyOn)
      headerOff(bus);  // done looking, power off again
  }
  if (sht && !shtFound)
    DBGLN("Could not find SHT41 on J3 or J4, check wiring!");
#if USE_ENS160
  if (!sht && !ens160Found)
    DBGLN("Could not find ENS160 on J3 or J4, check wiring!");
#endif
}

#if USE_ENS160
// turn the ENS160 on and start its heater for a gas task
void gasStart()
{
  if (gasWarming)
    return;  // alrd heating
  if (!ens160Found && !ensSearched && !(bootTrace.culprits & CULPRIT_GAS))
    findSensor(false);  // 1st gas task, look for the sensor
  if (!ens160Found)
    return;
  if (bootTrace.culprits & CULPRIT_GAS)
  {
    DBGLN("ENS160 left off: its heater browned the node out before");
    return;
  }
  if (!headerOn(ensBus))
  {
    DBGLN("ENS160 header left off after brown-outs");
    return;
  }
  i2cGuardStart();
  ens160SetMode(ENS160_OPMODE_RESET);  // reset the sensor
  delay(100);
  watchdogKick();
  bootTrace.phase = PHASE_IDLE;  // header is up, a brown-out from here is the heater
  bootTrace.gasOn = 1;
  uint8_t mode = 0xFF;
  bool ok = ens160SetMode(ENS160_OPMODE_IDLE);  // idle 1st, then standard (= gas sensing)
  delay(10);
  ok = ok && ens160SetMode(ENS160_OPMODE_STANDARD) && ens160GetMode(mode) && mode == ENS160_OPMODE_STANDARD;
  if (!ok)
  {
    DBGLN("ENS160 did not start gas sensing");
    i2cGuardStop();
    bootTrace.gasOn = 0;
    headerOff(ensBus);
    return;
  }
  i2cGuardStop();
  gasWarming = true;
  gasSince = millis();
  DBGLN("ENS160 on and heating for the gas task, read in the next slot");
}

// turn the ENS160 off
void gasStop()
{
  if (!gasWarming)
    return;  // alrd off
  gasWarming = false;
  bootTrace.gasOn = 0;
  headerOff(ensBus);
}
#endif

#if USE_DHT11
// ---- DHT11 on J3 (node 4) ----
// 3 pin DHT11: VCC on the J3 rail, data on PA2, GND. uses the board's i2c pull-up on that pin.
// 1 wire protocol: we pull the line low for 20 ms, the sensor answers 80 us low + 80 us high,
// then sends 40 bits. each bit = 50 us low then a short high (0) or a long high (1).
// bytes: hum int, hum decimal, temp int, temp decimal, checksum
const uint16_t DHT_POWERUP_MS = 1100;  // sensor needs 1 s after power-up
const uint16_t DHT_RETRY_MS = 1100;    // and 1 s between 2 reads
const uint16_t DHT_TIMEOUT = 1000;     // loop count before we say the pulse is missing (abt 1 ms)
const uint16_t DHT_MISSING = 0xFFFF;   // dhtPulse() returns this on a timeout

// wait ms in idle (not delay) and keep the watchdog happy
void dhtWait(uint16_t ms)
{
  uint32_t t0 = millis();
  while (millis() - t0 < ms)
  {
    LowPower.idle();
    watchdogKick();
  }
}

// count loops while PA2 stays at `level`, DHT_MISSING if it takes too long
static inline uint16_t dhtPulse(bool level)
{
  uint16_t n = 0;
  while (((VPORTA.IN & PIN2_bm) != 0) == level)
    if (++n >= DHT_TIMEOUT)
      return DHT_MISSING;
  return n;
}

// 1 read of the DHT11, true if the checksum is ok
bool dhtReadOnce(int16_t &tempX100, int16_t &humX100)
{
  uint8_t d[5] = { 0, 0, 0, 0, 0 };  // the 5 bytes from the sensor
  uint16_t lows[40], highs[40];      // low and high time of each bit

  VPORTA.OUT &= ~PIN2_bm;  // start signal: pull the line low for 20 ms
  VPORTA.DIR |= PIN2_bm;
  dhtWait(20);

  noInterrupts();          // timing matters from here (abt 5 ms)
  VPORTA.DIR &= ~PIN2_bm;  // let go of the line, pull-up takes it high
  delayMicroseconds(40);
  // wait for the sensor's answer: line goes low, 80 us low, 80 us high
  bool ok = dhtPulse(true) != DHT_MISSING && dhtPulse(false) != DHT_MISSING &&
            dhtPulse(true) != DHT_MISSING;
  for (uint8_t i = 0; ok && i < 40; i++)  // measure all 40 bits
  {
    lows[i] = dhtPulse(false);
    highs[i] = dhtPulse(true);
    ok = lows[i] != DHT_MISSING && highs[i] != DHT_MISSING;
  }
  interrupts();
  if (!ok)
  {
    DBGLN("DHT11 did not answer");
    return false;
  }
  for (uint8_t i = 0; i < 40; i++)
  {
    d[i / 8] <<= 1;
    if (highs[i] > lows[i])
      d[i / 8] |= 1;  // high longer than low = bit is 1
  }
  if ((uint8_t)(d[0] + d[1] + d[2] + d[3]) != d[4])  // checksum = sum of the 1st 4 bytes
  {
    DBGLN("DHT11 checksum wrong");
    return false;
  }
  humX100 = (int16_t)d[0] * 100 + (d[1] % 10) * 10;      // hum x100
  int16_t t = (int16_t)d[2] * 100 + (d[3] & 0x0F) * 10;  // temp x100
  tempX100 = (d[3] & 0x80) ? -t : t;                     // bit 7 = below 0 C
  return true;
}

// turn J3 on, wait for the DHT11 to start, read it (1 retry), turn J3 off
bool dhtRead(int16_t &tempX100, int16_t &humX100)
{
  if (bootTrace.culprits & CULPRIT_RAIL_A)
  {
    DBGLN("J3 (DHT11) left off after brown-outs");
    return false;
  }
  bootTrace.phase = PHASE_RAIL_A;  // remember it in case we brown out
  VPORTA.DIR &= ~PIN2_bm;          // data pin = input before the sensor gets power
  LowPower.enablePinISC(PIN_PA2);
  railRamp(VPORTD.OUT, PIN6_bm);   // J3 power on
  dhtWait(DHT_POWERUP_MS);
  bool ok = dhtReadOnce(tempX100, humX100);
  if (!ok)
  {
    dhtWait(DHT_RETRY_MS);
    ok = dhtReadOnce(tempX100, humX100);  // 2nd try
  }
  headerOff(BUS_J3);
  if (ok)
  {
    DBG("DHT11: ");
    DBG(tempX100 / 100.0);
    DBG(" C, ");
    DBG(humX100 / 100.0);
    DBGLN(" %RH");
  }
  return ok;
}
#endif

// do the measurement for a task and put it in r. cmd 0 (status pkt) measures nothing
void readTask(uint8_t cmd, Reading &r)
{
  // start w/ "not measured" in every field
  r.tempScaled = NOT_MEASURED;
  r.humScaled = NOT_MEASURED;
  r.tvoc = 0;
  r.eco2 = 0;
  r.aqi = 0;
  r.ensStatus = ENS_NOT_MEASURED;

  if (cmd == CMD_HUMIDITY || cmd == CMD_TEMPERATURE)
  {
    r.tempScaled = NO_READING;  // stays like this if the sensor doesnt answer
    r.humScaled = NO_READING;
#if USE_DHT11
    // node 4: read the DHT11 instead of the SHT41
    int16_t t, h;
    if (dhtRead(t, h))
    {
      r.tempScaled = t;
      r.humScaled = h;
    }
    return;
#endif
    if (!shtFound && !shtSearched)
      findSensor(true);  // 1st task, look for the sensor
    if (!shtFound)
      return;
#if USE_ENS160
    bool shared = gasWarming && ensBus == shtBus;  // header alrd on bc of a gas task
#else
    bool shared = false;
#endif
    if (!shared && !headerOn(shtBus))
    {
      DBGLN("SHT41 header left off after brown-outs");
      return;
    }
    selectBus(shtBus);
    i2cGuardStart();
    sensors_event_t humEvent, tempEvent;
    if (sht4.getEvent(&humEvent, &tempEvent))  // read temp + hum
    {
      r.tempScaled = (int16_t)(tempEvent.temperature * 100);
      r.humScaled = (int16_t)(humEvent.relative_humidity * 100);
    }
    else
      DBGLN("SHT41 did not answer");
    i2cGuardStop();
    if (!shared)
      headerOff(shtBus);  // done, power off
  }
  else if (cmd == CMD_GAS)
  {
    r.eco2 = 400;  // default values if theres no gas sensor
    r.ensStatus = ENS_ABSENT;
#if USE_ENS160
    if (!gasWarming)
      return;  // sensor never started
    selectBus(ensBus);
    bootTrace.phase = PHASE_GAS_READ;  // gasStop() puts it back to idle
    i2cGuardStart();
    uint8_t status = 0;
    bool fresh = false;
    for (uint8_t i = 0; i < 15 && !fresh; i++)  // wait up to 1.5 s for a new sample
    {
      if (!ens160ReadStatus(status))
        break;  // no i2c answer
      fresh = status & ENS160_STATUS_NEWDAT;
      if (!fresh)
      {
        uint32_t t0 = millis();
        while (millis() - t0 < 100)  // wait 100 ms in idle
          LowPower.idle();
      }
    }
    if (!fresh)
      r.ensStatus = ENS_NO_SAMPLE;
    else if (ens160ReadData(r.aqi, r.tvoc, r.eco2))
    {
      r.ensStatus = (status & ENS160_STATUS_VALIDITY_gm) >> ENS160_STATUS_VALIDITY_gp;  // sensor's own status
      bootTrace.fails[2] = 0;  // heater worked, reset its brown-out count
    }
    else
      r.ensStatus = ENS_NO_ANSWER;
    i2cGuardStop();
    DBG("ENS160 heated ");
    DBG((millis() - gasSince) / 1000);
    DBGLN(" s");
    gasStop();
#endif
  }
}

// read the storage voltage in mV (0 if VSTO_SENSE is off). uses the internal 2.5 V ref
// bc the 3.3 V rail isnt stable. takes abt 3 ms
uint16_t readVstoMv()
{
#if VSTO_SENSE
  ADC0.CTRLA |= ADC_ENABLE_bm;  // adc on (its off the rest of the time)
  analogReference(INTERNAL2V5);
  ADC0.CTRLC = (ADC0.CTRLC & ~ADC_PRESC_gm) | ADC_PRESC_DIV32_gc;  // adc clock = 8 MHz / 32 = 250 kHz
  ADC0.SAMPCTRL = 31;      // longest sample time bc the divider is high resistance
  delayMicroseconds(100);  // let the ref settle
  analogRead(PIN_VSTO);    // throw away the 1st reading

  uint32_t sum = 0;
  for (uint8_t i = 0; i < 16; i++)  // avg of 16 readings
    sum += analogRead(PIN_VSTO);
  ADC0.CTRLA &= ~ADC_ENABLE_bm;  // adc off

  float pinVolts = sum / 16.0 * 2.5 / 1023.0;  // adc counts -> volts on the pin
  float vsto = pinVolts * (VSTO_R_TOP + VSTO_R_BOTTOM) / VSTO_R_BOTTOM * VSTO_CAL;  // undo the divider
  return (uint16_t)(vsto * 1000.0 + 0.5);  // V -> mV, rounded
#else
  return 0;
#endif
}

// build and send 1 uplink: the reply to the pending task, or a status pkt if theres none
void do_send(osjob_t* j)
{
  if (lmicTxBusy())
  {
    // lmic is still sending smth, try again in 1 s
    DBGLN("LMIC busy, waiting");
    os_setTimedCallback(j, os_getTime() + sec2osticks(1), do_send);
    return;
  }

  uint16_t vstoMv = readVstoMv();  // measure before the radio turns on
  uint16_t energy = energyUnits(vstoMv);

  // (only w/ SKIP_UNAFFORDABLE_TASKS 1) not enough energy for the task -> skip it, a status pkt goes out instead
  if (SKIP_UNAFFORDABLE_TASKS && pendingCommand != 0 && energy < taskCost(pendingCommand))
  {
    tasksSkipped++;
    DBG("Skipping task 0x");
    DBG(pendingCommand, HEX);
    DBG(": needs ");
    DBG(taskCost(pendingCommand));
    DBG(", energy ");
    DBGLN(energy);
#if USE_ENS160
    if (pendingCommand == CMD_GAS)
      gasStop();  // heater off if it was on
#endif
    pendingCommand = 0;
  }

  Reading r;
  readTask(pendingCommand, r);  // do the measurement

  uint8_t payload[17];  // biggest pkt = status (15) + energy (2)
  uint8_t len = 0;

  if (pendingCommand == CMD_HUMIDITY)
  {
    // hum reply
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
    // temp reply
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
    // gas reply
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
    // no task -> status pkt (sensor fields are "not measured", only voltage is real)
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

    DBG("Sending status packet (no sensors switched on): storage ");
    DBG(vstoMv);
    DBG(" mV, TX cap ");
    DBG(settings.txPowerCap);
    DBGLN(" dBm");
  }

  // energy is always the last 2 bytes
  payload[len++] = highByte(energy);
  payload[len++] = lowByte(energy);
  DBG("  energy ");
  DBG(energy);
  DBG(" / ");
  DBG(ENERGY_CAPACITY);
  DBG(" (storage ");
  DBG(vstoMv);
  DBGLN(" mV)");

  // has to be set BEFORE LMIC_setTxData2, bc EV_TXSTART can fire inside that call
  dataFrameInFlight = true;
  if (LMIC_setTxData2(1, payload, len, 0) != LMIC_ERROR_SUCCESS)  // port 1, unconfirmed
  {
    dataFrameInFlight = false;
    // didnt work, keep the task and try again in 1 s
    DBGLN("LMIC_setTxData2 failed, retrying in 1 s");
    os_setTimedCallback(&sendjob, os_getTime() + sec2osticks(1), do_send);
    return;
  }

  slotsUsed++;
  pendingCommand = 0;  // task is answered
}

// lmic calls this for every radio event
void onEvent(ev_t ev)
{
  switch (ev)
  {
    case EV_JOINING:
      DBGLN("EV_JOINING");
      break;

    case EV_JOIN_TXCOMPLETE:
      bootTrace.phase = PHASE_IDLE;  // tx is over
      DBGLN("EV_JOIN_TXCOMPLETE (no JoinAccept yet)");
      break;

    case EV_JOINED:
      bootTrace.phase = PHASE_IDLE;
      DBGLN("EV_JOINED");
      LMIC_setLinkCheckMode(0);                       // no link check
      LMIC_setAdrMode(0);                             // ADR off
      LMIC_setDrTxpow(DR_SF7, settings.txPowerCap);   // fixed SF7 + our tx power limit
      // no schedule yet so start in our default slot
      nextSlotAt = millis() + 100 + (uint32_t)slotIndex * DEFAULT_SLOT_MS;
      DBG("Unsynced, first uplink in ");
      DBG((int32_t)(nextSlotAt - millis()));
      DBGLN(" ms");
      sleepPending = true;
      break;

    case EV_TXSTART:
      // radio starts right after this, last chance to limit the tx power (joins use 16 dBm)
      if (LMIC.radio.txpow > settings.txPowerCap)
        LMIC.radio.txpow = settings.txPowerCap;

      if (LMIC.opmode & OP_JOINING)
      {
        // save the next join nonce before the tx, so a brown-out here doesnt reuse an old one
        settings.devNonce = LMIC.devNonce;
        saveSettings();
      }
      else if (dataFrameInFlight)
      {
        txStartedAt = millis();  // the slot correction from the server is relative to this
      }

      bootTrace.phase = PHASE_TX;  // radio is on, remember it in case we brown out
      break;

    case EV_RXSTART:
      bootTrace.phase = PHASE_IDLE;  // rx window opened so the tx is over
      break;

    case EV_JOIN_FAILED:
      bootTrace.phase = PHASE_IDLE;  // lmic retries by itself
      DBGLN("EV_JOIN_FAILED");
      break;

    case EV_TXCOMPLETE:
      bootTrace.phase = PHASE_IDLE;
      DBGLN("EV_TXCOMPLETE");

      // got a downlink in rx1 or rx2 -> update the counters
      if (LMIC.txrxFlags & (TXRX_DNW1 | TXRX_DNW2))
      {
        int32_t fcnt = (int32_t)LMIC.seqnoDn - 1;  // counter of this downlink
        downlinksReceived++;
        if (fcnt - lastDownlinkFCnt - 1 > 0)  // counter jumped = missed some
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

    {
      bool scheduled = false;  // true if this downlink had a schedule
      if (LMIC.dataLen > 0)    // downlink has data
      {
        uint8_t port = (LMIC.txrxFlags & TXRX_PORT) ? LMIC.frame[LMIC.dataBeg - 1] : 0;
        DBG("Downlink on port: ");
        DBGLN(port);

        // only use it if its a TDMA downlink that answers OUR uplink
        if (port == DOWNLINK_PORT && LMIC.dataLen >= TDMA_DOWNLINK_LEN && dataFrameInFlight)
        {
          const uint8_t* d = &LMIC.frame[LMIC.dataBeg];  // downlink bytes
          uint8_t cmd = d[0];
          DBG("Downlink command received: 0x");
          DBGLN(cmd, HEX);
          if (cmd == CMD_HUMIDITY || cmd == CMD_TEMPERATURE || cmd == CMD_GAS)
            pendingCommand = cmd;  // answer it in the next slot
#if USE_ENS160
          if (cmd == CMD_GAS)
          {
            // check the energy now, before the heater uses any (only w/ SKIP_UNAFFORDABLE_TASKS 1)
            uint16_t energy = SKIP_UNAFFORDABLE_TASKS ? energyUnits(readVstoMv()) : 0;
            if (SKIP_UNAFFORDABLE_TASKS && energy < taskCost(CMD_GAS))
            {
              tasksSkipped++;
              DBG("Skipping task 0x");
              DBG(cmd, HEX);
              DBG(" at arrival: needs ");
              DBG(taskCost(CMD_GAS));
              DBG(", energy ");
              DBGLN(energy);
              pendingCommand = 0;  // cant afford it
            }
            else
              gasStartPending = true;  // loop() starts the heater 60 s before the slot
          }
#endif
          else if (cmd == CMD_RESET_ENERGY)
            DBGLN("  battery refill ignored: this node reports its real energy");
          applySchedule(d, LMIC.dataLen, txStartedAt);  // update slot timing
          scheduled = true;
        }
      }

      if (dataFrameInFlight && !scheduled)
        nextSlotAt += frameMs;  // no schedule, just go 1 frame later
      if (dataFrameInFlight && goodUplinks < GOOD_UPLINKS && ++goodUplinks == GOOD_UPLINKS)
      {
        bootTrace.brownOutRun = 0;  // node is running fine, clear the brown-out count
        DBGLN("  running steadily: brown-out count cleared");
      }
      dataFrameInFlight = false;

      DBG("  slot ");
      DBG(slotsUsed);
      DBG(synced ? " (synced" : " (free-running");
      DBG(", resyncs ");
      DBG(resyncs);
      DBG(", tasks skipped ");
      DBG(tasksSkipped);
      DBG("), next uplink in ");
      DBG((int32_t)(nextSlotAt - millis()));
      DBGLN(" ms");

      sleepPending = true;  // sleep until the next slot
      break;
    }

    case EV_TXCANCELED:
      bootTrace.phase = PHASE_IDLE;
      DBGLN("EV_TXCANCELED");
      if (dataFrameInFlight)
        nextSlotAt += frameMs;  // try again next frame
      dataFrameInFlight = false;
      sleepPending = true;
      break;

    default:
      break;
  }
}

void setup()
{
  _PROTECTED_WRITE(WDT.CTRLA, WDT_PERIOD_8KCLK_gc);  // watchdog on, 8 s

  resetFlags = RSTCTRL.RSTFR;  // why did we reset
  RSTCTRL.RSTFR = resetFlags;  // clear the flags (write 1 to clear)

  ADC0.CTRLA &= ~ADC_ENABLE_bm;  // adc off, readVstoMv() turns it on when needed

  for (uint8_t i = 0; i < sizeof(UNUSED_PINS); i++)
    LowPower.disablePinISC(UNUSED_PINS[i]);  // unused pins off
  // i2c pins of both headers off too, headerOn() turns them back on
  LowPower.disablePinISC(PIN_PA2);
  LowPower.disablePinISC(PIN_PA3);
  LowPower.disablePinISC(PIN_PC2);
  LowPower.disablePinISC(PIN_PC3);

  // led off, both sensor headers off
  pinMode(PIN_LED, OUTPUT);
  digitalWriteFast(PIN_LED, LOW);
  pinMode(PIN_RAIL_B, OUTPUT);
  digitalWriteFast(PIN_RAIL_B, LOW);
  pinMode(PIN_RAIL_A, OUTPUT);
  digitalWriteFast(PIN_RAIL_A, LOW);

  radioSleepEarly();  // radio to sleep before the brown-out wait

#if DEBUG
  Serial.begin(115200);
  PORTA.PIN1CTRL |= PORT_PULLUPEN_bm;  // pull-up on RX so it doesnt float w/o the usb adapter
  Serial.println("SHT41 + ENS160 LoRaWAN node - TDMA slots, energy from the storage voltage");
  Serial.print("Node number ");
  Serial.println(NODE_NUMBER);
  Serial.print("Reset flags 0x");  // 0x02 = brown-out, 0x08 = watchdog
  Serial.println(resetFlags, HEX);
#else
  LowPower.disablePinISC(PIN_PA0);  // uart pins off
  LowPower.disablePinISC(PIN_PA1);
#endif

  // start the RTC PIT: 1.024 kHz ULP clock / 64 = 16 interrupts per sec
  while (RTC.STATUS > 0) {}           // wait till the RTC is ready
  RTC.CLKSEL = RTC_CLKSEL_INT1K_gc;   // 1.024 kHz clock
  RTC.PITINTCTRL = RTC_PI_bm;         // PIT interrupt on
  while (RTC.PITSTATUS > 0) {}
  RTC.PITCTRLA = RTC_PERIOD_CYC64_gc | RTC_PITEN_bm;  // / 64 and enable

  brownOutBackOff();  // if we just browned out, sleep here before using any power

  usPerTick = measurePitTick();  // calibrate the sleep timer (abt 4 s)
  DBG("Sleep clock: one PIT tick = ");
  DBG(usPerTick);
  DBGLN(" us");

  uint16_t bootMv = readVstoMv();  // print the voltage at boot (for calibrating VSTO_CAL)
  DBG("Storage voltage ");
  DBG(bootMv);
  DBG(" mV, energy ");
  DBGLN(energyUnits(bootMv));

  DBGLN("Sensors off: each one is looked for and powered only when a task needs it");

  os_init();     // start lmic
  LMIC_reset();
  LMIC_setClockError(MAX_CLOCK_ERROR * 2 / 100);  // internal clock is +-2 %, make the rx windows wider
  PORTA.PIN5CTRL |= PORT_PULLUPEN_bm;  // pull-up on MISO so it doesnt float

  loadSettings();        // has to be after LMIC_reset()
  learnFromBrownOut();   // lower the tx power if the last reset was a brown-out during tx
  LMIC.devNonce = settings.devNonce;  // continue the join nonce from EEPROM
  DBG("TX power cap ");
  DBG(settings.txPowerCap);
  DBG(" dBm, brown-outs during TX ");
  DBG(settings.brownOuts);
  DBG(", next DevNonce ");
  DBGLN(settings.devNonce);

  LMIC_startJoining();  // start the OTAA join
}

// short power-down naps in loop() while lmic is just waiting (between joins, duty cycle)
const uint32_t NAP_MS = 2000;        // longest nap
const uint32_t NAP_GUARD_MS = 3000;  // only nap if lmic's next job is at least this far away
const int32_t NAP_MIN_MS = 200;      // shorter than this isnt worth it, just idle
static_assert(NAP_GUARD_MS > NAP_MS, "a nap must end before LMIC's next timed job is due");

void loop()
{
  watchdogKick();
  os_runloop_once();  // let lmic do its thing

  // some part was turned off for 1 h -> reset and try it again
  if (bootTrace.culprits && sleepPending && !lmicTxBusy() && millis() > SENSOR_RETRY_MS)
  {
    bootTrace.culprits = 0;
    bootTrace.brownOutRun = 0;
    DBGLN("Trying the sensors again: software reset");
#if DEBUG
    Serial.flush();
#endif
    _PROTECTED_WRITE(RSTCTRL.SWRR, RSTCTRL_SWRE_bm);  // software reset
  }

  if (sleepPending && !lmicTxBusy())
  {
    // uplink is done and lmic is free -> sleep until our next slot
    sleepPending = false;
    while ((int32_t)(nextSlotAt - millis()) < 50)
      nextSlotAt += frameMs;  // slot alrd passed, skip to the next one
#if USE_ENS160
    if (gasStartPending)
    {
      // gas task: wake up 60 s before the slot to start the heater (or start now if the frame is short)
      gasStartPending = false;
      uint32_t warmAt = nextSlotAt - GAS_WARMUP_MS;
      if ((int32_t)(warmAt - millis()) > 0)
      {
        DBG("Sleeping ");
        DBG((int32_t)(warmAt - millis()));
        DBGLN(" ms until the gas warm-up");
        sleepUntil(warmAt);
      }
      if (pendingCommand == CMD_GAS)
        gasStart();
    }
#endif
    DBG("Sleeping ");
    DBG((int32_t)(nextSlotAt - millis()));
    DBGLN(" ms until the slot");
    sleepUntil(nextSlotAt);
    os_setCallback(&sendjob, do_send);  // slot time, send
  }
  else
  {
    // lmic is busy or waiting. nap (power-down) if its safe, otherwise idle.
    // safe = no tx/rx going on and lmic's next job is far enough away
    uint32_t napUntil = millis() + NAP_MS;
    if (LMIC.devaddr != 0 && (int32_t)(napUntil - nextSlotAt) > 0)
      napUntil = nextSlotAt;  // joined: dont nap past our slot
    if (!(LMIC.opmode & OP_TXRXPEND) && !os_queryTimeCriticalJobs(ms2osticks(NAP_GUARD_MS)) &&
        (int32_t)(napUntil - millis()) >= NAP_MIN_MS)
      sleepUntil(napUntil);
    else
      LowPower.idle();  // idle keeps millis running so the rx windows stay on time
  }
}
