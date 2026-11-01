# Energy audit: TDMA sensor-node firmware

**Audited:**
- the sketch `sensor node tdma/sensor_node_1_tdma/sensor_node_1_tdma.ino`, 1329 lines (the firmware at HEAD is the same as f99731d)
- `ens160_min.h`, the README, and the bench `RESULTS.md`
- the libraries: MCCI LMIC 6.0.1, RocketScream LowPowerAVRZero 1.0.0, the MegaCoreX 1.2.0 core with Wire and SPI, and Adafruit SHT4x 1.0.5
- the datasheets: ATmega4809 DS40002173C, AEM10330 DS v1.5.0 and Eaton HS1040

The audit was read-only, dated 2026-11-01. **Nothing was measured, so every number here is an estimate.**

**Labels:** every number carries one of these labels.

| Label | Meaning |
|---|---|
| [DS] | From a datasheet on disk; the table is cited |
| [DSm] | A figure from memory, as given in the brief. The SX1276, ENS160 and SHT41 datasheets are not on disk |
| [C] | Follows from the sketch or library code; file:line is cited |
| [A] | An assumption. All of them are listed in section 1.4 for the user to confirm |

The only measured input used is the bench ramp data in `RESULTS.md`.

Line numbers are for `sensor_node_1_tdma.ino` unless a file is named.

---

## 0. Summary

### 0.1 Reference scenario [A]

The reference scenario assumes the following:
- The node is joined.
- Every uplink is answered in RX1 (case A).
- DEBUG is 1.
- The server sends 24 gas tasks and 48 T/RH tasks a day.
- Sensors are plugged into both headers.
- The I2C back-feed is 0.4 mA.
- The rail is at 3.3 V and the PMIC efficiency η is 0.85.

| Rank | Sink | Class | J/day at the 3.3 V rail | Share |
|---|---|---|---|---|
| 1 | Current back-fed through the I2C pull-ups R9-R12 into switched-off headers | HARDWARE (the firmware comment at L696-697 already suspects it) | 114 (range 86-314) | **46 %** |
| 2 | ENS160 heater, about 29 s per gas task | DESIGN | 67.3 | **27 %** |
| 3 | LoRa TX, SF7 at 10 dBm on PA_BOOST, once per 30 s | DESIGN (cadence) | 27.2 | **11 %** |
| 4 | `sleepUntil()` idle before every slot (1 s PIT: 0-1 s edge wait plus a 1-2 s tail) | BUG-class (unintended waste) | 16.4 | **6.7 %** |
| 5 | CPU idle from TX to the end of RX1 (Class A wait, 1.11 s) | DESIGN, partly avoidable | 10.2 | **4.2 %** |
| 6 | RX1 receive | DESIGN | 8.0 | 3.3 % |
| 7-10 | DEBUG UART 1.0, active compute 0.94, power-down floor 0.56, T/RH reads 0.05 | mixed | 2.6 | 1 % |
| | **Total at the rail** | | **≈ 246 J/day** | |
| | **Drawn from the store** (rail ÷ 0.85, plus 3.2 J/day for LiC leakage, the VSTO divider and the PMIC Iq) | | **≈ 292 J/day** | |
| | **Days on the 384 J store with no harvest** | | **≈ 1.3** | |

**Firmware alone** (status frames only, no tasks, no back-feed) is about 64 J/day at the rail. That is about 79 J/day from the store, or about 4.9 days on the 384 J store.

**The biggest unknown is which receive window the TDMA downlink arrives in.** It is not in the repo.
- **RX2:** ChirpStack's default RX2 is DR0/SF12. A downlink there costs +58 mJ per frame, which is **+167 J/day**.
- **No downlink:** an unanswered uplink opens a 0.3 s SF12 RX2 window, which costs +41 J/day.

Measure this first (check V1 in section 5).

### 0.2 Fixes, ranked by saving with zero functional loss

| Fix | What | Saving | Risk |
|---|---|---|---|
| F1 (HW) | Take R9-R12 off the always-on 3V3. The firmware must then input-disable PA2/PA3/PC2/PC3 at boot | 86-314 J/day | Low |
| F2 | PIT at 16 Hz instead of 1 Hz | ≈ 15 J/day | Low-medium: the tick counter range and the back-off conversion must be handled |
| F3 | Power down during long LMIC waits (unjoined, MAC-answer duty waits) | 287 → ≈ 14 J/day while the network is unreachable; ≈ 13 mJ per boot | Medium |
| F4 | Put the radio to sleep at the top of `setup()` | 0.16-2.5 J per brown-out rest; 24 mJ per boot | Low |
| F5 | Check gas-task energy when the task arrives, before starting the heater | 2.8 J per gas task that cannot be afforded (only with TEST_IGNORE_ENERGY 0) | Low |
| F6 (optional) | Standby instead of idle in the Class A gaps | ≈ 5.5 J/day | Medium-high: BOD is off in standby; the current is not measured |
| F7 | DEBUG 0 for deployment | ≈ 1 J/day | None |
| F8 | Idle inside `measurePitTick()` | ≈ 30 mJ per boot | None |
| F9 | Idle instead of `delay(100)` in the ENS160 poll | ≈ 3.7 mJ per gas task | None |
| F10 | Stop the unused TCA0/TCB PWM timers | ≈ 0.5 J/day | Check the millis timer's clock source first |

Projected results:
- **Reference scenario after F1 + F2 + F7:** ≈ 116 J/day at the rail, ≈ 139 J/day from the store, ≈ 2.8 days.
- **Status-only after F2 + F7:** ≈ 48 J/day at the rail, ≈ 60 J/day from the store, ≈ 6.4 days.

What remains after these fixes is the gas heater (2.8 J per task) and the 30 s cadence. Both are design decisions for the user (F11, F12, F13 in section 5.3).

---

## 1. Inputs

### 1.1 Currents

The rail is taken as 3.3 V [A]. The sketch says the AEM10330 LOAD output wanders between 3.15 and 3.34 V.

| Symbol | Value | Source |
|---|---|---|
| I_act (CPU active) | 2.9 mA | [DS] Table 32-5. Active at 8 MHz (OSC20M 16 MHz ÷ 2) is 2.6 mA at 3 V and 4.3 mA at 5 V, which interpolates to 2.86 mA at 3.3 V. Add 19 µA for the BOD in continuous mode (Table 32-8). The fuse BODCFG = 0x54 means 2.6 V, ACTIVE continuous, SLEEP disabled. |
| I_idle,s (idle inside `sleepUntil`) | 0.86 mA | [DS] Table 32-5 idle is 0.7 mA at 3 V and 1.3 mA at 5 V, so 0.79 mA at 3.3 V. Add BOD 19 µA and TCA0/TCB about 10 µA (Table 32-8). Add the 1 kHz millis ISR at about 1.5 % active duty [A]. |
| I_idle,loop (idle in `loop()`) | 0.96 mA | As above, plus one `loop()` pass (`os_runloop_once`, DIO polling, `lmicTxBusy`) after every 1 ms wake. That is about 500 cycles ≈ 62 µs per ms active [A]. |
| I_pd (power-down floor) | 2.2 µA | [DS] Table 32-6: power-down 0.1 µA typ. Table 32-8: RTC 1.2 µA and WDT 0.7 µA. SX1276 sleep 0.2 µA [DSm]. BOD is disabled in sleep by the fuse. |
| I_tx (radio TX) | 40 mA | [A]. PA_BOOST at +10 dBm is not on disk. The brief's "29 mA at +13 dBm" is the RFO-pin figure [DSm]. PA_BOOST draws 87 mA at +17 dBm (sketch comment L179) and 120 mA at +20 dBm [DSm]. **Measure this (V4).** |
| I_rx (radio RX) | 11.5 mA | [DSm] SX1276 RX with LNA boost on. LMIC writes LNA_RX_GAIN 0x23. |
| I_stby (radio standby) | 1.6 mA | [DSm] |
| ENS160 | 29 mA STANDARD (heater), 3 mA IDLE, 10 µA DEEP SLEEP | [DSm] |
| SHT41 breakout | ≈ 1 mA while powered (LED + LDO); the SHT41 itself draws 0.4-0.5 mA for about 8 ms while measuring | [DSm] |
| ADC | 0.33 mA | [DS] Table 32-8 |
| η (PMIC efficiency) | 0.85 | [A]. The AEM10330 DS v1.5.0 Fig. 5/6 efficiency curves could not be read numerically. |
| Store-side leaks | LiC leakage ≤ 9 µA; VSTO divider 3.2 V ÷ 2 MΩ = 1.6 µA; PMIC Iq 0.875 µA | LiC: [DS] HS1040, maximum after 72 h. Divider: [C]. PMIC: [DS] AEM10330 Table 6. |

### 1.2 Airtimes [C]

All at BW125, CR 4/5, an 8-symbol preamble and an explicit header. CRC is on for uplinks and off for downlinks.

The formula is T = (12.25 + 8 + ceil((8·PL − 4·SF + 28 + 16·CRC) / (4·(SF − 2·DE))) · 5) · 2^SF / 125 kHz.

