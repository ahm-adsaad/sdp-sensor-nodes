// TDMA VARIANT of sensor_node_1.ino (that file is the ALOHA version and is unchanged).
// SX1276 / MCCI LMIC sensor node (SHT41 + ENS160 + storage voltage) - NODE 1 keys (DevEUI a382a57121e8bd08).
// Server sees this board as sensor 1. Do not run it while a Heltec with the same keys is on.
//
// TDMA: runs with task-service-tdma (port 5002) and Node-RED "Workflow 4 - TDMA", the same
// protocol as heltec_v3_tdma_energy.ino. Disable Workflow 3 while it runs.
//  - Time is cut into frames of numSlots slots; this node transmits only at the start of its own
//    slot, once per frame, so the nodes' uplinks and the gateway's answers stay a slot apart.
//  - The schedule arrives in every TDMA downlink (fPort 20, 6 bytes):
//      [0] command: 0x00 none (sync only), 0x01 humidity, 0x02 temperature, 0x03 gas,
//          0x10 battery refill (ignored here: the energy is measured, not simulated)
//      [1] this node's slot index  [2] slots per frame  [3] frame length, s
//      [4..5] slot correction, ms: after the uplink this downlink answers, wait one frame PLUS this
//    Until the first downlink arrives the node free-runs on DEFAULT_SLOTS / DEFAULT_SLOT_MS.
//  - A task is answered in the node's NEXT slot, not straight away as in the ALOHA version.
//  - Every uplink ends with the node's energy (uint16, 0..ENERGY_CAPACITY units), worked out from
//    the storage voltage (see energyUnits); a task the node cannot afford is skipped and a status
//    packet goes instead, so the server reassigns it.
//  - Power-down between slots as before, but timed to the millisecond: the sleep clock is measured
//    against the main clock at boot (see sleepUntil).
//  - Sensors are powered only for the task that needs them (see readTask): a temperature or
//    humidity task switches the SHT41's header on in its reply slot, reads and switches it off; a
//    gas task switches the ENS160's header on as soon as the task arrives, heats it until the reply
//    slot one frame (30 s) later, reads and switches it off. Status packets switch nothing on and
//    carry voltage and energy only. Nothing is powered at boot: each sensor is found on J3 or J4 by
//    the first task that needs it (see findSensor), and
//    headers are switched on with a pulsed ramp found on the bench (see railRamp).
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
//  - the ENS160 (about 29 mA while gas sensing) is only powered for gas tasks, never during a join;
//  - the OTAA DevNonce continues from EEPROM across resets, so ChirpStack never sees a
//    JoinRequest with a nonce it already used (LMIC alone restarts from a random value).
//
// Freeze fix (2026-10-20). After a downlink that carries MAC commands, LMIC queues its own uplink
// with the MAC answers (OP_POLL), and it only transmits while loop() keeps running. The old code
// checked OP_TXRXPEND alone, so it went back to sleep, or called LMIC_setTxData2, got
// LMIC_ERROR_TX_BUSY and slept a whole cycle; the board stopped sending for good (seen on node 1).
// lmicTxBusy() checks OP_TXRXPEND | OP_TXDATA | OP_POLL | OP_JOINING: do_send() waits and retries
// every 1 s while it is set, a failed LMIC_setTxData2 retries in 1 s instead of sleeping, and
// loop() only sleeps once it is clear.
// The OTAA keys are in secrets.h next to this file, which is kept out of git.
#include <Wire.h>
#include <EEPROM.h>
#include <lmic.h>
#include <hal/hal.h>
#include <RocketScream_LowPowerAVRZero.h>
#include <Adafruit_SHT4x.h>

#define DEBUG 1           // 0 for battery runs: no serial output and the UART pins are parked
#define USE_ENS160 1      // 0 = no ENS160 on the bus: gas bytes carry 0 ppb / 400 ppm / status 0xFF
#define VSTO_SENSE 1      // 0 = the storage divider on H5 pin 1 is not fitted, status packets send 0 mV
#define NODE_NUMBER 1     // sensor number on the server (num_to_eui); picks the default slot
#define TEST_IGNORE_ENERGY 1  // TEST ONLY (2026-10-28): never skip a task for lack of energy; set 0 again
                              // after the bench tests. The real energy is still reported.

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
bool ens160Found = false;    // answered its part id (findSensor)
bool gasWarming = false;     // powered and heating for a gas task, read in the next slot (gasStart)
uint32_t gasSince = 0;       // millis() when it started heating
#endif

void os_getArtEui(u1_t* buf) { memcpy_P(buf, APPEUI, 8); }
void os_getDevEui(u1_t* buf) { memcpy_P(buf, DEVEUI, 8); }
void os_getDevKey(u1_t* buf) { memcpy_P(buf, APPKEY, 16); }

// Board pins (PCB rev 2; the radio pins, PD6 and PD7 are the same on rev 1)
const uint8_t PIN_RAIL_A = PIN_PD6;  // U8 ENA: VCC_SENS_A on J3, I2C bus A (PA2/PA3)
const uint8_t PIN_RAIL_B = PIN_PC1;  // U8 ENB: VCC_SENS_B on J4, I2C bus B (PC2/PC3)
const uint8_t PIN_LED = PIN_PD7;     // never use LED_BUILTIN: MegaCoreX maps it to PA7 = radio NSS
const uint8_t PIN_VSTO = PIN_PD0;    // H5 pin 1 = AIN0: storage voltage through the R1/R2 divider

