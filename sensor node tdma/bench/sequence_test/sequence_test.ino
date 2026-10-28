// Power-up sequence tester for the rev-2 PCB (no LoRa): which way of switching on the two sensor
// headers gets both the SHT41 and the ENS160 (with its gas heater) running without a brown-out?
// Each trial starts with both rails off (the MIC94069 drains them), rests REST_S so the storage
// recovers, switches the rails on in one of the SEQUENCES below, finds both sensors, starts gas
// sensing and reads both every 2 s for HOLD_S. A brown-out (or a hang caught by the watchdog)
// resets the chip; the score sheet lives in .noinit RAM, which a brown-out keeps, so the next
// boot books it against the sequence and stage that were running. Sequences take turns,
// TRIALS_EACH times each, then the ranking is printed. Flash the TDMA node sketch back afterwards.
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_SHT4x.h>
#include "ens160_min.h"

const uint8_t PIN_RAIL_A = PIN_PD6;  // J3
const uint8_t PIN_RAIL_B = PIN_PC1;  // J4
const uint8_t PIN_VSTO = PIN_PD0;
const uint8_t BUS_J3 = 0, BUS_J4 = 1;

const uint8_t TRIALS_EACH = 8;
const uint16_t REST_S = 8;
const uint16_t HOLD_S = 8;

// What a trial does, in order: rails (first, gap, second), then sensors, then the heater.
// Round 2: J3 first (it never browned out in round 1), then J4 pre-charged in pulses. Each pulse
// switches J4 on for part of the MIC94069 800 us soft-start ramp and off again for offUs, so the
// ENS160 board fills a little at a time; offUs is kept short so the switch output discharge does
// not empty it again. onUs grows from onFrom to onTo in onStep (or repeats reps times), then J4
// stays on. pulses = 0 is the plain switch-on, as a control.
struct Sequence { const char* name; uint8_t first; uint16_t gapMs; uint8_t second; uint16_t heaterDelayMs;
                  uint16_t onFrom, onTo, onStep, offUs, reps; };
const uint8_t A = 1, B = 2, AB = 3;  // rails: J3, J4, both at once
// Round 2 found the ramp 50-800 us / step 10 / off 50; round 3 showed step size matters most
// (25: 0/5, 10: 3/5, 5: 5/5) and short gaps help (off 20: 5/5, 50: 3/5, 100: 3/5).
// Round 4 confirms the combination of both.
const Sequence SEQUENCES[] = {
  { "ramp 50-800, step 5, off 20", A, 1000, B, 0,  50, 800,  5,  20, 1 },
  { "ramp 50-800, step 2, off 20", A, 1000, B, 0,  50, 800,  2,  20, 1 },
};
const uint8_t N_SEQ = sizeof(SEQUENCES) / sizeof(SEQUENCES[0]);

// stages, to see where a brown-out hits
const uint8_t ST_IDLE = 0, ST_FIRST = 1, ST_SECOND = 2, ST_PROBE = 3, ST_HEATER = 4, ST_HOLD = 5;
const char* const STAGE_NAMES[] = { "-", "1st rail", "2nd rail", "finding sensors", "heater start", "reading" };

struct Sheet
{
  uint32_t magic;
  uint8_t trial;       // next trial number
  uint8_t running;     // a trial was in progress
  uint8_t seq, stage;  // what it was doing
  uint16_t lastMv;
  uint8_t ok[N_SEQ];
  uint8_t bo[N_SEQ][6];   // brown-outs per stage
  uint8_t hang[N_SEQ];    // watchdog resets
  uint8_t missing[N_SEQ]; // got through, but a sensor did not answer / read
  uint16_t mvSum[N_SEQ];  // storage at the start of passing trials, /10 mV
};
const uint32_t SHEET_MAGIC = 0x53455154;  // "SEQT"
Sheet sheet __attribute__((section(".noinit")));

Adafruit_SHT4x sht4;
uint8_t currentBus = 0xFF;

void kick() { __asm__ __volatile__("wdr"); }

void selectBus(uint8_t bus)
{
  if (bus == currentBus) return;
  Wire.end();
  Wire.swap(bus);
  Wire.begin();
  currentBus = bus;
}

void radioSleep()
{
  pinMode(PIN_PF3, INPUT);
  pinMode(PIN_PA7, OUTPUT);
  digitalWrite(PIN_PA7, HIGH);
  SPI.begin();
  delay(10);
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_PA7, LOW);
  SPI.transfer(0x81);  // RegOpMode, write
  SPI.transfer(0x00);  // sleep
  digitalWrite(PIN_PA7, HIGH);
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
  return (uint16_t)(sum / 16.0 * 2.5 / 1023.0 * 2.0 * 1000.0 + 0.5);
}