| Frame | PHY bytes | SF7 | SF12 |
|---|---|---|---|
| Status uplink (17 B payload, FPort 1) | 30 | 71.9 ms | 1646.6 ms |
| T/RH reply (5 B) | 18 | 51.5 ms | |
| Gas reply (9 B) | 22 | 56.6 ms | |
| TDMA downlink (6 B, FPort 20) | 19 | 51.5 ms | 1318.9 ms |
| Empty MAC/ACK uplink | 12 | 41.2 ms | |
| JoinRequest | 23 | 61.7 ms | 1482.8 ms (SF8 113.2, SF9 205.8, SF10 370.7, SF11 823.3) |
| JoinAccept | 17 | 46.3 ms | |

### 1.3 Receive windows [C, LMIC 6.0.1]

**Timing and data rate.**
- RX1 opens at TX end + rxDelay. rxDelay comes from the JoinAccept and is forced to at least 1 s (lmic.c:1634-1635).
- RX2 opens one second later, at `LMIC.dn2Dr` from the JoinAccept DLSettings (lmic.c:1632).
- LMIC's default for RX2 is DR0/SF12 at 869.525 MHz (lorabase.h:141-142).
- ChirpStack's RX2 DR and RX1 delay are not in the repo (searched); treat them as unknown.

**Window widening.** `LMIC_setClockError(MAX_CLOCK_ERROR * 2 / 100);` (L1278) widens every window for ±2 % clock error. With LMIC's drift maths (MINRX_SYMS 6, RX_EXTRA_MARGIN 2 ms):

| Window | Opens early by | Timeout |
|---|---|---|
| RX1 at SF7 | 21.98 ms | 47 symbols = 48.1 ms |
| RX2 at SF12 | 41.97 ms | 9 symbols = 294.9 ms |
| Join RX1 at 5 s, SF7 | | 204 symbols (209 ms) |
| Join RX1 at 5 s, SF12 | | 13 symbols (426 ms) |
| Join RX2 at 6 s, SF12 | | 14 symbols (459 ms) |

**RX2 is opened only when RX1 brought nothing:**
```c
if( LMIC.dataLen == 0 || !processDnData() ) {
    schedRx12(sec2osticks(LMIC.rxDelay +(int)DELAY_EXTDNW2), FUNC_ADDR(setupRx2DnData), LMIC.dn2Dr);
```
(lmic.c:1785-1786). So **a downlink in RX1 saves the whole RX2 window.**

**Ramp-up before each window.** The window job runs RX_RAMPUP_DEFAULT (10 ms, oslmic.h:131) early. It then spins in `hal_waitUntil` with the radio in standby.

### 1.4 Assumptions to confirm

| ID | Assumption | What depends on it |
|---|---|---|
| A1 | Rail at 3.3 V | |
| A2 | I_tx = 40 mA at +10 dBm on PA_BOOST | |
| A3 | PMIC efficiency η = 0.85 at these loads | |
| A4 | Back-feed of 0.4 mA (range 0.3-1.1 mA) with sensors plugged into both headers | |
| A5 | A TDMA downlink arrives in RX1 on every frame | Case A |
| A6 | 24 gas and 48 T/RH tasks a day | Only an illustration; the server decides the rate |
| A7 | Cycle counts behind the idle currents (about 62 µs per `loop()` pass and about 1.5 % ISR duty) | |
| A8 | ENS160 breakout draws about 4 mA during its 0.19 s start (3 mA IDLE + LED) | |
| A9 | SHT41 breakout draws 1 mA and has about 10 µF of input capacitance | |
| A10 | The PIT phase is random relative to the slot | Mean 0.5 s edge wait and mean 1.5 s idle tail |

---

## 2. Timelines

### 2.1 How the node sleeps (code facts)

**Two sleep modes**, both through LowPowerAVRZero, which only sets SLPCTRL and executes `sleep`:

- **Power-down:** `LowPower.powerDown();` at L419 (`sleepUntil`) and L630 (`brownOutBackOff`).
  - Only the RTC PIT and the WDT run (DS Table 11-1, §11.3.2.1).
  - The PIT runs from OSCULP32K: `RTC.CLKSEL = RTC_CLKSEL_INT1K_gc;` (L1253) and `RTC.PITCTRLA = RTC_PERIOD_CYC1024_gc | RTC_PITEN_bm;` (L1256). That is 1024 cycles of 1.024 kHz, i.e. **1 wake per second** (ISR at L357-361), followed by `watchdogKick()`.
  - XOSC32K is not used; PF0/PF1 are input-disabled.
- **Idle:** `LowPower.idle();` at L405 and L431 (`sleepUntil`) and L1327 (`loop()`).
  - The CPU stops; every peripheral runs.
  - The millis TCB wakes the CPU every 1 ms. TCA0/TCB PWM, the USART (DEBUG 1), SPI and the BOD (continuous) also run.
- **Standby is never used.**

**`loop()` never spins at full speed.**
- `os_runloop_once()` (oslmic.c:158-174) runs one job or calls `lmic_hal_sleep()`.
- `lmic_hal_sleep()` is empty (hal.cpp:427-429, `// Not implemented`), so control returns to `loop()`, which idles (L1327). The cost is one `loop()` pass per 1 kHz wake.
- **The node sleeps (power-down) only through `sleepUntil()`.** That happens only when `sleepPending && !lmicTxBusy()` (L1312).
- **`sleepPending` is set only by EV_JOINED (L1089), EV_TXCOMPLETE (L1199) and EV_TXCANCELED (L1209).**

**Busy-waits with the CPU active:**

| Where | Code | Duration |
|---|---|---|
| `measurePitTick` | L382, L385 | 4-5 s per boot |
| `railRamp` | `delayMicroseconds`, L663-673 | 67.2 ms per header switch-on |
| `headerOn` | `delay(5)`, L688 | 5 ms |
| `gasStart` | `delay(100)` L788 and `delay(10)` L794 | 110 ms |
| ENS160 poll | `delay(100)`, L877 | 0-1.5 s |
| SHT4x `getEvent` (high precision) | `delay(10)` in the library | 10 ms |
| `readVstoMv` | `delayMicroseconds(100)` L910 plus 17 conversions | ≈ 3.2 ms |
| LMIC `hal_waitUntil` (hal.cpp:345-388) | | ≈ 10 ms before every RX window |
| `Serial.flush()` and blocking `Serial` writes once the 64-byte buffer is full (DEBUG 1) | L397, L623, L1307 | |

**Radio:** LMIC puts the SX1276 to sleep after every TX/RX interrupt: `opmode(OPMODE_SLEEP);` (radio_sx127x.c:1516-1517).
- After RX1, or after RX2 if it is opened, the radio sleeps [C].
- **The exception is the time from reset until `os_init()` (L1274).** In that time the radio stays in whatever state it was in (see sink S9).

**ADC:** disabled at boot (`ADC0.CTRLA &= ~ADC_ENABLE_bm;`, L1226). It is enabled only inside `readVstoMv` (L903) and disabled again at L916. `analogReference(INTERNAL2V5)` only selects the reference, so VREF runs only while the ADC uses it [C, MegaCoreX]. **Neither is left on.**

**TWI:** enabled from `headerOn()` → `selectBus()` → `Wire.begin()` until `headerOff()` → `Wire.end();` (L702).
- It stays enabled during the roughly 29 s of ENS160 heating. That costs nothing in power-down; the 24 µA in Table 32-8 is for active/idle.
- **It is not left on otherwise.**

### 2.2 (a) Status frame, case A (downlink in RX1), DEBUG 1

t = 0 is the slot start, when `millis() == nextSlotAt`. Energy = I × 3.3 V × t.

| # | Phase | Code | Time | On | I | Energy |
|---|---|---|---|---|---|---|
| 1 | Idle tail of `sleepUntil` | L429-433 | 1.0-2.0 s, mean 1.5 s [A10] | CPU idle, 1 kHz tick | 0.86 mA | 0.86 × 3.3 × 1.5 = **4.26 mJ** |
| 2 | `do_send`: VSTO read (ADC ≈ 3.2 ms), payload, DBG | L927-1050, L900-925 | ≈ 15 ms [A] | CPU active | 2.9 mA | 2.9 × 3.3 × 0.015 = 0.14 mJ |
| 3 | TX of the 17 B status, SF7, 10 dBm | LMIC | 71.9 ms | Radio TX + idle loop | 40 + 0.96 mA | 40.96 × 3.3 × 0.0719 = **9.72 mJ** |
| 4 | Wait for RX1 | `loop()` L1327 | 968 ms | Idle loop; radio asleep | 0.96 mA | 0.96 × 3.3 × 0.968 = **3.07 mJ** |
| 5 | RX1 ramp-up spin | `hal_waitUntil` | ≈ 9 ms | CPU active; radio standby | 2.9 + 1.6 mA | 4.5 × 3.3 × 0.009 = 0.13 mJ |
| 6 | RX1: opens 22 ms early, then a 51.5 ms downlink | LMIC | 73.5 ms | Radio RX + idle loop | 11.5 + 0.96 mA | 12.46 × 3.3 × 0.0735 = **3.02 mJ** |
| 7 | EV_TXCOMPLETE, `applySchedule`, DBG | L1125-1200 | ≈ 5 ms | CPU active | 2.9 mA | 0.05 mJ |
| 8 | `sleepUntil`: `Serial.flush`, then wait for the PIT edge | L396-407 | 0-1 s, mean 0.5 s | CPU idle | 0.86 mA | 0.86 × 3.3 × 0.5 = **1.42 mJ** |
| 9 | Power-down | L417-421 | 26.86 s | PIT, WDT; radio asleep | 2.2 µA | 0.0022 × 3.3 × 26.86 = 0.20 mJ |
| | **Total** | | 30.0 s | | | **22.0 mJ**, plus ≈ 0.35 mJ for the DEBUG UART |