// Both sensor headers are used. The ATmega4809 has one TWI, which reaches J3 on its default pins
// (PA2/PA3) or J4 on the alternate ones (PC2/PC3, Wire.swap(1)). Nothing is powered at boot: the
// first task that needs a sensor looks for it on J3, then J4 (findSensor), so it does not matter
// which one is plugged where; selectBus() moves the TWI to a sensor's header before every access.
const uint8_t BUS_J3 = 0;  // Wire.swap() states
const uint8_t BUS_J4 = 1;
uint8_t currentBus = 0xFF;  // none: Wire not started
uint8_t shtBus = BUS_J3;
uint8_t ensBus = BUS_J3;
bool shtFound = false;
bool shtSearched = false;   // looked for once per boot; a missing sensor is not searched again
bool ensSearched = false;

// Pins this sketch does not drive: PMIC status PB2-PB4 (not read yet), header H5 (PD0-PD4, PC7)
// and the unconnected ones. Their digital input buffers are switched off so a floating level
// cannot draw current. PD0 stays on the list: the ADC does not use the digital buffer, and a
// buffer sitting at half the storage voltage would draw current.
const uint8_t UNUSED_PINS[] = {
  PIN_PB0, PIN_PB1, PIN_PB2, PIN_PB3, PIN_PB4, PIN_PB5,
  PIN_PC0, PIN_PC4, PIN_PC5, PIN_PC6, PIN_PC7,
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

// ---- TDMA schedule ----
// Defaults until the first downlink brings the real schedule. Keep them in step with
// TDMA_SLOTS / TDMA_SLOT_S in task-service-tdma/TaskGenerator.py. The frame replaces the ALOHA
// version's TX_INTERVAL: one uplink per frame, and a task waits up to a frame for its reply slot.
const uint8_t DEFAULT_SLOTS = 2;
const uint32_t DEFAULT_SLOT_MS = 15000;
// At least 10 s (1 % duty cycle for a ~70 ms frame), at most 1800 s (LMIC and micros() wrapping)
const uint32_t MIN_FRAME_MS = 10000;
const uint32_t MAX_FRAME_MS = 1800000;

uint8_t slotIndex = NODE_NUMBER - 1;
uint8_t numSlots = DEFAULT_SLOTS;
uint32_t frameMs = DEFAULT_SLOTS * DEFAULT_SLOT_MS;
uint32_t nextSlotAt = 0;          // millis() of this node's next slot start
uint32_t txStartedAt = 0;         // millis() when the current data uplink went on air
bool dataFrameInFlight = false;   // our uplink, not one LMIC queued for MAC answers
bool synced = false;
uint32_t slotsUsed = 0, resyncs = 0, tasksSkipped = 0;

// Length of one RTC PIT tick in microseconds, measured against the main clock in setup()
// (nominally 1 s, but the ULP oscillator is only good to +-10 %).
uint32_t usPerTick = 1000000;

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
  uint8_t brownOutRun;  // brown-out resets in a row, see brownOutBackOff()
  uint8_t culprits;     // CULPRIT_* bits: what browned the node out and stays off
  uint8_t gasOn;        // the ENS160 hot plate is heating (gas sensing)
  uint8_t fails[3];     // brown-outs in a row pinned on J3, J4, the gas heater (see CULPRIT_AFTER)
};
const uint32_t TRACE_MAGIC = 0x54524143;  // "TRAC"
const uint8_t PHASE_IDLE = 0;
const uint8_t PHASE_TX = 1;      // from EV_TXSTART until the radio is done transmitting
const uint8_t PHASE_RAIL_A = 2;  // switching on VCC_SENS_A (J3) and talking to what is on it
const uint8_t PHASE_RAIL_B = 3;  // switching on VCC_SENS_B (J4) and talking to what is on it
BootTrace bootTrace __attribute__((section(".noinit")));
uint8_t bootPrevPhase = PHASE_IDLE;  // the phase the last reset hit, before this boot overwrites it
bool bootPrevValid = false;

// Per-sensor fallback (2026-10-28): switching both rails on browned the node out even with the
// storage at 3.7 V, and the back-off below then turned ALL sensors off although the SHT41 on J3
// had worked alone. Now a brown-out is pinned on what was happening: switching J3 on, switching
// J4 on, or the ENS160 heating (29 mA, also during transmissions). Only that stays off, and only
// after CULPRIT_AFTER such brown-outs in a row: switching J4 on is marginal, a sensor-only bench
// test browned out twice and got through on the third try. A start that gets through clears the
// count; a power-on, a flash, or the hourly retry clears everything.
const uint8_t CULPRIT_RAIL_A = 0x01;
const uint8_t CULPRIT_RAIL_B = 0x02;
const uint8_t CULPRIT_GAS = 0x04;
const uint8_t CULPRIT_AFTER = 3;
const char* const CULPRIT_NAMES[3] = { "J3 (switching it on)", "J4 (switching it on)", "ENS160 gas sensing (its heater)" };