void stage(uint8_t s)
{
  sheet.stage = s;
  Serial.flush();  // so the serial log is complete up to here if the next step browns out
}

void precharge(const Sequence &q)
{
  if (!q.reps) return;
  for (uint16_t on = q.onFrom; on <= q.onTo; on += q.onStep)
    for (uint16_t r = 0; r < q.reps; r++)
    {
      digitalWriteFast(PIN_RAIL_B, HIGH);
      delayMicroseconds(on);
      digitalWriteFast(PIN_RAIL_B, LOW);
      delayMicroseconds(q.offUs);
      if ((r & 31) == 0) kick();
    }
}

void rails(uint8_t which)
{
  if (which & A) digitalWrite(PIN_RAIL_A, HIGH);
  if (which & B) digitalWrite(PIN_RAIL_B, HIGH);
}

void wait(uint32_t ms)
{
  uint32_t end = millis() + ms;
  while ((int32_t)(end - millis()) > 0) { kick(); delay(10); }
}

void printSheet()
{
  Serial.println("------------------------------------------------------------------------");
  Serial.println(" sequence                        pass  brown-outs (where)          hang miss  avg mV");
  for (uint8_t s = 0; s < N_SEQ; s++)
  {
    char line[40];
    snprintf(line, sizeof(line), " %-30s", SEQUENCES[s].name);
    Serial.print(line);
    uint8_t total = 0;
    for (uint8_t st = 0; st < 6; st++) total += sheet.bo[s][st];
    Serial.print("  "); Serial.print(sheet.ok[s]);
    Serial.print("     "); Serial.print(total);
    if (total)
    {
      Serial.print(" (");
      bool first = true;
      for (uint8_t st = 1; st < 6; st++)
        if (sheet.bo[s][st])
        {
          if (!first) Serial.print(", ");
          Serial.print(STAGE_NAMES[st]); Serial.print(" x"); Serial.print(sheet.bo[s][st]);
          first = false;
        }
      Serial.print(")");
    }
    Serial.print("   hang "); Serial.print(sheet.hang[s]);
    Serial.print("  miss "); Serial.print(sheet.missing[s]);
    if (sheet.ok[s]) { Serial.print("  "); Serial.print((uint32_t)sheet.mvSum[s] * 10 / sheet.ok[s]); }
    Serial.println();
  }
  Serial.println("------------------------------------------------------------------------");
}

void setup()
{
  _PROTECTED_WRITE(WDT.CTRLA, WDT_PERIOD_8KCLK_gc);
  uint8_t flags = RSTCTRL.RSTFR;
  RSTCTRL.RSTFR = flags;
  pinMode(PIN_RAIL_A, OUTPUT);
  pinMode(PIN_RAIL_B, OUTPUT);
  digitalWrite(PIN_RAIL_A, LOW);
  digitalWrite(PIN_RAIL_B, LOW);
  Serial.begin(115200);
  delay(50);
  radioSleep();

  bool fresh = sheet.magic != SHEET_MAGIC || (flags & (RSTCTRL_PORF_bm | RSTCTRL_UPDIRF_bm));
  if (fresh)
  {
    memset(&sheet, 0, sizeof(sheet));
    sheet.magic = SHEET_MAGIC;
    Serial.println();
    Serial.println("=== Power-up sequence test, round 4: confirming the best J4 ramp ===");
    Serial.print(N_SEQ); Serial.print(" sequences x "); Serial.print(TRIALS_EACH);
    Serial.print(" trials, "); Serial.print(REST_S); Serial.print(" s rest + "); Serial.print(HOLD_S);
    Serial.println(" s reading each");
  }
  else if (sheet.running)
  {
    uint8_t s = sheet.seq, st = sheet.stage;
    bool bo = (flags & RSTCTRL_BORF_bm) != 0;
    if (bo && sheet.bo[s][st] < 255) sheet.bo[s][st]++;
    else if (!bo && sheet.hang[s] < 255) sheet.hang[s]++;
    Serial.println();
    Serial.print("!! Trial "); Serial.print(sheet.trial); Serial.print(" ("); Serial.print(SEQUENCES[s].name);
    Serial.print("): "); Serial.print(bo ? "BROWN-OUT" : "watchdog reset (hang)");
    Serial.print(" at "); Serial.print(STAGE_NAMES[st]);
    Serial.print(", storage was "); Serial.print(sheet.lastMv); Serial.println(" mV");
    sheet.running = 0;
    sheet.trial++;
    printSheet();
  }
}