- **The node is awake 3.14 s of every 30 s (10.5 %).** That awake time costs 13.2 mJ, or 60 % of the frame. Of it, 9.7 mJ is TX and 3.5 mJ is CPU idle.
- **DEBUG UART:** about 394 characters per status+sync frame at 115200 baud (86.8 µs each) is 34 ms of UART time. The CPU busy-waits while the 64-byte buffer is full and inside `Serial.flush`. That adds at most 34 ms × (2.9 − 0.86) mA × 3.3 V ≈ 0.23 mJ, plus the USART itself → ≈ 0.35 mJ per frame [A], or ≈ 1 J/day. An attached USB-serial adapter can also load PA0 (TX idles high). That load is unknown and bench-only.
- **Per day:** 2880 × 22.0 mJ = **63.4 J**, plus 1.0 J for DEBUG.

**Receive-window variants** (everything else unchanged):

| Case | What changes | Per frame | Per day |
|---|---|---|---|
| A: downlink in RX1 | (table above) | 22.0 mJ | 63.4 J |
| B: downlink in RX2 at SF12 | RX1 times out: 48.1 ms × 12.46 mA × 3.3 V = 1.98 mJ. Idle loop for 0.92 s until RX2: 2.92 mJ. RX2 spin: 0.13 mJ. RX2 opens 42 ms early, then a 1318.9 ms downlink: 1.361 s × 12.46 mA × 3.3 V = 55.96 mJ | **79.9 mJ** | **230 J** |
| C: no downlink | RX1 timeout 1.98 mJ + idle 2.92 mJ + spin 0.13 mJ + RX2 timeout (294.9 ms × 12.46 mA × 3.3 V = 12.13 mJ) | **36.1 mJ** | **104 J** |

**Conclusion:** an uplink answered in RX1 is the cheapest frame. No answer costs 64 % more; an answer in RX2 at SF12 costs 3.6 times as much.

### 2.3 (b) T/RH frame (the reply slot; the task arrived in an ordinary status frame one frame earlier)

Compared with 2.2, two steps change:

**Step 2 adds the read** (`readTask`, L822-857).
- `headerOn` runs `railRamp`. That is 151 pulses: the on-times step from 50 to 800 µs in 5 µs steps (64.2 ms), plus 151 × 20 µs off (3.0 ms). Total 67.2 ms busy.
- Then `delay(5)` (L688), `Wire.begin`, the SHT4x `getEvent` (command, `delay(10)`, read), and `headerOff`.
- CPU: about 85 ms active → 2.9 × 3.3 × 0.085 = 0.81 mJ.
- Breakout: 1 mA for about 80 ms = 0.26 mJ [DSm/A9].
- Inrush: C·V² = 10 µF × 3.3² = 0.11 mJ [A9].
- **Total +1.12 mJ.**
- The first task after a boot also runs `findSensor()`, which can add two more ramps: about +1.3 mJ once per boot.

**Step 3 sends a 5-byte payload** (PHY 18 B, 51.5 ms) → 40.96 × 3.3 × 0.0515 = 6.96 mJ. **That is 2.76 mJ less than a status frame.**

**Frame total ≈ 22.0 + 1.12 − 2.76 = 20.4 mJ.** A T/RH reply frame is cheaper than a status frame.
- The SHT41 header is on for about 85 ms per task, 67 ms of which is the bench-proven ramp.
- **Nothing worth saving here.**

### 2.4 (c) Gas task: arrival frame k, heater, reply frame k+1 (case A)

**Arrival frame k:** steps 1-6 are as in a status frame. Step 7 grows: EV_TXCOMPLETE → `gasStart();` (L1169), which runs:
- `headerOn`: 67.2 ms ramp + 5 ms
- `ens160SetMode(ENS160_OPMODE_RESET); delay(100);` (L787-788)
- IDLE, `delay(10)` (L794)
- STANDARD, then a mode read-back (L795)

Cost of the start:
- CPU: about 190 ms active → 2.9 × 3.3 × 0.19 = 1.82 mJ.
- Board: about 4 mA for 0.19 s → 2.5 mJ [A8].
- Inrush: 0.1-0.5 mJ.
- **Total ≈ +4.9 mJ; the frame comes to ≈ 26.9 mJ.**

**Heater:**
- It turns on at about t = +1.33 s in frame k: TX 72 ms + 1 s + RX1 74 ms + 190 ms start.
- It runs until frame k+1 reads it at about t = +0.55 s.
- That is 30 − 1.33 + 0.55 = 29.2 s at 29 mA → 29 × 3.3 × 29.2 = **2.79 J** [DSm].
- The MCU is in power-down as usual meanwhile.

**Reply frame k+1:**
- `readTask` polls the ENS160 status every 100 ms with a busy `delay(100)` (L871-878) until a new sample appears. The ENS160 makes one sample a second, so this takes 0-1 s, mean ≈ 0.55 s: 2.9 × 3.3 × 0.55 = 5.26 mJ.
- Then `gasStop();` (L891) → `headerOff`, **before** TX, so the heater is never on during TX.
- TX sends a 9-byte payload (PHY 22 B, 56.6 ms): 7.65 mJ, which is 2.07 mJ less than a status TX.
- **Frame ≈ 22.0 + 5.26 − 2.07 ≈ 25.2 mJ.**

**Marginal cost of one gas task ≈ 2.79 J + 4.9 mJ + 3.2 mJ ≈ 2.80 J.**
- That equals 127 status frames, or about one hour of status traffic.
- In the server's units it is 1.46 energy units (1 unit = 1.92 J).
- The server's `COST_GAS` is 30 units = 57.6 J (L280), about 20 times the real cost. T/RH costs 10 units (19.2 J) against about 1 mJ real.
- This is not a firmware issue; it is noted for the task-assignment algorithms.

**Is the ENS160 really switched off?** Yes.
- `gasStop()` → `headerOff()` runs `Wire.end`, input-disables the pins and does `digitalWriteFast(PIN_RAIL_A/B, LOW)` (L702-709).
- The same happens for a skipped task (L951-954) and a failed start (L796-802).
- **The heater runs longer than one frame only if the reply is delayed:**
  - Each "LMIC busy, waiting" retry (L929-935) adds 1 s × 29 mA × 3.3 V = 96 mJ.
  - A skipped (passed) slot (L1316-1317) adds a whole frame, 2.8 J.

### 2.5 Per-boot and event costs

| Event | Breakdown | Energy |
|---|---|---|
| Boot without a brown-out | **`measurePitTick`:** busy 4-5 s at 2.9 mA → 43 mJ. **Radio standby until `os_init`:** about 4.5 s × 1.6 mA × 3.3 V = 24 mJ [DSm, unverified]. **Join:** idle loop for rnd 0-8 s (≈ 12.7 mJ), JoinRequest SF7 61.7 ms × 40.96 mA (8.3 mJ), 5 s idle loop to RX1 (15.8 mJ), JoinAccept RX ≈ 0.15 s (≈ 6 mJ), EEPROM DevNonce write (0.04 mJ) → ≈ 43 mJ | **≈ 110 mJ** |
| Brown-out rest (L610-632) | Power-down for 30-480 s. If the radio is in standby (S9): 1.6 × 3.3 × (30…480 s) = 0.16…2.5 J. The back-feed adds 0.4 × 3.3 × t = 0.04…0.63 J | **0.2-3.1 J** |
| Hourly sensor retry while a part is left off (L1299-1310) | A software reset → a full boot and join, about 110 mJ, 24 times a day | ≈ 2.6 J/day |
| Extra LMIC uplink (OP_POLL or a port-0 MAC answer, S12) | `lmicTxBusy()` keeps the node awake until the 1 % duty cycle allows, about 7.2 s after the data TX: ≈ 7 s × 0.96 mA × 3.3 V = 22 mJ. Empty uplink of 41 ms: 5.6 mJ. RX1 + RX2 timeouts: ≈ 17 mJ | **≈ 45 mJ each** |
| Unjoined (gateway unreachable) | `OP_JOINING` is cleared only by a JoinAccept (lmic.c:1625) or `LMIC_setSession` (lmic.c:3075). `sleepPending` is never set, so `loop()` idles around the clock: 0.96 × 3.3 × 86400 = 274 J/day. After the SF7 → SF12 sweep (about 2.8 h) there is one SF12 JoinRequest per 1483 s (0.1 % band) + 3 s + rnd(0-255 s) ≈ 1614 s, i.e. 53.5 a day. Each costs TX 1.483 s × 40.96 mA × 3.3 V = 200 mJ plus RX 0.885 s × 12.46 mA × 3.3 V = 36 mJ, so 12.6 J/day | **≈ 287 J/day** |