uint8_t resetFlags = 0;  // RSTCTRL.RSTFR at boot: 0x01 power-on, 0x02 brown-out, 0x08 watchdog

// Brown-out back-off. A storage that cannot carry the sensors put the node in a reset loop
// (2026-10-28): every boot switched the sensor rail on, browned out and started again at
// once, so the harvester never got to refill the storage. Now each brown-out reset in a row
// first sleeps (power-down, a few uA) for BROWNOUT_WAIT_S, doubling up to BROWNOUT_WAIT_MAX_S.
// The sensors are off between tasks anyway, so an unexplained brown-out (the radio, a low
// storage) only lengthens the wait; one pinned on a sensor's header or heater leaves that part
// off (CULPRIT_AFTER), retried after SENSOR_RETRY_MS by a software reset. GOOD_UPLINKS clean
// uplinks end the run.
const uint16_t BROWNOUT_WAIT_S = 30;
const uint16_t BROWNOUT_WAIT_MAX_S = 480;
const uint32_t SENSOR_RETRY_MS = 3600000UL;
const uint8_t GOOD_UPLINKS = 3;
uint8_t goodUplinks = 0;

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

// ---- Energy reported to the task-assignment algorithms ----
// The storage holds E = C V^2 / 2, but only what is above VSTO_EMPTY_MV is usable, so the node
// reports ENERGY_CAPACITY x (V^2 - Vempty^2) / (Vfull^2 - Vempty^2): 0 at VSTO_EMPTY_MV, full at
// VSTO_FULL_MV, no capacitance needed. ENERGY_CAPACITY and the task costs are the server's units
// (ENERGY_CAPACITY / TASK_COST in task-service-tdma/TaskGenerator.py): keep them the same.
const uint16_t VSTO_FULL_MV = 3600;   // the LiC is full at 3.60 V (STO_CFG LLLH)
const uint16_t VSTO_EMPTY_MV = 2800;  // AEM10330 STO_CFG LLLH: the LOAD output (the board) is cut below 2.80 V, back on above 3.10 V
const uint16_t ENERGY_CAPACITY = 200;
const uint16_t COST_HUMIDITY = 10;
const uint16_t COST_TEMPERATURE = 10;
const uint16_t COST_GAS = 30;
static_assert(VSTO_EMPTY_MV < VSTO_FULL_MV, "VSTO_EMPTY_MV must be below VSTO_FULL_MV");

const uint8_t DOWNLINK_PORT = 20;       // TDMA port; the ALOHA version uses 10
const uint8_t CMD_NONE = 0x00;          // sync only
const uint8_t CMD_HUMIDITY = 0x01;
const uint8_t CMD_TEMPERATURE = 0x02;
const uint8_t CMD_GAS = 0x03;
const uint8_t CMD_RESET_ENERGY = 0x10;  // simulated-battery refill for the Heltecs, ignored here
const uint8_t TDMA_DOWNLINK_LEN = 6;

// Uplink packet types (first payload byte, uplinks on fPort 1):
//   PKT_STATUS (0x00) - routine periodic full reading. NOT a reply to a command,
//                       so the server does not treat it as "task done".
//   0x01 / 0x02 / 0x03 - response to a humidity / temperature / gas command.
//                       Only these mark the sensor as free again on the server.
// Status packets switch no sensor on (sensors are powered for tasks only): their temperature and
// humidity are NOT_MEASURED, TVOC / eCO2 0 and the ENS160 status ENS_NOT_MEASURED.
// Status packet, 15 bytes, 16-bit values big-endian:
//   [0] 0x00, [1-2] TVOC ppb, [3-4] eCO2 ppm, [5-6] temperature x100 (C),
//   [7-8] humidity x100 (%RH), [9-10] storage voltage in mV (0 = not measured),
//   [11] AQI-UBA 1..5 (0 = none), [12] ENS160 status (see ENS_ABSENT),
//   [13] TX power cap in dBm, [14] reset flags of this boot (RSTCTRL.RSTFR).
// Bytes 0-10 are unchanged, so a decoder that stops at byte 10 keeps working.
// Gas reply, 7 bytes: [0] 0x03, [1-2] TVOC, [3-4] eCO2, [5] AQI-UBA, [6] ENS160 status.
// TDMA: every packet above gets the energy (uint16, see energyUnits) as its LAST two bytes:
// status 17 bytes, humidity / temperature reply 5, gas reply 9. Same rule as the Heltec TDMA
// node (status 5, replies 5 / 7), so the server reads the energy from the end of any uplink.
const uint8_t PKT_STATUS = 0x00;

// Sent in place of temperature / humidity when the SHT41 does not answer (decodes as 327.67).
const int16_t NO_READING = 0x7FFF;
// Sent in place of temperature / humidity when they were not measured: status packets (decodes as 327.66).
const int16_t NOT_MEASURED = 0x7FFE;

// ENS160 status byte in the packets: 0..3 is the sensor's own validity flag (0 normal,
// 1 warm-up, 2 initial start-up, 3 invalid output); the rest are the node's codes.
const uint8_t ENS_NOT_MEASURED = 0xFC;  // no gas reading asked for: status packets
const uint8_t ENS_NO_SAMPLE = 0xFD;  // sensing, but no fresh sample yet (first second after start)
const uint8_t ENS_NO_ANSWER = 0xFE;  // found before, no I2C answer now
const uint8_t ENS_ABSENT = 0xFF;     // not fitted, not found, or not started yet