void loop()
{
  if (sheet.trial >= N_SEQ * TRIALS_EACH)
  {
    static bool shown = false;
    if (!shown)
    {
      Serial.println("=== DONE: final results ===");
      printSheet();
      shown = true;
    }
    kick();
    delay(100);
    return;
  }

  uint8_t s = sheet.trial % N_SEQ;
  const Sequence &q = SEQUENCES[s];

  // both rails off (drained by the switch), rest so the storage recovers
  digitalWrite(PIN_RAIL_A, LOW);
  digitalWrite(PIN_RAIL_B, LOW);
  Wire.end();
  currentBus = 0xFF;
  wait((uint32_t)REST_S * 1000);

  uint16_t mv = readVstoMv();
  Serial.println();
  Serial.print("Trial "); Serial.print(sheet.trial + 1); Serial.print("/"); Serial.print(N_SEQ * TRIALS_EACH);
  Serial.print(": "); Serial.print(q.name); Serial.print(", storage "); Serial.print(mv); Serial.println(" mV");

  sheet.seq = s;
  sheet.lastMv = mv;
  sheet.running = 1;

  stage(ST_FIRST);
  rails(q.first);
  wait(q.gapMs ? q.gapMs : 5);
  if (q.second)
  {
    stage(ST_SECOND);
    precharge(q);
    rails(q.second);
    wait(5);
  }

  stage(ST_PROBE);
  bool shtOk = false, ensOk = false;
  uint8_t shtBus = BUS_J3, ensBus = BUS_J4;
  ens160Addr = 0;
  for (uint8_t bus = BUS_J3; bus <= BUS_J4; bus++)
  {
    selectBus(bus);
    kick();
    if (!ensOk && ens160Probe()) { ensOk = true; ensBus = bus; }
    if (!shtOk && sht4.begin()) { shtOk = true; shtBus = bus; }
  }
  Serial.print("  found: SHT41 "); Serial.print(shtOk ? (shtBus == BUS_J3 ? "J3" : "J4") : "NO");
  Serial.print(", ENS160 "); Serial.println(ensOk ? (ensBus == BUS_J3 ? "J3" : "J4") : "NO");

  bool sensing = false;
  if (ensOk)
  {
    wait(q.heaterDelayMs);
    stage(ST_HEATER);
    selectBus(ensBus);
    ens160SetMode(ENS160_OPMODE_RESET);
    wait(100);
    ens160SetMode(ENS160_OPMODE_IDLE);
    wait(10);
    uint8_t mode = 0xFF;
    sensing = ens160SetMode(ENS160_OPMODE_STANDARD) && ens160GetMode(mode) && mode == ENS160_OPMODE_STANDARD;
  }

  stage(ST_HOLD);
  bool readsOk = true;
  uint8_t gasSamples = 0;
  uint32_t end = millis() + (uint32_t)HOLD_S * 1000;
  while ((int32_t)(end - millis()) > 0)
  {
    wait(2000);
    float t = NAN, h = NAN;
    if (shtOk)
    {
      selectBus(shtBus);
      sensors_event_t hum, temp;
      if (sht4.getEvent(&hum, &temp)) { t = temp.temperature; h = hum.relative_humidity; }
    }
    uint16_t tvoc = 0, eco2 = 0;
    uint8_t aqi = 0, status = 0;
    bool gas = false;
    if (sensing)
    {
      selectBus(ensBus);
      if (ens160ReadStatus(status) && (status & ENS160_STATUS_NEWDAT) && ens160ReadData(aqi, tvoc, eco2)) { gas = true; gasSamples++; }
    }
    if (isnan(t)) readsOk = false;
    Serial.print("  "); Serial.print(readVstoMv()); Serial.print(" mV | ");
    if (isnan(t)) Serial.print("SHT41 no reading"); else { Serial.print(t, 2); Serial.print(" C "); Serial.print(h, 1); Serial.print(" %"); }
    Serial.print(" | ");
    if (gas) { Serial.print("TVOC "); Serial.print(tvoc); Serial.print(" eCO2 "); Serial.print(eco2); Serial.print(" AQI "); Serial.print(aqi); }
    else Serial.print(sensing ? "ENS160 no sample" : "no gas sensing");
    Serial.println();
  }
  if (!sensing || gasSamples == 0) readsOk = false;

  stage(ST_IDLE);
  sheet.running = 0;
  if (shtOk && ensOk && readsOk)
  {
    sheet.ok[s]++;
    sheet.mvSum[s] += mv / 10;
    Serial.println("  PASS: both sensors read, no brown-out");
  }
  else
  {
    sheet.missing[s]++;
    Serial.println("  no brown-out, but a sensor did not answer or read");
  }
  sheet.trial++;
  printSheet();
}