### 2.6 Per day and days to empty (384 J store, no harvest)

The store-side figure is rail ÷ 0.85 + 3.2 J/day.

| Scenario | Rail J/day | Store J/day | Days |
|---|---|---|---|
| Status frames only, case A, DEBUG 0, no back-feed | 63.4 | 77.8 | 4.9 |
| + DEBUG 1 | 64.4 | 79.0 | 4.9 |
| + 24 gas and 48 T/RH tasks a day [A6] (gas 24 × 2.802 J, T/RH 48 × −1.6 mJ) | 131.6 | 158.0 | 2.4 |
| + back-feed 0.4 mA [A4] = **reference** | **245.6** | **292.1** | **1.3** |
| Reference with downlinks in RX2 at SF12 | 412.4 | 488.4 | 0.8 |
| Reference with no downlinks (case C) | 286.2 | 339.9 | 1.1 |
| Unjoined, no tasks, with back-feed | 401 | 475 | 0.8 |
| Reference after F1 + F2 + F7 | 115.6 | 139.2 | 2.8 |
| Status frames only after F2 + F7, no back-feed | 48.4 | 60.1 | 6.4 |

Storage-side sinks, not caused by firmware [DS/C]:

| Sink | Current | Per day |
|---|---|---|
| LiC leakage | ≤ 9 µA × 3.2 V | ≤ 2.5 J/day |
| VSTO divider | 1.6 µA | 0.44 J/day |
| PMIC Iq | 0.875 µA | 0.24 J/day |

PMIC conversion loss is (1/η − 1) × rail ≈ 43 J/day in the reference scenario [A3].

---

## 3. Ranked energy sinks (reference scenario)

### S1. Back-feed through the I2C pull-ups into switched-off headers (HARDWARE)

**Where:** L696-697:
> `// On rev 2 the bus pull-ups R9-R12 sit on the always-on 3V3, so a sensor whose header is off is`
> `// back-fed through SDA/SCL (estimated 0.3-0.5 mA, not measured).`

**Mechanism:**
- In the rev-2 schematic, R9-R12 are 10 kΩ to 3V3 on SCL_A, SDA_A, SCL_B and SDA_B.
- With a header off, the MIC94069 holds VCC_SENS low. L647 says the switch "drains it while off".
- So each line can feed up to (3.3 − ≈ 0.5 V clamp) ÷ 10 kΩ ≈ 0.28 mA into the dead breakout. Four lines give at most 1.1 mA.
- The firmware comment estimates 0.3-0.5 mA.

**Cost:** 0.4 mA × 3.3 V × 30 s = 39.6 mJ per frame, 1.8 times a whole status frame. **That is 114 J/day (range 86-314).**
- It flows around the clock, including during brown-out rests. There, it works against the recharge the rest is for.

**The firmware cannot fix it:**
- Driving SDA/SCL low sinks 0.33 mA per line from the pull-up instead.
- Keeping the headers powered costs the breakouts' LED/LDO (about 0.5-1 mA each) and undoes the bench-tested per-task power design.

**Fix: F1 (hardware).** Measure first (V2).

### S2. ENS160 heater (DESIGN)

**Where:**
- `gasStart` (L769-806), started from EV_TXCOMPLETE (L1169).
- `ens160SetMode(ENS160_OPMODE_STANDARD)` (L795).
- Read and switched off in the next slot (L859-893).
- The intent is in L766-768: "heated for a whole frame (30 s) by the reply slot … the 30 s value is sent with that status [warm-up]".

**Cost:**
- 2.79 J per task (29.2 s × 29 mA × 3.3 V), plus 8 mJ for the start and the poll.
- 67.3 J/day at 24 gas tasks a day [A6]; it scales as 2.8 J × tasks per day.

**BUG part (F5):** with TEST_IGNORE_ENERGY 0, the energy check runs at the reply slot, **after** the heater has already run:
```c
if (!TEST_IGNORE_ENERGY && pendingCommand != 0 && energy < taskCost(pendingCommand))   // L942
...
      gasStop();                                                                        // L953
```
So a gas task that cannot be afforded still burns 2.8 J.

**Design part:** only the user can trade warm-up time for energy (F11).

### S3. LoRa TX (DESIGN, set by the cadence)

**Where:**
- `LMIC_setDrTxpow(DR_SF7, settings.txPowerCap);` (L1082)
- `LMIC_setAdrMode(0);` (L1081)
- `const int8_t TX_POWER_DBM = 10;` (L185), applied again in EV_TXSTART (L1095-1096)
- One uplink per 30 s frame.

**Cost (radio only):**
- 71.9 ms × 40 mA × 3.3 V = 9.49 mJ per status frame.
- 2808 status frames × 9.49 mJ + 48 × 6.80 mJ + 24 × 7.47 mJ = **27.2 J/day**.

**Already optimal within the contract.** SF7 is the fastest data rate, and SF12 would cost 23 times as much. Shrinking the status payload would change the codec, so it is ruled out; 17 B → 10 B would save only 1.35 mJ per frame anyway.

**What is left is design:** cadence (F12), or a lower TX cap if the link allows. PA_BOOST current at low power is unknown, so measure it first (V4).

### S4. `sleepUntil()` idle before every slot (BUG-class)

**Where:**
- L401-407 waits for a PIT edge in idle.
- L409-427 does the power-down. Then L429-433 runs the idle tail: `while ((int32_t)(target - millis()) > 0) { LowPower.idle(); watchdogKick(); }`.

```c
uint32_t ticks = left > 0 ? (uint32_t)left * 1000UL / usPerTick : 0;   // L410
if (ticks > 0)
{
  ticks--;  // keep up to one tick for the idle part: never wake past the target   // L413
```

**Cost:**
- With a 1 s PIT (`RTC_PERIOD_CYC1024_gc`, L1256), the floor() plus `ticks--` leaves a 1-2 s idle tail. Add 0-1 s of edge wait.
- Mean 2.0 s × 0.86 mA × 3.3 V = **5.68 mJ per frame, 26 % of a status frame → 16.4 J/day.**

**Why it is waste:** the long tail buys no accuracy.
- `millis()` is credited by computation, not by measurement: `uint32_t us = ticks * usPerTick + usCarry;` … `timer_millis += us / 1000UL;` (L422-425).
- So the tail only absorbs the floor() remainder. It cannot "wake past the target" in the millis domain with any tick length.
- OSCULP32K drift after the boot calibration (±3 % factory at 25 °C/3 V, ±10 % over 0-70 °C, DS Table 32-14) gives a real-time wake error of drift × sleep length. That error is the same for any tick length, and the server's slot correction absorbs it.

**Fix: F2.**

### S5. Class A wait in idle (DESIGN, partly avoidable)

**Where:** `loop()` → `LowPower.idle();` (L1327) while `lmicTxBusy()`. OP_TXRXPEND is set from TX start (lmic.c:2697) until the cycle ends (lmic.c:2349). The comment at L1326 says: "Idle keeps the 1 ms millis tick running, so LMIC's receive-window timing still holds."

**Cost:** TX + gap + RX1 = 1.114 s × 0.96 mA × 3.3 V = 3.53 mJ per frame → **10.2 J/day**.

**Options:**
- Power-down would stop millis and endanger RX1 timing, so it is not safe.
- Standby with the millis TCB set to RUNSTDBY keeps the timing (F6, optional).

### S6. RX1 (DESIGN)

**Cost:** 73.5 ms × 11.5 mA × 3.3 V = 2.79 mJ per frame → **8.0 J/day**.

The 22 ms early opening (≈ 0.83 mJ of that) comes from `LMIC_setClockError(MAX_CLOCK_ERROR * 2 / 100);` (L1278). It is justified by OSC20M's ±2 % over 0-70 °C (DS Table 32-13, E_TOTAL). **Keep it.**

### S7. DEBUG UART (bench setting; BUG for deployment)

**Where:** `#define DEBUG 1` (L71).

**Cost:** ≈ 0.35 mJ per frame → ≈ **1 J/day**, plus any load from an attached adapter.

With DEBUG 0, the sketch compiles out every print and `Serial.flush`, and disables PA0/PA1 (L1247-1248). **Everything else is identical.** Fix: F7.

### S8. Active compute (DESIGN)

VSTO read, payload build, LMIC processing and the RX ramp spin: ≈ 0.33 mJ per frame → 0.94 J/day.

### S9. Radio in standby until `os_init()` (BUG candidate, unverified)

**Where:** the `setup()` order is:
1. `brownOutBackOff();` (L1258): power-down for 30-480 s after a brown-out.
2. `usPerTick = measurePitTick();` (L1260): 4-5 s.
3. `os_init();` (L1274): resets the radio and puts it to sleep.

**Why it costs energy:**
- Until `os_init()` the SX1276 stays in its reset state after a power-on. That state is standby (RegOpMode reset value 0x01 [DSm]), at 1.6 mA.
- After an MCU brown-out, the radio is in whatever state it was left in. A TX or RX that ends returns it to standby by itself (comments at radio_sx127x.c:948-949 and 1124-1125).
- NSS (PA7) is also an undriven input until `os_init` [C].