struct Reading
{
  int16_t tempScaled;  // C x100
  int16_t humScaled;   // %RH x100
  uint16_t tvoc;       // ppb
  uint16_t eco2;       // ppm
  uint8_t aqi;         // AQI-UBA 1..5, 0 = none
  uint8_t ensStatus;
};
void readTask(uint8_t cmd, Reading &r);  // declared here so the IDE's generated prototype does not land above the struct

uint8_t pendingCommand = 0;
bool sleepPending = false;  // an uplink cycle has finished and nothing else is queued

// LMIC has a frame queued or on air: its own uplink carrying MAC answers (OP_POLL, queued after a
// downlink with MAC commands), a join, or our data. LMIC only sends a queued frame while loop() is
// awake, so sleeping or starting a new send in this state deadlocks: LMIC_setTxData2 keeps failing
// with LMIC_ERROR_TX_BUSY and the board sleeps again before LMIC can transmit (seen 2026-10-20).
static bool lmicTxBusy()
{
  return (LMIC.opmode & (OP_TXRXPEND | OP_TXDATA | OP_POLL | OP_JOINING)) != 0;
}

// Downlink loss tracking (same idea as the Heltec sketch): the network numbers
// every downlink, so a jump in the downlink counter means frames were missed.
int32_t lastDownlinkFCnt = -1;
uint32_t downlinksReceived = 0;
uint32_t downlinksMissed = 0;

// MegaCoreX's millis() counter (wiring.c). LMIC keeps time with micros(), which is built on it
// and stops in power-down, so sleepUntil() adds the slept time back.
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

// Measures one RTC PIT tick (1024 ULP cycles, nominally 1 s) against the main clock, which keeps
// millis() and LMIC's timing (+-2 %). Takes about 5 s; called once in setup().
uint32_t measurePitTick()
{
  const uint8_t TICKS = 4;
  uint16_t t = readPitTicks();
  while (readPitTicks() == t) { watchdogKick(); }  // start on a tick edge
  uint32_t start = micros();
  t = readPitTicks();
  while ((uint16_t)(readPitTicks() - t) < TICKS) { watchdogKick(); }
  return (micros() - start) / TICKS;
}

// Sleeps until millis() reaches `target`: power-down in whole PIT ticks (the RTC PIT, from the
// 1.024 kHz ULP oscillator, is the only timer left running there), then idle for the last part,
// where the 1 ms tick runs again, so the slot is hit to the millisecond. millis() stops in
// power-down, so the slept ticks are added back at the measured tick length; LMIC keeps time
// with micros(), which is built on it.
void sleepUntil(uint32_t target)
{
#if DEBUG
  Serial.flush();
#endif
  static uint32_t usCarry = 0;  // sub-millisecond part of the slept time, carried to the next sleep

  // wait for a tick edge (idle, under a second) so every powered-down tick is a whole one
  uint16_t t = readPitTicks();
  while (readPitTicks() == t && (int32_t)(target - millis()) > 0)
  {
    LowPower.idle();
    watchdogKick();
  }

  int32_t left = (int32_t)(target - millis());
  uint32_t ticks = left > 0 ? (uint32_t)left * 1000UL / usPerTick : 0;
  if (ticks > 0)
  {
    ticks--;  // keep up to one tick for the idle part: never wake past the target
    noInterrupts();
    pitTicks = 0;
    interrupts();
    while (readPitTicks() < ticks)
    {
      LowPower.powerDown();
      watchdogKick();  // the watchdog keeps counting in power-down
    }
    uint32_t us = ticks * usPerTick + usCarry;
    usCarry = us % 1000UL;
    noInterrupts();
    timer_millis += us / 1000UL;
    interrupts();
  }

  while ((int32_t)(target - millis()) > 0)
  {
    LowPower.idle();
    watchdogKick();
  }
}

// The storage voltage as energy units for the algorithms (see ENERGY_CAPACITY).
uint16_t energyUnits(uint16_t mv)
{
  if (mv == 0)
    return ENERGY_CAPACITY;  // VSTO_SENSE off: nothing measured, counted as full
  if (mv <= VSTO_EMPTY_MV)
    return 0;
  if (mv >= VSTO_FULL_MV)
    return ENERGY_CAPACITY;
  float empty2 = (float)VSTO_EMPTY_MV * VSTO_EMPTY_MV;
  float usable = (float)mv * mv - empty2;
  float full = (float)VSTO_FULL_MV * VSTO_FULL_MV - empty2;
  return (uint16_t)(ENERGY_CAPACITY * usable / full + 0.5);
}

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

