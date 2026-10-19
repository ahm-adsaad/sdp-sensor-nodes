// SX1276 / MCCI LMIC sensor node (SHT41, ENS160 optional) - NODE 1 keys (DevEUI a382a57121e8bd08).
// Server sees this board as sensor 1. Do not run it while a Heltec with the same keys is on.
// Network behaviour matches heltec_v3_node.ino: ADR off + SF7 after join, downlink
// loss counter, packet types 0x00 status / 0x01-0x03 command responses.
//
// Build: Arduino IDE, MegaCoreX > ATmega4809, Pinout "48 pin standard", Clock "Internal 8 MHz",
// Programmer "JTAG2UPDI", flash with Sketch > Upload Using Programmer.
// Libraries: MCCI LoRaWAN LMIC library 6.0.1, Adafruit SHT4x Library 1.0.5,
// Rocket Scream LowPowerAVRZero 1.0.0 (plus ENS160 - Adafruit Fork 3.0.1 if USE_ENS160 is 1).
// MCCI_LoRaWAN_LMIC_library/project_config/lmic_project_config.h must contain exactly:
//   #define CFG_eu868 1
//   #define CFG_sx1276_radio 1
//   #define LMIC_ENABLE_arbitrary_clock_error 1
//   #define DISABLE_PING
//   #define DISABLE_BEACONS
// Compile-tested 2026-10-19 with MegaCoreX 1.2.0 and the versions above. First run on a rev-2
// board from storage: brown-out reset on every join at LMIC's 16 dBm, hence TX_POWER_DBM.
// The OTAA keys are in secrets.h next to this file, which is kept out of git.
#include <Wire.h>
#include <lmic.h>
#include <hal/hal.h>
#include <RocketScream_LowPowerAVRZero.h>
#include <Adafruit_SHT4x.h>

#define DEBUG 1           // 0 for battery runs: no serial output and the UART pins are parked
#define USE_ENS160 0      // 1 = ENS160 on the SHT41's bus, left in STANDARD mode (~29 mA, always on)
#define RAIL_ALWAYS_ON 0  // 1 = keep VCC_SENS_A on between readings (see sensorRailOff)

#define SWITCH_RAIL (!RAIL_ALWAYS_ON && !USE_ENS160)

#if USE_ENS160
#include <ScioSense_ENS160.h>
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

#if USE_ENS160
ScioSense_ENS160 ens160(0x52);
#endif
Adafruit_SHT4x sht4 = Adafruit_SHT4x();

void os_getArtEui(u1_t* buf) { memcpy_P(buf, APPEUI, 8); }
void os_getDevEui(u1_t* buf) { memcpy_P(buf, DEVEUI, 8); }
void os_getDevKey(u1_t* buf) { memcpy_P(buf, APPKEY, 16); }

// Board pins (PCB rev 2; the radio pins, PD6 and PD7 are the same on rev 1)
const uint8_t PIN_RAIL_A = PIN_PD6;  // U8 ENA: VCC_SENS_A on J3, I2C bus A (PA2/PA3)
const uint8_t PIN_RAIL_B = PIN_PC1;  // U8 ENB: VCC_SENS_B on J4, I2C bus B - unused, held off
const uint8_t PIN_LED = PIN_PD7;     // never use LED_BUILTIN: MegaCoreX maps it to PA7 = radio NSS

// Pins this sketch does not drive: PMIC status PB2-PB4 (not read yet), I2C bus B on PC2/PC3,
// header H5 (PD0-PD4, PC7) and the unconnected ones. Their digital input buffers are switched
// off so a floating level cannot draw current.
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
// AEM10330's LOAD output, which gives about 60 mA with the storage at 2.8-3.0 V (DS v1.5.0
// Table 6, Fig. 7). LMIC sends joins at 16 dBm on PA_BOOST, and the SX1276 draws 87 mA at 17 dBm,
// so the rail sagged and the chip brown-out reset on every JoinRequest (reset flags 0x02).
// 10 dBm is a starting point, not a measured limit: check the TX current with the PPK2 before
// raising it. LMIC accepts 2..17 on PA_BOOST.
const int8_t TX_POWER_DBM = 10;
static_assert(TX_POWER_DBM >= 2 && TX_POWER_DBM <= 17, "TX_POWER_DBM must be 2..17 dBm");

const uint8_t DOWNLINK_PORT = 10;
const uint8_t CMD_HUMIDITY = 0x01;
const uint8_t CMD_TEMPERATURE = 0x02;
const uint8_t CMD_GAS = 0x03;

// Uplink packet types (first payload byte, uplinks on fPort 1):
//   PKT_STATUS (0x00) - routine periodic full reading. NOT a reply to a command,
//                       so the server does not treat it as "task done".
//   0x01 / 0x02 / 0x03 - response to a humidity / temperature / gas command.
//                       Only these mark the sensor as free again on the server.
const uint8_t PKT_STATUS = 0x00;

// Sent in place of temperature / humidity when the SHT41 does not answer (decodes as 327.67).
const int16_t NO_READING = 0x7FFF;

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