**Cost:**
- 24 mJ per boot.
- **0.16-2.5 J per brown-out rest.** A 480 s rest with the radio in standby costs 2.5 J, which works directly against the recharge the rest is for.

**Fix: F4.**

### S10. `measurePitTick()` busy spin (BUG-class, small)

```c
while (readPitTicks() == t) { watchdogKick(); }                    // L382
while ((uint16_t)(readPitTicks() - t) < TICKS) { watchdogKick(); } // L385
```

**Cost:** 4.5 s × 2.9 mA × 3.3 V = 43 mJ per boot. With idle inside the loops it would be 12.8 mJ.

**Fix: F8.**

### S11. Unjoined: the CPU idles around the clock (BUG-class, conditional)

This applies whenever the network is unreachable, for example when the gateway is down or out of range. It costs **≈ 287 J/day**, enough to empty the store in about 1.3 days on its own (section 2.5). **Fix: F3.**

### S12. Extra LMIC uplinks (conditional, driven by the server)

**Where OP_POLL and OP_TXDATA get set:**
- A confirmed downlink or FPending: `if( LMIC.dnConf || (fct & FCT_MORE) ) LMIC.opmode |= OP_POLL;` (lmic.c:1259-1260).
- Pending MAC answers: OP_POLL at lmic.c:2357, or OP_TXDATA for a port-0 answer at lmic.c:2368.

**Cost:** each forced uplink costs ≈ 45 mJ and lands in another node's TDMA slot.
- **If the TDMA server sent confirmed downlinks every frame, this would add ≈ 130 J/day.**
- Rare MAC commands (for example a daily DevStatusReq) cost little.

The repo cannot say which applies; see V1 and question Q1.

### S13. ENS160 poll busy-wait (negligible)

`delay(100)` at L877 costs ≈ 5.3 mJ per gas task, or 0.13 J/day at 24 tasks a day. **Fix: F9** saves 3.7 mJ per task.

### S14. Header switch-on ramp (DESIGN; do not touch)

`railRamp` (L663-673) is 67.2 ms busy → ≈ 0.64 mJ per switch-on. It is bench-proven:
- 36 of 36 plain switch-ons browned the node out.
- This ramp passed 8 of 8 at 3.04 V.

(`RESULTS.md`; comment at L647-655.)

### S15. Peripheral clocks in idle (small)

- MegaCoreX `init()` starts TCA0 in split-mode PWM at F_CPU/16 and the PWM TCBs; the sketch does not use them. They draw ≈ 10-15 µA while the CPU is awake ([DS] Table 32-8, scaled) → ≈ 0.5 J/day. **Fix: F10.**
- SPI stays enabled after `os_init`; it draws 2.1 µA in active/idle (Table 32-8). Negligible.

### S16. Power-down floor (DESIGN floor)

2.2 µA → 0.56 J/day.

---

## 4. Suspect checklist (each item from the brief)

### 4.1 Does `loop()` ever spin awake?

**No.** It idles (L1327) and is woken by the 1 kHz millis tick. The opmode bits in LMIC 6.0.1 behave as follows:

| Bit | Set at | Cleared at | Can it stay set while joined? |
|---|---|---|---|
| OP_TXRXPEND | TX start, lmic.c:2697 | End of the Class A cycle (2349); JoinAccept and join paths (1625, 1659, 1662, 1671); 2320/2331 (confirmed/repeat); 2688; 2896 | No. It is cleared at the end of every cycle |
| OP_TXDATA | `LMIC_setTxData`, 2966; port-0 MAC answer, 2368 | 2349, 2688, 2892 | No |
| OP_POLL | Confirmed or FPending downlink, 1260; piggyback MAC answers, 2357; `LMIC_sendAlive`, 3031 | TX start, 2697 (`LMIC.opmode = (LMIC.opmode & ~(OP_POLL|OP_RNDTX)) | OP_TXRXPEND | OP_NEXTCHNL;`); 2688; 2892; `startJoining`, 2170 | Only while the server keeps sending confirmed or FPending downlinks, or MAC commands. Each forced uplink clears it again (S12) |
| OP_JOINING | `LMIC_startJoining`, 2179 | JoinAccept, 1625; `LMIC_setSession`, 3075 | Not after a join. **It stays set forever while joins fail (S11)** |

So in normal joined operation no bit sticks [C]. The mask in `lmicTxBusy()` (L340-343) matches LMIC's own "TX path busy" test.

### 4.2 Awake time around the uplink

The node is awake **3.14 s per frame** (table 2.2):
- 2.0 s idle in `sleepUntil` (S4)
- 15 ms active in `do_send`
- 72 ms TX
- 0.97 s idle waiting for RX1
- 74 ms RX1
- about 20 ms of other active work

**All gaps already use idle, not active spinning.**
- Power-down in the TX → RX1 gap is not safe. It stops millis, and the ULP calibration error over about 1 s could exceed the 22 ms early-opening margin.
- **Standby, with the millis TCB set to RUNSTDBY, is the safe variant (F6).**

### 4.3 DR, SF, TX power, ADR, RX2 and LinkCheck

**Data uplinks:**
- SF7/DR5 (L1082), ADR off (L1081).
- TX power: LMIC uses `LMIC.radio.txpow = LMIC.txpow > LMIC.adrTxPow ? LMIC.adrTxPow : LMIC.txpow;` (lmic.c:2700). EV_TXSTART then caps it (L1095-1096) → 10 dBm.
- `LMIC_setTxData2` changes the DR only if the payload does not fit; 17 B fits DR5.

**Joins:**
- They start at SF7 and step down one DR after each pass over the three join channels, to SF12, then stay there.
- Power is min(14 dBm band, 16 dBm) = **14 dBm**, not the 16 dBm the comment at L1092-1093 says. It is then capped to 10 dBm.

**Status airtime:** 71.9 ms at SF7, against 1646.6 ms at SF12.

**RX2:** opened only when RX1 brings nothing (lmic.c:1785-1786). Its DR comes from the JoinAccept (lmic.c:1632). If ChirpStack leaves RX2 at DR0, RX2 costs 12.1 mJ on a timeout and 56 mJ with an SF12 downlink.

**LinkCheck is off** (`LMIC_setLinkCheckMode(0);`, L1078).
- With it off, `setAdrAckCount` does nothing: `if (LMIC.adrAckReq != LINK_CHECK_OFF)` (lmic.c:1115-1119). So **LMIC never sets ADRACKReq and never unjoins or rejoins**, and there is no LinkCheck traffic.
- MAC traffic happens only when the server sends MAC commands (S12).

### 4.4 Joins

- The node joins once per boot (L1291) and never rejoins on its own.
- Every reset rejoins: power-on, brown-out, WDT, and the hourly software reset (L1309).
- A successful join costs ≈ 43 mJ.
- When joins fail, each SF12 attempt costs ≈ 236 mJ of radio, on top of the CPU idling around the clock (≈ 287 J/day in total, S11).

### 4.5 ENS160 heating

See section 2.4.
- The heater costs 2.79 J per task.
- The ramp and start sequence add about 190 ms active (1.8 mJ); polling adds about 0.55 s (5.3 mJ).
- The sensor really is switched off afterwards: `gasStop` → `headerOff` → EN low.
- The energy check comes too late (F5).

### 4.6 SHT41

The header is on about 85 ms per task: 67 ms of ramp, 5 ms, and about 11 ms of measurement. That costs ≈ 1.1 mJ. **Not worth optimising.**

### 4.7 Serial, `delay()` and millis-polling loops

- DEBUG 1 is covered in S7.
- Every `delay()` and busy-wait is listed in section 2.1.
- The millis-polling loops are:
  - the `sleepUntil` tail (idle inside, fine);
  - `loop()` itself (idle);
  - the skip-a-passed-slot `while` (L1316-1317), which is arithmetic only.

### 4.8 VSTO ADC

- Read once per frame (L937) and once per boot (L1266), about 3.2 ms each with the ADC on, ≈ 34 µJ per frame.
- The ADC is disabled after each read (L916); the reference goes off with it.
- The 1 MΩ + 1 MΩ divider leaks 1.6 µA from the storage continuously. That is hardware.

### 4.9 Brown-out rests

**The node rests in power-down** (L625-632), not awake.

**The rest escalates sanely:** 30, 60, 120, 240, 480, 480 … s.
- The formula is `(uint32_t)BROWNOUT_WAIT_S << (run - 1 < 5 ? run - 1 : 5)`, capped at 480 s (L613-615).
- A brown-out pinned on a culprit rests once for 30 s (run = 1, L610).
- The run count is cleared after 3 good uplinks (L1180-1184) or on any boot that is not a brown-out (L588-589).

**Two leaks during the rest:** the radio is not yet asleep (S9), and the back-feed keeps flowing (S1).

BOD is disabled in power-down (fuse SLEEP disabled), so the rest itself cannot cause a reset.

### 4.10 EEPROM writes

**No writes per frame.**

**Writes that do happen:**
- The DevNonce at every JoinRequest (L1098-1104). `EEPROM.put` only writes changed bytes: 1 byte usually, 2 bytes every 256th time.
- The TX cap after a brown-out during TX (L533).
- First boot (L507).

**Energy:** 4 ms per byte (Table 32-34) × 3 mA (flash write, Table 32-8) × 3.3 V ≈ 0.04 mJ. Negligible.