// A TDMA downlink answers the uplink that went on air at `uplinkAt`: the next slot is one frame
// after it, plus the correction that pulls this node onto the server's slot grid.
void applySchedule(const uint8_t* d, uint32_t uplinkAt)
{
  slotIndex = d[1];
  numSlots = d[2];
  uint32_t frame = (uint32_t)d[3] * 1000UL;
  if (frame >= MIN_FRAME_MS && frame <= MAX_FRAME_MS)
    frameMs = frame;
  uint32_t correction = ((uint32_t)d[4] << 8) | d[5];
  nextSlotAt = uplinkAt + frameMs + correction;
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
  // the phase as the reset left it: by now the sensor start-up has overwritten bootTrace.phase
  bool duringTx = bootPrevValid && bootPrevPhase == PHASE_TX;
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

// Counts brown-out resets in a row and, after one, sleeps before anything draws current so the
// storage can recharge (see BROWNOUT_WAIT_S). Runs before learnFromBrownOut(), which rewrites
// the magic. Needs the RTC PIT running; millis() is not credited, LMIC has not started yet.
void brownOutBackOff()
{
  bool brownOut = (resetFlags & RSTCTRL_BORF_bm) && !(resetFlags & RSTCTRL_PORF_bm);
  bootPrevValid = bootTrace.magic == TRACE_MAGIC;
  bootPrevPhase = bootTrace.phase;

  // a power-on or a flash starts over: every sensor gets tried again
  if (!bootPrevValid || (resetFlags & (RSTCTRL_PORF_bm | RSTCTRL_UPDIRF_bm)))
  {
    bootTrace.culprits = 0;
    bootTrace.fails[0] = bootTrace.fails[1] = bootTrace.fails[2] = 0;
  }

  // pin the brown-out on what was going on, if anything sensor-related; that part stays off
  // once it has done it CULPRIT_AFTER times in a row
  uint8_t culprit = 0, idx = 0;
  if (bootPrevValid && brownOut)
  {
    if (bootPrevPhase == PHASE_RAIL_A)
      culprit = CULPRIT_RAIL_A, idx = 0;
    else if (bootPrevPhase == PHASE_RAIL_B)
      culprit = CULPRIT_RAIL_B, idx = 1;
    else if (bootTrace.gasOn)
      culprit = CULPRIT_GAS, idx = 2;
  }
  if (culprit)
  {
    if (bootTrace.fails[idx] < 255)
      bootTrace.fails[idx]++;
    DBG("Brown-out pinned on ");
    DBG(CULPRIT_NAMES[idx]);
    DBG(", ");
    DBG(bootTrace.fails[idx]);
    DBG(" of ");
    DBG(CULPRIT_AFTER);
    DBGLN(bootTrace.fails[idx] >= CULPRIT_AFTER ? ": leaving it off" : ": will try again");
    if (bootTrace.fails[idx] >= CULPRIT_AFTER)
      bootTrace.culprits |= culprit;
  }
  bootTrace.gasOn = 0;

  // an unexplained brown-out counts towards the all-sensors-off back-off; an explained one does
  // not, that sensor is simply left off
  if (!bootPrevValid || !brownOut)
    bootTrace.brownOutRun = 0;
  else if (!culprit && bootTrace.brownOutRun < 255)
    bootTrace.brownOutRun++;
  // Valid from here on: a boot that browns out before learnFromBrownOut() (at the sensor rail,
  // say) must still leave a trace the next boot can count (seen 2026-10-28: it never did).
  if (!bootPrevValid)
  {
    bootTrace.magic = TRACE_MAGIC;
    bootTrace.phase = PHASE_IDLE;
    bootTrace.gasOn = 0;
  }

  if (bootTrace.culprits)
  {
    DBG("Left off after brown-outs:");
    if (bootTrace.culprits & CULPRIT_RAIL_A) DBG(" J3 (switching it on)");
    if (bootTrace.culprits & CULPRIT_RAIL_B) DBG(" J4 (switching it on)");
    if (bootTrace.culprits & CULPRIT_GAS) DBG(" ENS160 gas sensing (its heater)");
    DBGLN(" - power-cycle to try again");
  }

  uint8_t run = culprit ? 1 : bootTrace.brownOutRun;  // an explained one still rests once
  if (run == 0)
    return;
  uint32_t wait = (uint32_t)BROWNOUT_WAIT_S << (run - 1 < 5 ? run - 1 : 5);
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
  noInterrupts();
  pitTicks = 0;
  interrupts();
  while (readPitTicks() < wait)
  {
    LowPower.powerDown();
    watchdogKick();
  }
}

// Moves the TWI to header J3 or J4. Wire.swap() only takes effect in Wire.begin().
void selectBus(uint8_t bus)
{
  if (bus == currentBus)
    return;
  Wire.end();
  Wire.swap(bus);
  Wire.begin();
  currentBus = bus;
}

// ---- Sensor power, per task ----
// Switch-on ramp. The MIC94069 ramps its output over about 800 us by itself and drains it while
// off, yet a plain switch-on of the ENS160 board browned the node out every time (36 of 36 bench
// trials, 2026-10-28, storage 3.2 V), on J4 or J3, in any order or gap. Pulsing the enable with
// on-times that grow from RAMP_FROM_US to RAMP_TO_US in RAMP_STEP_US, RAMP_OFF_US off in between
// (about 70 ms in all), charges the board a little at a time: step 5 us and off 20 us each passed
// 5 of 5 trials with the gas heater running, step 10 / off 50 passed 8 of 10, step 25 none; the
// two together (used here) passed 8 of 8 at 3.04 V storage, the lowest of the whole test.
// sensor node tdma/bench/sequence_test/ in the repo has the bench sketch and the full results. Used
// for both headers.
const uint16_t RAMP_FROM_US = 50;
const uint16_t RAMP_TO_US = 800;
const uint8_t RAMP_STEP_US = 5;
const uint8_t RAMP_OFF_US = 20;

// The enable goes in as its port's OUT register and bit (digitalWriteFast() needs a constant
// pin): VPORTD.OUT / PIN6_bm is PIN_RAIL_A (PD6, J3), VPORTC.OUT / PIN1_bm is PIN_RAIL_B (PC1, J4).
void railRamp(volatile uint8_t &out, uint8_t mask)
{
  for (uint16_t on = RAMP_FROM_US; on <= RAMP_TO_US; on += RAMP_STEP_US)
  {
    out |= mask;
    delayMicroseconds(on);
    out &= ~mask;
    delayMicroseconds(RAMP_OFF_US);
  }
  out |= mask;
}

// Powers the header a sensor sits on and points the TWI at it; false when that header was left off
// after brown-outs. bootTrace.phase stays on the header until headerOff(), so a brown-out while
// talking to its sensor is pinned on it too.
bool headerOn(uint8_t bus)
{
  bool j3 = bus == BUS_J3;
  if (bootTrace.culprits & (j3 ? CULPRIT_RAIL_A : CULPRIT_RAIL_B))
    return false;
  bootTrace.phase = j3 ? PHASE_RAIL_A : PHASE_RAIL_B;
  if (j3)
    railRamp(VPORTD.OUT, PIN6_bm);
  else
    railRamp(VPORTC.OUT, PIN1_bm);
  delay(5);  // SHT41 power-up is 1 ms max
  LowPower.enablePinISC(j3 ? PIN_PA2 : PIN_PC2);
  LowPower.enablePinISC(j3 ? PIN_PA3 : PIN_PC3);
  currentBus = 0xFF;
  selectBus(bus);
  return true;
}

// On rev 2 the bus pull-ups R9-R12 sit on the always-on 3V3, so a sensor whose header is off is
// back-fed through SDA/SCL (estimated 0.3-0.5 mA, not measured). The header came up and did its
// work, so its brown-out count starts over.
void headerOff(uint8_t bus)
{
  bool j3 = bus == BUS_J3;
  Wire.end();
  currentBus = 0xFF;
  LowPower.disablePinISC(j3 ? PIN_PA2 : PIN_PC2);  // also clears the internal pull-ups Wire.begin() set
  LowPower.disablePinISC(j3 ? PIN_PA3 : PIN_PC3);
  if (j3)
    digitalWriteFast(PIN_RAIL_A, LOW);
  else
    digitalWriteFast(PIN_RAIL_B, LOW);
  bootTrace.phase = PHASE_IDLE;
  bootTrace.fails[j3 ? 0 : 1] = 0;
}

// Looks for the SHT41 (sht) or the ENS160 the first time a task needs it, so nothing is powered
// outside a task: J3, then J4, one header at a time, each switched off again (the task powers the
// sensor's header itself). A header already on for a warming ENS160 is asked as it is: switching it
// again would cut the heater. The other sensor is noted too if it answers on the same header.
void findSensor(bool sht)
{
  if (sht)
    shtSearched = true;
  else
    ensSearched = true;
  for (uint8_t bus = BUS_J3; bus <= BUS_J4 && !(sht ? shtFound : ens160Found); bus++)
  {
#if USE_ENS160
    bool alreadyOn = gasWarming && bus == ensBus;
#else
    bool alreadyOn = false;
#endif
    if (alreadyOn)
      selectBus(bus);
    else if (!headerOn(bus))
      continue;
    watchdogKick();
#if USE_ENS160
    if (!ens160Found && ens160Probe())
    {
      ens160Found = true;
      ensBus = bus;
      DBG("ENS160 found at 0x");
      DBG(ens160Address(), HEX);
      DBGLN(bus == BUS_J3 ? " on J3" : " on J4");
    }
#endif
    if (!shtFound && sht4.begin())
    {
      shtFound = true;
      shtBus = bus;
      DBGLN(bus == BUS_J3 ? "SHT41 found on J3" : "SHT41 found on J4");
      sht4.setPrecision(SHT4X_HIGH_PRECISION);
      sht4.setHeater(SHT4X_NO_HEATER);
    }
    if (!alreadyOn)
      headerOff(bus);
  }
  if (sht && !shtFound)
    DBGLN("Could not find SHT41 on J3 or J4, check wiring!");
#if USE_ENS160
  if (!sht && !ens160Found)
    DBGLN("Could not find ENS160 on J3 or J4, check wiring!");
#endif
}

#if USE_ENS160
// A gas task arrived: power the ENS160 and start its heater now, so it has heated for a whole
// frame (30 s) by the reply slot. Its readings only count as valid after about 3 min (status 1,
// warm-up, until then); the 30 s value is sent with that status, as decided for the gas task.
void gasStart()
{
  if (gasWarming)
    return;
  if (!ens160Found && !ensSearched && !(bootTrace.culprits & CULPRIT_GAS))
    findSensor(false);
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
  ens160SetMode(ENS160_OPMODE_RESET);
  delay(100);
  watchdogKick();
  bootTrace.phase = PHASE_IDLE;  // the header came up: from here a brown-out is the heater's
  bootTrace.gasOn = 1;
  uint8_t mode = 0xFF;
  bool ok = ens160SetMode(ENS160_OPMODE_IDLE);
  delay(10);
  ok = ok && ens160SetMode(ENS160_OPMODE_STANDARD) && ens160GetMode(mode) && mode == ENS160_OPMODE_STANDARD;
  if (!ok)
  {
    DBGLN("ENS160 did not start gas sensing");
    bootTrace.gasOn = 0;
    headerOff(ensBus);
    return;
  }
  gasWarming = true;
  gasSince = millis();
  DBGLN("ENS160 on and heating for the gas task, read in the next slot");
}

void gasStop()
{
  if (!gasWarming)
    return;
  gasWarming = false;
  bootTrace.gasOn = 0;
  headerOff(ensBus);
}
#endif

// The reading a task asks for. cmd 0 (a status packet) switches nothing on: every sensor field is
// NOT_MEASURED / ENS_NOT_MEASURED. Temperature and humidity: the SHT41's header is switched on,
// read and off again. Gas: the ENS160 has been heating since the task arrived (gasStart); it is
// read and switched off. A sensor that did not answer sends NO_READING / ENS_ABSENT and friends.
void readTask(uint8_t cmd, Reading &r)
{
  r.tempScaled = NOT_MEASURED;
  r.humScaled = NOT_MEASURED;
  r.tvoc = 0;
  r.eco2 = 0;
  r.aqi = 0;
  r.ensStatus = ENS_NOT_MEASURED;

  if (cmd == CMD_HUMIDITY || cmd == CMD_TEMPERATURE)
  {
    r.tempScaled = NO_READING;
    r.humScaled = NO_READING;
    if (!shtFound && !shtSearched)
      findSensor(true);
    if (!shtFound)
      return;
#if USE_ENS160
    bool shared = gasWarming && ensBus == shtBus;  // already powered for a gas task
#else
    bool shared = false;
#endif
    if (!shared && !headerOn(shtBus))
    {
      DBGLN("SHT41 header left off after brown-outs");
      return;
    }
    selectBus(shtBus);
    sensors_event_t humEvent, tempEvent;
    if (sht4.getEvent(&humEvent, &tempEvent))
    {
      r.tempScaled = (int16_t)(tempEvent.temperature * 100);
      r.humScaled = (int16_t)(humEvent.relative_humidity * 100);
    }
    else
      DBGLN("SHT41 did not answer");
    if (!shared)
      headerOff(shtBus);
  }
  else if (cmd == CMD_GAS)
  {
    r.eco2 = 400;  // the values the server already got when no gas sensor is fitted
    r.ensStatus = ENS_ABSENT;
#if USE_ENS160
    if (!gasWarming)
      return;
    selectBus(ensBus);
    uint8_t status = 0;
    bool fresh = false;
    for (uint8_t i = 0; i < 15 && !fresh; i++)  // a sample comes every second
    {
      if (!ens160ReadStatus(status))
        break;
      fresh = status & ENS160_STATUS_NEWDAT;
      if (!fresh)
        delay(100);
    }
    if (!fresh)
      r.ensStatus = ENS_NO_SAMPLE;
    else if (ens160ReadData(r.aqi, r.tvoc, r.eco2))
    {
      r.ensStatus = (status & ENS160_STATUS_VALIDITY_gm) >> ENS160_STATUS_VALIDITY_gp;
      bootTrace.fails[2] = 0;  // the heater ran a whole frame without a brown-out
    }
    else
      r.ensStatus = ENS_NO_ANSWER;
    DBG("ENS160 heated ");
    DBG((millis() - gasSince) / 1000);
    DBGLN(" s");
    gasStop();
#endif
  }
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
  if (lmicTxBusy())
  {
    // let LMIC send what it has queued first; EV_TXCOMPLETE calls do_send again for a pending task
    DBGLN("LMIC busy, waiting");
    os_setTimedCallback(j, os_getTime() + sec2osticks(1), do_send);
    return;
  }

  uint16_t vstoMv = readVstoMv();  // first, while the radio is off
  uint16_t energy = energyUnits(vstoMv);

  // Not enough energy for the task: skip it and send a status packet; the server sees the low
  // energy and gives the task to another node.
  if (!TEST_IGNORE_ENERGY && pendingCommand != 0 && energy < taskCost(pendingCommand))
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
      gasStop();
#endif
    pendingCommand = 0;
  }

  Reading r;
  readTask(pendingCommand, r);

  uint8_t payload[17];
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
    // No command pending: a status packet, voltage and energy only (sensors are for tasks)
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

  // TDMA: the energy goes last in every packet
  payload[len++] = highByte(energy);
  payload[len++] = lowByte(energy);
  DBG("  energy ");
  DBG(energy);
  DBG(" / ");
  DBG(ENERGY_CAPACITY);
  DBG(" (storage ");
  DBG(vstoMv);
  DBGLN(" mV)");

  // Set before LMIC_setTxData2: LMIC starts the radio inside that call when the duty cycle allows,
  // so EV_TXSTART (which stamps txStartedAt) fires before it returns. Set after, the stamp was
  // skipped and every slot correction was applied to a stale time (seen 2026-10-28: uplinks 11-15 s
  // off where the server asked for a full frame).
  dataFrameInFlight = true;
  if (LMIC_setTxData2(1, payload, len, 0) != LMIC_ERROR_SUCCESS)
  {
    dataFrameInFlight = false;
    // keep pendingCommand and stay awake: retry shortly rather than sleeping a whole frame
    DBGLN("LMIC_setTxData2 failed, retrying in 1 s");
    os_setTimedCallback(&sendjob, os_getTime() + sec2osticks(1), do_send);
    return;
  }

  slotsUsed++;
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
      // Free-run on the defaults until the first downlink brings the schedule: start in this
      // node's own slot of the current frame.
      nextSlotAt = millis() + 100 + (uint32_t)slotIndex * DEFAULT_SLOT_MS;
      DBG("Unsynced, first uplink in ");
      DBG((int32_t)(nextSlotAt - millis()));
      DBGLN(" ms");
      sleepPending = true;
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
      else if (dataFrameInFlight)
      {
        // the moment the server's slot correction refers to
        txStartedAt = millis();
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

    {
      bool scheduled = false;
      if (LMIC.dataLen > 0)
      {
        uint8_t port = (LMIC.txrxFlags & TXRX_PORT) ? LMIC.frame[LMIC.dataBeg - 1] : 0;
        DBG("Downlink on port: ");
        DBGLN(port);

        // Only a TDMA downlink answering our own uplink carries a usable schedule. A frame LMIC
        // sent on its own (MAC answers) is not one the server's correction refers to; port 10
        // is the ALOHA workflow (Workflow 3 left on).
        if (port == DOWNLINK_PORT && LMIC.dataLen >= TDMA_DOWNLINK_LEN && dataFrameInFlight)
        {
          const uint8_t* d = &LMIC.frame[LMIC.dataBeg];
          uint8_t cmd = d[0];
          DBG("Downlink command received: 0x");
          DBGLN(cmd, HEX);
          if (cmd == CMD_HUMIDITY || cmd == CMD_TEMPERATURE || cmd == CMD_GAS)
            pendingCommand = cmd;  // answered in the next slot
#if USE_ENS160
          if (cmd == CMD_GAS)
            gasStart();  // heat from now until the reply slot
#endif
          else if (cmd == CMD_RESET_ENERGY)
            DBGLN("  battery refill ignored: this node reports its real energy");
          applySchedule(d, txStartedAt);
          scheduled = true;
        }
      }

      if (dataFrameInFlight && !scheduled)
        nextSlotAt += frameMs;  // no schedule this time: keep the frame going on the local clock
      if (dataFrameInFlight && goodUplinks < GOOD_UPLINKS && ++goodUplinks == GOOD_UPLINKS)
      {
        bootTrace.brownOutRun = 0;  // the storage carries the node: back-off over
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

      // TDMA: even a task waits for the node's next slot, so always sleep until then
      sleepPending = true;
      break;
    }

    case EV_TXCANCELED:
      bootTrace.phase = PHASE_IDLE;
      DBGLN("EV_TXCANCELED");
      if (dataFrameInFlight)
        nextSlotAt += frameMs;
      dataFrameInFlight = false;
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
  Serial.println("SHT41 + ENS160 LoRaWAN node - TDMA slots, energy from the storage voltage");
  Serial.print("Node number ");
  Serial.println(NODE_NUMBER);
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

  brownOutBackOff();  // first, before anything draws current

  usPerTick = measurePitTick();
  DBG("Sleep clock: one PIT tick = ");
  DBG(usPerTick);
  DBGLN(" us");

  // printed at boot too, so calibration does not have to wait for the join
  uint16_t bootMv = readVstoMv();
  DBG("Storage voltage ");
  DBG(bootMv);
  DBG(" mV, energy ");
  DBGLN(energyUnits(bootMv));

  DBGLN("Sensors off: each one is looked for and powered only when a task needs it");

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

  if (bootTrace.culprits && sleepPending && !lmicTxBusy() && millis() > SENSOR_RETRY_MS)
  {
    bootTrace.culprits = 0;  // try every sensor again
    bootTrace.brownOutRun = 0;
    // a part left off for an hour: restart to try it again (a software reset does
    // not count as a brown-out, so the first try comes without a wait)
    DBGLN("Trying the sensors again: software reset");
#if DEBUG
    Serial.flush();
#endif
    _PROTECTED_WRITE(RSTCTRL.SWRR, RSTCTRL_SWRE_bm);
  }

  if (sleepPending && !lmicTxBusy())
  {
    sleepPending = false;
    // a slot already passed (a late uplink, a long LMIC wait) is skipped, not sent late
    while ((int32_t)(nextSlotAt - millis()) < 50)
      nextSlotAt += frameMs;
    DBG("Sleeping ");
    DBG((int32_t)(nextSlotAt - millis()));
    DBGLN(" ms until the slot");
    sleepUntil(nextSlotAt);
    os_setCallback(&sendjob, do_send);
  }
  else
  {
    // Idle keeps the 1 ms millis tick running, so LMIC's receive-window timing still holds.
    LowPower.idle();
  }
}