// Fresh SHT41 reading (plus the ENS160's latest values if fitted). Returns false when the SHT41
// did not answer; temperature and humidity are then NO_READING.
bool readSensors(int16_t &tempScaled, int16_t &humScaled, uint16_t &tvoc, uint16_t &eco2)
{
#if SWITCH_RAIL
  sensorRailOn();
#endif

  sensors_event_t humEvent, tempEvent;
  bool ok = sht4.getEvent(&humEvent, &tempEvent);
  tempScaled = ok ? (int16_t)(tempEvent.temperature * 100) : NO_READING;
  humScaled = ok ? (int16_t)(humEvent.relative_humidity * 100) : NO_READING;

  // the values the server already got when no gas sensor is fitted
  tvoc = 0;
  eco2 = 400;
#if USE_ENS160
  if (ens160.available())
  {
    ens160.measure(false);  // STANDARD mode refreshes every second, so don't block for new data
    tvoc = ens160.getTVOC();
    eco2 = ens160.geteCO2();
  }
#endif

#if SWITCH_RAIL
  sensorRailOff();
#endif
  return ok;
}

void do_send(osjob_t* j)
{
  if (LMIC.opmode & OP_TXRXPEND)
  {
    DBGLN("OP_TXRXPEND, not sending");
    os_setTimedCallback(j, os_getTime() + ms2osticks(200), do_send);
    return;
  }

  int16_t tempScaled, humScaled;
  uint16_t tvoc, eco2;
  if (!readSensors(tempScaled, humScaled, tvoc, eco2))
    DBGLN("SHT41 did not answer, sending 0x7FFF for temperature and humidity");

  uint8_t payload[9];
  uint8_t len = 0;

  if (pendingCommand == CMD_HUMIDITY)
  {
    payload[0] = CMD_HUMIDITY;
    payload[1] = highByte(humScaled);
    payload[2] = lowByte(humScaled);
    len = 3;

    DBG("Sending humidity only: ");
    DBG(humScaled / 100.0);
    DBGLN(" %");
  }
  else if (pendingCommand == CMD_TEMPERATURE)
  {
    payload[0] = CMD_TEMPERATURE;
    payload[1] = highByte(tempScaled);
    payload[2] = lowByte(tempScaled);
    len = 3;

    DBG("Sending temperature only: ");
    DBG(tempScaled / 100.0);
    DBGLN(" C");
  }
  else if (pendingCommand == CMD_GAS)
  {
    payload[0] = CMD_GAS;
    payload[1] = highByte(tvoc);
    payload[2] = lowByte(tvoc);
    payload[3] = highByte(eco2);
    payload[4] = lowByte(eco2);
    len = 5;

    DBG("Sending gas/CO2 only: TVOC ");
    DBG(tvoc);
    DBG(" ppb, eCO2 ");
    DBG(eco2);
    DBGLN(" ppm");
  }
  else
  {
    // No command pending: send a status packet (full reading)
    payload[0] = PKT_STATUS;
    payload[1] = highByte(tvoc);
    payload[2] = lowByte(tvoc);
    payload[3] = highByte(eco2);
    payload[4] = lowByte(eco2);
    payload[5] = highByte(tempScaled);
    payload[6] = lowByte(tempScaled);
    payload[7] = highByte(humScaled);
    payload[8] = lowByte(humScaled);
    len = 9;

    DBG("Sending status packet: ");
    DBG(tempScaled / 100.0);
    DBG(" C, ");
    DBG(humScaled / 100.0);
    DBGLN(" %");
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
      DBGLN("EV_JOIN_TXCOMPLETE (no JoinAccept yet)");
      break;

    case EV_JOINED:
      DBGLN("EV_JOINED");
      LMIC_setLinkCheckMode(0);
      // ADR off + fixed SF7 (DR5): no ADR downlinks from ChirpStack, short uplinks.
      // Uplink channels are limited to 868.1/868.3/868.5 by ChirpStack (no CFList).
      LMIC_setAdrMode(0);
      LMIC_setDrTxpow(DR_SF7, TX_POWER_DBM);
      do_send(&sendjob);
      break;

    case EV_TXSTART:
      // LMIC has just picked this frame's power (16 dBm for a join) and starts the radio right
      // after this event returns, so this is the last place to cap it
      if (LMIC.radio.txpow > TX_POWER_DBM)
        LMIC.radio.txpow = TX_POWER_DBM;
      break;

    case EV_JOIN_FAILED:
      // LMIC keeps retrying on its own
      DBGLN("EV_JOIN_FAILED");
      break;

    case EV_TXCOMPLETE:
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

  uint8_t resetFlags = RSTCTRL.RSTFR;
  RSTCTRL.RSTFR = resetFlags;  // flags clear by writing 1

  ADC0.CTRLA &= ~ADC_ENABLE_bm;  // the core enables the ADC; nothing here uses it

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
  Serial.println("SHT41 LoRaWAN node - power-down between uplinks, downlink task support");
  Serial.print("Reset flags 0x");  // 0x08 = watchdog reset
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

  sensorRailOn();

#if USE_ENS160
  if (!ens160.begin())
    DBGLN("Could not find ENS160, check wiring!");
  else
  {
    DBGLN("ENS160 found!");
    ens160.setMode(ENS160_OPMODE_STD);
  }
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