**Wear** (100k cycles, Table 32-34):

| Case | Writes/day | Time to 100k |
|---|---|---|
| Unjoined at SF12 | ≈ 54 | about 5 years |
| A brown-out boot loop at the 30 s rest | ≈ 2160 | 46 days |
| With the back-off doubling to 480 s | ≈ 180 | about 1.5 years |

### 4.11 Pins

All 40 pins are accounted for:

| Pin(s) | State | Notes |
|---|---|---|
| PB0-5, PC0, PC4-7, PD0-5, PE0-3, PF0-1 (unused) | Input buffers disabled | `UNUSED_PINS` (L137-142, applied at L1228-1229). Leakage only, < 0.05 µA (Table 32-17) |
| PA0/PA1 (UART) | Disabled with DEBUG 0 (L1247-1248); PA1 pull-up with DEBUG 1 (L1240) | |
| PA2/PA3/PC2/PC3 (TWI) | Held high by R9-R12 at boot, so they do not float. Input-disabled after first use (L704-705) | **With F1 they would float at boot** |
| PA4/PA6/PA7 (SPI) | Driven by SPI after `os_init` | |
| PA5 (MISO) | Pull-up (L1279) | The radio tri-states it, so no current |
| PD6/PC1 (header enables), PD7 (LED) | Outputs, low (L1230-1235) | The LED is never switched on |
| PF2/PF4/PF5 (DIO) | Inputs | Driven by the radio |
| PF3 (radio RST) | Left as an input by LMIC after the reset pulse | Whether it floats depends on the module; unverified |
| PA7 (NSS) | Undriven input before `os_init` | See S9 |

### 4.12 `hal.cpp`

- It starts no timers.
- SPI runs at 1 MHz (`LMIC_SPI_FREQ`) and stays enabled; negligible.
- The DIO lines are polled in `lmic_hal_enableIRQs` (hal.cpp:403-421). That is why `loop()` must wake every millisecond during TX/RX.
- `lmic_hal_sleep()` is empty (hal.cpp:427-429), so there is no busy loop.
- `hal_waitUntil` (hal.cpp:345-388) uses `delay()` in 8 ms steps, then spins. It is used only for the ≈ 10 ms RX ramp and in `radio_init`.

### 4.13 RTC/PIT

- Clock: OSCULP32K through INT1K (L1253). No XOSC32K.
- Period: 1024 cycles = 1 s (L1256), so 1 wake per second in power-down.
- **The 1 s period is what makes S4 cost 16 J/day.**

---

## 5. Fixes: change, risk, bench verification

### 5.1 Bench measurement points

Put the PPK2 in ammeter mode (or in source mode at 3.3 V in place of the PMIC) at these points:

| Point | Where | What it shows |
|---|---|---|
| P1 | The 3.3 V rail into the board | MCU + radio + headers |
| P2 | VCC_SENS_A / VCC_SENS_B | Each header |
| P3 | The storage terminal U11, if it can be broken out | The whole store-side draw, including PMIC loss |

### 5.2 Checks used below

**V1 — which window the downlink uses** (answers A5 and Q1).
- On P1 around an uplink, look for an RX burst of about 74 ms at about 12 mA, exactly 1 s after TX. That is an RX1 hit.
- A 48 ms burst at +1 s followed by a 0.3 s burst (no downlink) or a 1.36 s burst (SF12 downlink) at +2 s means RX2.
- In the log, two "EV_TXCOMPLETE" lines per frame mean forced extra uplinks (S12).
- Optional bench-only log line: print `LMIC.txrxFlags & TXRX_DNW1 / TXRX_DNW2`. Today the log only says "downlinks received N".

**V2 — back-feed.** Measure P1 while the node sleeps, between "Sleeping N ms until the slot" and the next "Sending …" line.
- Compare sensors plugged against unplugged.
- Expect about 3-5 µA unplugged, and +0.3-1.1 mA plugged.

**V3 — sleep floor.** Same window, with the sensors unplugged. Expect about 2-5 µA with PIT spikes.

**V4 — TX current.** Measure P1 during TX at the 10 dBm cap. This replaces assumption A2. If the user wants a lower cap, measure at that power too.

**V5 — heater current.** Measure P2 while the ENS160 heats.

### 5.3 The fixes

#### F1 (hardware): take R9-R12 off the always-on 3V3

**Change:**
- Remove R9-R12. The breakouts carry their own pull-ups to their own switched VCC, and `Wire.begin` also enables the MCU's internal pull-ups.
- Or move R9-R12 to VCC_SENS_A/B.
- **Firmware follow-up:** add PA2, PA3, PC2 and PC3 to the boot-time input-disable (next to L1228-1229). Without the external pull-ups these pins float until the first task. `headerOn` already re-enables them (L689-690).

**Saving:** 86-314 J/day (point estimate 114).

**Risks:**
- Bus rise time with fewer pull-ups. The Adafruit SHT41 breakout has 10 kΩ on board [DSm]; the ENS160 breakout's pull-ups are unknown. Check them, or put 10 kΩ to VCC_SENS on that header.
- `findSensor` on an empty header: the internal pull-ups (about 20-50 kΩ) keep the bus idle high, so no Wire hang is expected. A hang would be a WDT reset.

**Bench:**
- V2 before and after.
- Expect "SHT41 found on J3/J4" and "ENS160 found at 0x52 on J…".
- T/RH and gas replies should be unchanged, with no "SHT41 did not answer" or "ENS160 did not start gas sensing".

#### F2: shorter PIT period (recommended `RTC_PERIOD_CYC64_gc`, 16 Hz, 62.5 ms)

**Change:**
- L1256: the period.
- L174: the default `usPerTick = 1000000` becomes 62500.
- L378-387 `measurePitTick`: measure 64 ticks (about 4 s) for the same accuracy.
- **L625-628 `brownOutBackOff`:** `wait` is in seconds and compared against ticks, so it must become `wait * 16`. `usPerTick` is not measured yet at that point; the nominal value is fine for a rest.
- Update the comments that say "one interrupt per second" and "nominally 1 s".

**Saving:**
- Idle per frame falls from 2.0 s to 0.125 s (edge wait 31 ms + tail 94 ms) = 5.32 mJ.
- PIT wakes cost back 16/s × 26.9 s × ≈ 0.24 µJ = 0.10 mJ. Each wake is 15 µs (Table 32-7) plus about 10 µs of ISR and loop at 2.9 mA [A].
- **Net ≈ 5.2 mJ per frame ≈ 15 J/day.**

**Risks:**
1. **Counter range.** `volatile uint16_t pitTicks` (L355) is compared with a 32-bit `ticks` in `while (readPitTicks() < ticks)` (L417). The longest sleep is MAX_FRAME_MS 1800 s + up to 65.5 s correction ≈ 1866 s:

   | PIT rate | Ticks for 1866 s | Fits in 65535? |
   |---|---|---|
   | 16 Hz | 29,856 | Yes |
   | 32 Hz | 59,712 | Yes |
   | 64 Hz | ≈ 119,400 | **No** |

   **At 64 Hz or faster the counter overflows.** L417 then never ends, and because the WDT is kicked inside the loop, **the node sleeps forever.** Do not go above 32 Hz without widening `pitTicks` to 32 bits.
2. Forgetting the back-off conversion makes every rest 16 times shorter, so brown-out loops come back.
3. 32-bit arithmetic still fits: `(uint32_t)left * 1000UL` ≤ 1.87e9, and `ticks * usPerTick` ≤ 29,856 × 68,750 = 2.05e9.
4. The PIT sync wait `while (RTC.PITSTATUS > 0)` is already in place (L1255).

**Bench:**
- Log "Sleep clock: one PIT tick = ≈ 62500 us" (±10 %).
- "TDMA sync: … correction N ms" stays in its usual range, and "!! MISSED" never appears.
- A forced brown-out shows "sleeping 30 s", and the rest really lasts 30 s.
- On P1, the idle step before TX drops from 1-2 s to under 130 ms, and 16 Hz spikes appear in power-down.

#### F3: power down during long LMIC waits (needs F2 first)

**Change:** in the `loop()` else-branch (L1324-1328), when both of these hold:
- `!(LMIC.opmode & OP_TXRXPEND)`, so no TX/RX cycle is running and no RX window can be missed;
- `!os_queryTimeCriticalJobs(ms2osticks(3000))`, so no timed job is due within 3 s (oslmic.c:176-178);

call `sleepUntil(millis() + 2000)`. When joined, cap that at `nextSlotAt` minus a margin.

**Saving:**
- Unjoined: 287 → ≈ 14 J/day.
- About 13 mJ per boot (the random 0-8 s before the first JoinRequest).
- About 20 mJ per OP_POLL duty-cycle wait.

**Risks:**
- `os_queryTimeCriticalJobs` only sees timed jobs. A runnable job (`os_setCallback`) could wait up to 2 s.
  - That is harmless for a join or a MAC uplink.
  - It is never an RX window, because those are scheduled only while OP_TXRXPEND is set.
- The `do_send` 1 s retry is a timed job, so the node does not sleep during it. That is correct.
- LMIC's duty-cycle bookkeeping inherits the ULP calibration error of the credited millis, a few percent at most. A fast ULP could let a frame out a few percent early against the 0.1 %/1 % limits.

**Bench:**
- With the gateway off, P1 shows microamps between JoinRequests, and "EV_JOINING" / "EV_JOIN_TXCOMPLETE (no JoinAccept yet)" keep their cadence.
- With the gateway on, "EV_JOINED" and "Unsynced, first uplink in N ms" appear as before.
- When joined, trigger a MAC command from ChirpStack (for example DevStatusReq). The extra uplink should still go out, and the slot timing should not change.

#### F4: put the radio to sleep at the top of `setup()`

**Change, option a (smallest):** before `brownOutBackOff()` (L1258):
1. Drive PA7 (NSS) high and call `SPI.begin()`.
2. Wait at least 10 ms after power-up for the SX1276 POR [DSm].
3. Read RegOpMode (0x01) and write it back with bits 2:0 = 000 (sleep). Keep bit 7 as read: LongRangeMode can only change in sleep.

**Change, option b:** move `os_init()` before `brownOutBackOff()`. This uses LMIC's own radio reset and sleep, but adds a few ms of RX at 11.5 mA for its random seed.

**Saving:** 24 mJ per boot, and 0.16-2.5 J per brown-out rest if the radio really is in standby there (unverified).

**Risks:**
- SPI traffic before the radio's POR completes; the 10 ms wait covers it.
- A radio still transmitting after an MCU brown-out gets cut off. That frame is lost anyway.
- LMIC's `hal_init` calls `SPI.begin()` again later; that is harmless.
- Option b goes against the "first, before anything draws current" rule at L1258. Option a draws under 1 mA for under 1 ms.

**Bench:**
- Measure P1 during "Brown-out reset 1 in a row: sleeping 30 s". Expect microamps instead of about 1.6 mA.
- Measure P1 during the first 4.5 s after a power-on.

#### F5: check the gas-task energy when the task arrives

**Change:** in EV_TXCOMPLETE, before `gasStart();` (L1168-1169):
- If `!TEST_IGNORE_ENERGY && energyUnits(readVstoMv()) < taskCost(CMD_GAS)`, do what L942-955 does one frame later: `tasksSkipped++`, log "Skipping task 0x3", set `pendingCommand = 0`, and do not start the heater.
- The next slot then sends a status packet, exactly as today.
- Keep the L942 check for T/RH tasks.

**Saving:** 2.8 J per gas task that arrives below 30 units (VSTO ≈ 2.93 V). This applies only with TEST_IGNORE_ENERGY 0.

**Risks:**
- The decision moves one frame earlier. If the storage climbed back above 30 units within those 30 s, today's code would send the gas reply and the changed code sends a status packet instead. This is the only functional difference, and the server already handles skipped tasks.
- With TEST_IGNORE_ENERGY 1 the behaviour must stay identical: the heater always starts.
- `readVstoMv` inside EV_TXCOMPLETE runs while the radio sleeps (3 ms), which is fine.

**Bench:**
- With TEST_IGNORE_ENERGY 0 and VSTO below 2.93 V: "Skipping task 0x3" appears in the arrival frame, "ENS160 on and heating …" does not, and P2 shows no heater current.
- Above 2.93 V nothing changes.

#### F6 (optional): standby instead of idle in the Class A gaps

**Change:** in `loop()` (L1327), use standby when the radio is not transmitting.
- Set RUNSTDBY on the millis TCB.
- Flush the USART first.
- Keep idle from EV_TXSTART until TX done.

**Saving:** idle current falls from 0.96 mA to ≈ 0.36 mA [A] (OSC20M 130 µA + TCB + 1 kHz wakes) over ≈ 1.04 s per frame → ≈ 2 mJ per frame ≈ **5.5 J/day** in case A, and up to about 19 J/day in cases B and C.

**Risks:**
- BOD is off in standby (fuse SLEEP disabled), so a sag is caught only at the next 1 ms wake. That is why TX must stay in idle: `learnFromBrownOut` depends on PHASE_TX brown-outs being caught.
- The millis TCB's clock source must allow RUNSTDBY. Check MegaCoreX `wiring.c`: if that TCB is clocked from TCA0, TCA0 must run in standby too.
- The USART stops in standby.
- The current is not measured; measure it before adopting this fix.

**Bench:**
- P1 between TX and RX1 drops below 0.96 mA.
- "downlinks received" keeps counting, and "!! MISSED" never appears.

#### F7: DEBUG 0 for deployment

**Saving:** ≈ 1 J/day, plus any adapter load. **Risk:** no field log.

This is already the documented battery setting (L71 comment).

#### F8: idle inside `measurePitTick()`

**Change:** add `LowPower.idle();` in both waits (L382, L385).

**Saving:** ≈ 30 mJ per boot. **Risk:** none. The idle wake takes 2.4 µs (Table 32-7) against a 4 s window.

**Bench:** "Sleep clock: one PIT tick = N us" stays the same within 0.1 %.

#### F9: idle instead of `delay(100)` in the ENS160 poll

**Change:** at L877, idle until 100 ms have passed.

**Saving:** ≈ 3.7 mJ per gas task. **Risk:** none.

**Bench:** "ENS160 heated N s" and the gas values are unchanged.

#### F10: stop the unused TCA0 and PWM TCBs

**Saving:** ≈ 0.5 J/day.

**Risk:** the millis TCB and its clock source must keep running. Check in MegaCoreX `wiring.c` which TCB runs millis and what clocks it. The sketch does not use `analogWrite`. Low value, so do this last.

#### Design options (these change function, so they are the user's call)

- **F11, shorter gas heating:** start the heater about 10 s before the reply slot instead of at arrival (wake at `nextSlotAt − 10 s`, `gasStart`, sleep again). Saves ≈ 1.9 J per task. The 30 s reading is already reported with warm-up status 1.
- **F12, cadence:** after F2 a status frame costs ≈ 16.8 mJ. That is 48.4 J/day at 30 s and 24 J/day at 60 s. The server's slot plan must change with it.
- **F13, server side:**
  - Answer every uplink in RX1 (ChirpStack RX window = RX1).
  - Set a faster RX2 DR than DR0. It reaches the node through the JoinAccept DLSettings (lmic.c:1632), and an RX2 timeout then costs about 1-2 mJ instead of 12 mJ.
  - Avoid confirmed downlinks, and avoid more than one queued downlink per uplink (FPending → OP_POLL, S12).

**Leave alone:** the switch-on ramp (S14), the ±2 % clock-error widening (S6), SF7, and per-task sensor power.

---

## 6. Functional contract (every item must survive the fixes)

### 6.1 Build and identity

- [ ] `DEBUG` (L71), `USE_ENS160` (L72), `VSTO_SENSE` (L73), `NODE_NUMBER` (L74) and `TEST_IGNORE_ENERGY` (L75) keep their meaning. Their current values stay until the user changes them.
- [ ] The `#error` checks (EU868 + sx1276, arbitrary clock error, F_CPU ≤ 10 MHz) and every `static_assert` stay.
- [ ] Node 2's sketch gets the same changes. It differs from node 1 only in 3 header lines and `NODE_NUMBER`.
- [ ] `secrets.h` layout: APPEUI and DEVEUI LSB-first, APPKEY MSB-first, read with `memcpy_P` (8/8/16 bytes).

### 6.2 LoRaWAN (LMIC 6.0.1, EU868)

- [ ] OTAA join once per boot (L1291), and no rejoin otherwise.
- [ ] The DevNonce is written to EEPROM in EV_TXSTART **before** each JoinRequest goes on air (L1098-1104), and restored at boot (L1283). A blank EEPROM takes LMIC's random DevNonce.
- [ ] On EV_JOINED: LinkCheck off, ADR off, `LMIC_setDrTxpow(DR_SF7, settings.txPowerCap)` (L1078-1082).
- [ ] Every frame, joins included, goes out at or below `settings.txPowerCap` (EV_TXSTART, L1095-1096).
- [ ] Uplinks on fPort 1, unconfirmed: `LMIC_setTxData2(1, payload, len, 0)` (L1049).
- [ ] `LMIC_setClockError(MAX_CLOCK_ERROR * 2 / 100)` (L1278). The MISO pull-up is set (L1279).
- [ ] `lmicTxBusy()` uses the mask OP_TXRXPEND | OP_TXDATA | OP_POLL | OP_JOINING.
  - `do_send` retries every 1 s while LMIC is busy.
  - A failed `LMIC_setTxData2` keeps `pendingCommand` and retries in 1 s.
  - **The node never sleeps or starts a send while LMIC is busy** (the deadlock from 2026-10-20 must not return).
- [ ] `dataFrameInFlight` is set **before** `LMIC_setTxData2` (L1048), so that EV_TXSTART stamps `txStartedAt` for data frames only.
- [ ] Downlink counters: received, and missed (from jumps in `seqnoDn`), with their log lines.
- [ ] LMIC's own MAC answers still go out.

### 6.3 TDMA timing

- [ ] Defaults until the first schedule: 2 slots × 15 s, a 30 s frame, `slotIndex = NODE_NUMBER − 1` (L157-166).
- [ ] The first uplink after the join is at `millis() + 100 + slotIndex × 15000` (L1085).
- [ ] A schedule is applied only from a **port 20** downlink with **≥ 6 bytes** that arrives **while `dataFrameInFlight`** is set:
  - d[0] = command
  - d[1] = slot
  - d[2] = number of slots
  - d[3] = frame in seconds, accepted only within 10-1800 s
  - d[4-5] = unsigned big-endian correction in ms
  - then `nextSlotAt = txStartedAt + frameMs + correction` (L464-485, L1157-1175)
- [ ] With no schedule, `nextSlotAt += frameMs` (L1179). EV_TXCANCELED does the same (L1207).
- [ ] A slot that has passed, or is less than 50 ms away, is skipped by whole frames (L1316-1317).
- [ ] Wake-up is accurate to the millisecond: `do_send` is posted only once `millis() >= nextSlotAt`.
  - `millis()`, and with it LMIC's `micros()`, is credited for the time spent in power-down, with the sub-millisecond carry kept (L422-426).
  - `usPerTick` is calibrated against `micros()` at boot.
- [ ] One uplink per frame, at the start of this node's slot.

### 6.4 Tasks

- [ ] Commands:

  | Code | Meaning |
  |---|---|
  | 0x00 | Sync only |
  | 0x01 | Humidity |
  | 0x02 | Temperature |
  | 0x03 | Gas |
  | 0x10 | Ignored, with its log line |

  A task that arrives in frame k is answered in this node's next slot.
- [ ] **Gas:**
  - The ENS160 is powered and started when the task arrives: RESET, 100 ms, IDLE, 10 ms, STANDARD, mode check.
  - It is read at the reply slot after waiting up to 15 × 100 ms for NEWDAT.
  - It is switched off **before** the uplink.
  - Status byte: the sensor's own 0-3, or 0xFD (no sample), 0xFE (no answer) or 0xFF (absent).
  - When absent: eCO2 400, TVOC 0, AQI 0.
- [ ] **T/RH:**
  - The SHT41 header is powered only for the read, unless the heating ENS160 shares that header.
  - High precision, heater off.
  - 0x7FFF if the sensor does not answer.
- [ ] **Status:**
  - Nothing is powered.
  - T/RH = 0x7FFE, TVOC 0, eCO2 0, AQI 0, ENS status 0xFC.

### 6.5 Uplink bytes

16-bit values are big-endian. The ChirpStack codec stays unchanged.

| Packet | Length | Bytes |
|---|---|---|
| Status | 17 B | [0]=0x00, [1-2] TVOC, [3-4] eCO2, [5-6] T×100, [7-8] RH×100, [9-10] VSTO mV, [11] AQI, [12] ENS status, [13] TX cap dBm, [14] reset flags of this boot, [15-16] energy units |
| Humidity reply | 5 B | [0]=0x01, [1-2] RH×100, [3-4] energy |
| Temperature reply | 5 B | [0]=0x02, [1-2] T×100, [3-4] energy |
| Gas reply | 9 B | [0]=0x03, [1-2] TVOC, [3-4] eCO2, [5] AQI, [6] ENS status, [7-8] energy |

### 6.6 Energy

- [ ] VSTO is read with: the internal 2.5 V reference, ADC prescaler ÷32, SAMPCTRL 31, a 100 µs settle, one discarded conversion and 16 averaged ones, then the divider and `VSTO_CAL` applied.
  - It is read first in every `do_send`, before the radio starts, and once at boot.
  - The ADC is off otherwise.
- [ ] `energyUnits`: 0 at ≤ 2800 mV, 200 at ≥ 3600 mV, (V² − Ve²)/(Vf² − Ve²) × 200 in between, and 200 when `VSTO_SENSE` is 0.
- [ ] Task costs are 10/10/30 (L278-280).
- [ ] `TEST_IGNORE_ENERGY` 1: no task is ever skipped, and the real energy is still reported.
- [ ] `TEST_IGNORE_ENERGY` 0: a task whose cost exceeds the energy is skipped: `tasksSkipped++`, a log line, `gasStop()`, and a status packet is sent instead.

### 6.7 Sensors and power

- [ ] Nothing is powered at boot.
- [ ] `findSensor` runs once per boot per sensor. It tries J3, then J4, one header at a time, and switches each one off again. A header already on for a heating ENS160 is probed without being switched (L718-763).
- [ ] There is one TWI, moved per access by `Wire.end(); Wire.swap(bus); Wire.begin();`. J3 = PA2/PA3 (swap 0), J4 = PC2/PC3 (swap 1).
- [ ] `headerOn`: the culprit check, then the phase set, then `railRamp` exactly as tuned (50→800 µs in 5 µs steps, 20 µs off, then on), then `delay(5)`, input buffers on, TWI on.
- [ ] `headerOff`: `Wire.end`, input buffers off (which also clears the pull-ups), EN low, phase idle, and that header's fail count reset.
- [ ] Pins: EN on PD6 (J3) and PC1 (J4); the LED on PD7 stays low; `LED_BUILTIN` is never used.

### 6.8 Brown-out handling

- [ ] The reset flags are read and cleared at boot and reported in status byte 14.
- [ ] `bootTrace` lives in `.noinit` with magic 0x54524143, phase, `brownOutRun`, culprits, `gasOn` and `fails[3]`. It is valid from `brownOutBackOff` onward.
- [ ] **Phases:**
  - PHASE_TX runs from EV_TXSTART to EV_RXSTART, EV_TXCOMPLETE or EV_JOIN_TXCOMPLETE.
  - RAIL_A and RAIL_B are set while a header switches on and is used.
  - `gasOn` is set while the heater runs.
- [ ] **Culprit pinning:** 3 brown-outs in a row pinned on the same part leave that part off.
  - It comes back after the hourly retry. That retry is a software reset after `SENSOR_RETRY_MS`, done only when `sleepPending && !lmicTxBusy()`.
  - A power-on or a flash clears everything.
- [ ] **Back-off:**
  - An unexplained brown-out run rests 30 × 2^(run−1) s, at most 480 s.
  - An explained one rests once for 30 s.
  - The rest is in power-down and comes before anything draws current.
  - The run is cleared after 3 good uplinks.
- [ ] **`learnFromBrownOut`:** BORF without PORF, with the previous phase TX, lowers the cap by 2 dB (to a minimum of 2 dBm), counts `brownOuts`, and saves.
- [ ] The WDT is 8 s, kicked in `loop()` and on every wake.

### 6.9 EEPROM

- [ ] The settings live at address 0: magic 0x4E4F4431, `txPowerMax`, `txPowerCap`, `brownOuts`, `devNonce`.
- [ ] The validity rules of L494-509 apply.
- [ ] Only changed bytes are written.

### 6.10 DEBUG

- [ ] With DEBUG 1: Serial at 115200 and every existing log line. Their text is used for bench checks, for example "Sleeping N ms until the slot", "Sleep clock: one PIT tick = N us", "TDMA sync: slot", "Brown-out reset N in a row: sleeping N s", "ENS160 heated N s", "EV_TXCOMPLETE" and "!! MISSED". `Serial.flush` runs before every sleep and reset.
- [ ] With DEBUG 0: no serial output, and PA0/PA1 input-disabled. All other behaviour, timing and packets are identical.

---

## 7. Open questions (only the user can answer)

- **Q1.** Which window do the TDMA downlinks arrive in, what is ChirpStack's RX2 data rate, and are the downlinks confirmed?
  - None of this is in the repo.
  - It decides whether the uplink cycle costs 63 J/day (RX1) or 230 J/day (RX2 at SF12).
  - Check V1 answers it on the bench.
- **Q2.** Does the gas reading need about 30 s of heating, or would about 10 s before the reply (F11) do? The 30 s reading is already sent with warm-up status. The difference is 1.9 J per task.
- **Q3.** How many gas and T/RH tasks does task-service-tdma actually send a day (A6)?
- **Q4.** May R9-R12 be removed, or moved to VCC_SENS, on the rev-2 boards (F1)? Do both breakouts have their own pull-ups?
- **Q5.** Is the 30 s cadence fixed for deployment (F12)?

---

## 8. Other observations (not energy; for the implementer and reviewer)

- **Gas-reply retry sends "absent".** If `LMIC_setTxData2` fails on a gas reply, the retry 1 s later (L1053-1054) calls `readTask` again. `gasStop()` has already run (L891), so the retried gas reply carries ENS_ABSENT, eCO2 400.
- **Join power comment is wrong.** The comment at L1092-1093 says joins go at 16 dBm. LMIC actually picks min(14 dBm band, 16) = 14 dBm (lmic.c:2700) before the cap.
- **Data is forced to SF7 even after a weak join.** After a join that only succeeded at SF8-SF12, data still goes at SF7 (L1082). With LinkCheck off the node never notices that it is no longer heard, and it never rejoins.
- **Forced uplinks break the TDMA plan.** Extra LMIC uplinks (S12) go out about 7 s after the data uplink, which is inside another node's slot.
- **The idle tail does not guard against drift.** The 1-2 s idle tail in `sleepUntil` is not protection against ULP drift (S4). Real-time wake error is drift × sleep length with any PIT period, and the server's correction absorbs it.
