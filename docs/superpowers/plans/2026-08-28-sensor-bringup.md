# Sensor Bring-up Firmware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A PlatformIO firmware for the custom ATmega4809 sensor node that powers the sensor rail through the load switch, scans the I2C bus, and prints SHT41 (temp/RH) and ENS160 (eCO2/TVOC/AQI/validity) readings over UART every 2 s, with serial commands to toggle rail power and re-scan.

**Architecture:** One PlatformIO project with a shared `src/common/` layer (board pins, sensor wrappers, `SensorManager`) and per-app entry points under `src/apps/<app>/main.cpp` selected by `build_src_filter`. The sensor layer is written so the future LoRaWAN firmware reuses it unchanged. Pure logic (ENS160 status mapping) lives in an Arduino-free header and is unit-tested on the host.

**Tech Stack:** PlatformIO 6.1.19 · `atmelmegaavr` platform · MegaCoreX Arduino core (board `ATmega4809`, variant `48pin-standard`, 16 MHz internal osc) · jtag2updi upload · `sensirion/Sensirion I2C SHT4x@1.1.2` · `sparkfun/SparkFun Indoor Air Quality Sensor - ENS160@1.1.0` · Unity (native tests, host g++ 14.2 via MSYS2).

**Spec:** `docs/superpowers/specs/2026-08-28-sensor-bringup-design.md`

## Global Constraints

- PlatformIO executable is NOT on PATH. Always invoke it as `~/.platformio/penv/Scripts/pio.exe` (Git Bash: `"$HOME/.platformio/penv/Scripts/pio.exe"`).
- Board: `platform = atmelmegaavr`, `board = ATmega4809`, `framework = arduino`, `board_build.f_cpu = 16000000L`, `board_hardware.oscillator = internal`, `board_build.variant = 48pin-standard`, `upload_protocol = jtag2updi`, `monitor_speed = 115200`.
- Libraries pinned exactly: `sensirion/Sensirion I2C SHT4x@1.1.2`, `sparkfun/SparkFun Indoor Air Quality Sensor - ENS160@1.1.0`.
- Pins are referenced ONLY via MegaCoreX `PIN_Pxn` macros through `src/common/board.h`. Never Arduino D-numbers. **Never use `LED_BUILTIN`** — MegaCoreX maps it to PA7, which is the SX1276 `NSS` on this PCB.
- Pin map (from PCB netlist): MIC_ENA=PD6, LED=PD7, SDA=PA2, SCL=PA3, TX0=PA0, RX0=PA1, SX NSS=PA7, SX RST=PF3, SX DIO0=PF2, DIO1=PF4, DIO2=PF5, CO_ANLG=PD5 (unused).
- I2C addresses: SHT41 `0x44`; ENS160 `0x53` (try first) or `0x52`.
- The app never halts on a sensor error; it reports and retries next cycle.
- Sensor rail is ON by default so the ENS160 can finish its ~3 min warm-up.
- Every task ends with `pio run -e sensor_test` succeeding; report Flash/RAM numbers from the build output.
- Hardware verification steps require the user to flash and watch the monitor; the executor records what the user reports, never invents results.

---

### Task 1: PlatformIO scaffold, board pins, blink + banner

**Files:**
- Create: `platformio.ini`
- Create: `.gitignore`
- Create: `src/common/board.h`
- Create: `src/common/board.cpp`
- Create: `src/apps/sensor_test/main.cpp`

**Interfaces:**
- Consumes: nothing.
- Produces: namespace `board` with `constexpr uint8_t PIN_MIC_ENA, PIN_LED, PIN_SX_NSS, PIN_SX_RST, PIN_SX_DIO0, PIN_SX_DIO1, PIN_SX_DIO2`, `constexpr uint32_t SERIAL_BAUD`, and `void board::init()` (LED+MIC_ENA outputs LOW, SX NSS output HIGH, `Serial.begin(SERIAL_BAUD)`, `Wire.begin()`).

- [ ] **Step 1: Create `platformio.ini`**

```ini
; SDP EH sensor node firmware — PlatformIO project
; Build:   pio run -e sensor_test
; Upload:  pio run -e sensor_test -t upload      (JTAG2UPDI programmer on auto-detected COM port)
; Monitor: pio device monitor
; Tests:   pio test -e native

[platformio]
default_envs = sensor_test

; ---- shared settings for every ATmega4809 target -------------------------
[avr_base]
platform = atmelmegaavr
board = ATmega4809
framework = arduino
board_build.f_cpu = 16000000L
board_hardware.oscillator = internal
board_build.variant = 48pin-standard
upload_protocol = jtag2updi
; upload_port = COM5            ; uncomment + set if auto-detect picks the wrong port
monitor_speed = 115200
build_flags = -Wall -Wextra
lib_deps =
    sensirion/Sensirion I2C SHT4x@1.1.2
    sparkfun/SparkFun Indoor Air Quality Sensor - ENS160@1.1.0

; ---- app: sensor bring-up test ------------------------------------------
[env:sensor_test]
extends = avr_base
build_src_filter = +<common/> +<apps/sensor_test/>

; ---- host unit tests (pure logic only, no Arduino) -----------------------
[env:native]
platform = native
build_flags = -std=c++17 -I src
build_src_filter = -<*>
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.pio/
.vscode/.browse.c_cpp.db*
.vscode/c_cpp_properties.json
.vscode/launch.json
.vscode/ipch
*.pyc
```

- [ ] **Step 3: Create `src/common/board.h`**

```cpp
// Board definition for the SDP EH sensor node (custom ATmega4809 PCB, rev 1.0).
// Pin assignments come from the PCB netlist (sensor-nodes-hardware/sensor-node-json.json).
// Always reference pins through these constants; never use Arduino D-numbers or LED_BUILTIN
// (MegaCoreX maps LED_BUILTIN to PA7, which is the SX1276 NSS line on this board).
#pragma once
#include <Arduino.h>

namespace board {

// Power / indication
constexpr uint8_t PIN_MIC_ENA = PIN_PD6;  // MIC94069 load switch enable: HIGH = VCC_SENS on
constexpr uint8_t PIN_LED     = PIN_PD7;  // LED1 through R1 (1 k), active high

// SX1276 LoRa transceiver (SPI0 on PA4/PA5/PA6 default mux) — defined now, used by later apps
constexpr uint8_t PIN_SX_NSS  = PIN_PA7;
constexpr uint8_t PIN_SX_RST  = PIN_PF3;
constexpr uint8_t PIN_SX_DIO0 = PIN_PF2;
constexpr uint8_t PIN_SX_DIO1 = PIN_PF4;
constexpr uint8_t PIN_SX_DIO2 = PIN_PF5;

// I2C (TWI0 default mux PA2/PA3) and UART (USART0 default mux PA0/PA1) need no pin constants:
// Wire and Serial use them by default on the 48pin-standard variant.

constexpr uint32_t SERIAL_BAUD = 115200;

// Configure GPIO directions to a safe state, start Serial and Wire.
// Leaves the sensor rail OFF and the SX1276 deselected.
void init();

}  // namespace board
```

- [ ] **Step 4: Create `src/common/board.cpp`**

```cpp
#include "board.h"
#include <Wire.h>

namespace board {

void init() {
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    pinMode(PIN_MIC_ENA, OUTPUT);
    digitalWrite(PIN_MIC_ENA, LOW);   // sensor rail off until SensorManager::powerOn()

    pinMode(PIN_SX_NSS, OUTPUT);
    digitalWrite(PIN_SX_NSS, HIGH);   // keep the radio off the SPI bus
    pinMode(PIN_SX_RST, INPUT);       // leave SX1276 reset floating (internal pull-up) for now

    Serial.begin(SERIAL_BAUD);
    Wire.begin();
}

}  // namespace board
```

- [ ] **Step 5: Create `src/apps/sensor_test/main.cpp` (banner + blink only for now)**

```cpp
// sensor_test: bring-up firmware for the sensor rail, I2C bus, SHT41 and ENS160.
#include <Arduino.h>
#include "common/board.h"

static void blink(uint8_t times, uint16_t periodMs) {
    for (uint8_t i = 0; i < times; ++i) {
        digitalWrite(board::PIN_LED, HIGH);
        delay(periodMs / 2);
        digitalWrite(board::PIN_LED, LOW);
        delay(periodMs / 2);
    }
}

void setup() {
    board::init();
    delay(200);  // let the serial monitor attach
    Serial.println();
    Serial.println(F("=== SDP EH sensor node: sensor_test ==="));
    Serial.print(F("build: ")); Serial.print(F(__DATE__)); Serial.print(' '); Serial.println(F(__TIME__));
    blink(3, 200);
}

void loop() {
    digitalWrite(board::PIN_LED, HIGH);
    delay(500);
    digitalWrite(board::PIN_LED, LOW);
    delay(500);
}
```

- [ ] **Step 6: Build**

Run: `"$HOME/.platformio/penv/Scripts/pio.exe" run -e sensor_test`
Expected: `[SUCCESS]`, with a `RAM:` and `Flash:` line. Record both numbers.

- [ ] **Step 7: Hardware check (user)**

Ask the user to run `pio run -e sensor_test -t upload` then `pio device monitor`. Expected: banner with build date/time, three fast blinks, then a 1 Hz blink on LED1. If the upload fails with a port error, uncomment `upload_port` in `platformio.ini` and set it to the JTAG2UPDI COM port.

- [ ] **Step 8: Commit**

```bash
git add platformio.ini .gitignore src/common/board.h src/common/board.cpp src/apps/sensor_test/main.cpp
git commit -m "feat: PlatformIO scaffold, board pin map, blink+banner test app"
```

---

### Task 2: Sensor rail power control and I2C bus scan

**Files:**
- Create: `src/common/I2cScan.h`
- Create: `src/common/I2cScan.cpp`
- Create: `src/common/SensorManager.h`
- Create: `src/common/SensorManager.cpp`
- Modify: `src/apps/sensor_test/main.cpp`

**Interfaces:**
- Consumes: `board::PIN_MIC_ENA`, `board::PIN_LED` from Task 1.
- Produces:
  - `uint8_t i2cScan(Print& out)` — prints every ACKing 7-bit address in `0x08..0x77` as `  found 0x44`, returns the count, prints `  (no devices)` when zero.
  - `class SensorManager` with `void powerOn()`, `void powerOff()`, `bool isPowered() const`. (Sensor members are added in Tasks 3 and 4; this task creates the class with only power control so it compiles standalone.)

- [ ] **Step 1: Create `src/common/I2cScan.h`**

```cpp
#pragma once
#include <Arduino.h>

// Probe every 7-bit I2C address from 0x08 to 0x77 on Wire.
// Prints one line per responding device to `out` and returns how many responded.
uint8_t i2cScan(Print& out);
```

- [ ] **Step 2: Create `src/common/I2cScan.cpp`**

```cpp
#include "I2cScan.h"
#include <Wire.h>

uint8_t i2cScan(Print& out) {
    uint8_t found = 0;
    for (uint8_t addr = 0x08; addr <= 0x77; ++addr) {
        Wire.beginTransmission(addr);
        const uint8_t err = Wire.endTransmission();
        if (err == 0) {
            out.print(F("  found 0x"));
            if (addr < 0x10) out.print('0');
            out.println(addr, HEX);
            ++found;
        }
    }
    if (found == 0) out.println(F("  (no devices)"));
    return found;
}
```

- [ ] **Step 3: Create `src/common/SensorManager.h` (power control only)**

```cpp
// Owns the load-switched sensor rail (VCC_SENS) and, in later tasks, the sensor drivers.
// Reused unchanged by the full node firmware.
#pragma once
#include <Arduino.h>

class SensorManager {
public:
    // Time to wait after enabling VCC_SENS before touching the sensors.
    static constexpr uint16_t RAIL_SETTLE_MS = 50;

    void powerOn();            // enable MIC94069, wait RAIL_SETTLE_MS
    void powerOff();           // disable MIC94069
    bool isPowered() const { return _powered; }

private:
    bool _powered = false;
};
```

- [ ] **Step 4: Create `src/common/SensorManager.cpp`**

```cpp
#include "SensorManager.h"
#include "board.h"

void SensorManager::powerOn() {
    digitalWrite(board::PIN_MIC_ENA, HIGH);
    delay(RAIL_SETTLE_MS);
    _powered = true;
}

void SensorManager::powerOff() {
    digitalWrite(board::PIN_MIC_ENA, LOW);
    _powered = false;
}
```

- [ ] **Step 5: Update `src/apps/sensor_test/main.cpp` to power the rail and scan**

Replace the whole file with:

```cpp
// sensor_test: bring-up firmware for the sensor rail, I2C bus, SHT41 and ENS160.
#include <Arduino.h>
#include "common/board.h"
#include "common/I2cScan.h"
#include "common/SensorManager.h"

static SensorManager sensors;

static void blink(uint8_t times, uint16_t periodMs) {
    for (uint8_t i = 0; i < times; ++i) {
        digitalWrite(board::PIN_LED, HIGH);
        delay(periodMs / 2);
        digitalWrite(board::PIN_LED, LOW);
        delay(periodMs / 2);
    }
}

static void runScan() {
    Serial.println(F("I2C scan:"));
    const uint8_t n = i2cScan(Serial);
    Serial.print(F("  -> ")); Serial.print(n); Serial.println(F(" device(s)"));
}

void setup() {
    board::init();
    delay(200);  // let the serial monitor attach
    Serial.println();
    Serial.println(F("=== SDP EH sensor node: sensor_test ==="));
    Serial.print(F("build: ")); Serial.print(F(__DATE__)); Serial.print(' '); Serial.println(F(__TIME__));
    blink(3, 200);

    Serial.println(F("Sensor rail: ON"));
    sensors.powerOn();
    runScan();
}

void loop() {
    digitalWrite(board::PIN_LED, HIGH);
    delay(500);
    digitalWrite(board::PIN_LED, LOW);
    delay(500);
}
```

- [ ] **Step 6: Build**

Run: `"$HOME/.platformio/penv/Scripts/pio.exe" run -e sensor_test`
Expected: `[SUCCESS]`. Record Flash/RAM.

- [ ] **Step 7: Hardware check (user)**

Flash and open the monitor. Expected after the banner:
```
Sensor rail: ON
I2C scan:
  found 0x44
  found 0x53
  -> 2 device(s)
```
(`0x52` instead of `0x53` is fine.) If `0x44` is missing → SHT41 wiring/power; if `0x52/0x53` missing → ENS160 SDA/SCL jumper or power; if `(no devices)` → check `VCC_SENS` with a meter (should be ~3.3 V) and the SDA/SCL pull-ups.

- [ ] **Step 8: Commit**

```bash
git add src/common/I2cScan.h src/common/I2cScan.cpp src/common/SensorManager.h src/common/SensorManager.cpp src/apps/sensor_test/main.cpp
git commit -m "feat: sensor rail power control and I2C bus scan"
```

---

### Task 3: SHT41 driver wrapper and periodic temperature/humidity readout

**Files:**
- Create: `src/common/sensors/Sht41.h`
- Create: `src/common/sensors/Sht41.cpp`
- Modify: `src/common/SensorManager.h`
- Modify: `src/common/SensorManager.cpp`
- Modify: `src/apps/sensor_test/main.cpp`

**Interfaces:**
- Consumes: `SensorManager::powerOn/powerOff/isPowered` from Task 2.
- Produces:
  - `class Sht41` with `bool begin()`, `bool read(float& tempC, float& rh)`, `uint32_t serialNumber() const`, `bool ok() const`.
  - `SensorManager` gains `bool beginSensors()`, `bool sht41Ok() const`, `Sht41& sht41()`; `powerOff()` now clears the ok flags.

- [ ] **Step 1: Create `src/common/sensors/Sht41.h`**

```cpp
// Thin wrapper over the Sensirion SHT4x driver for the SHT41 at 0x44.
#pragma once
#include <Arduino.h>
#include <SensirionI2cSht4x.h>

class Sht41 {
public:
    static constexpr uint8_t I2C_ADDRESS = SHT41_I2C_ADDR_44;

    // Soft-reset the sensor and read its serial number to prove it is present.
    // Returns true if the sensor answered. Safe to call again after a power cycle.
    bool begin();

    // Single-shot high-precision measurement (~10 ms). Returns false on I2C/CRC error.
    bool read(float& tempC, float& rh);

    bool ok() const { return _ok; }
    uint32_t serialNumber() const { return _serial; }

private:
    SensirionI2cSht4x _dev;
    uint32_t _serial = 0;
    bool _ok = false;
};
```

- [ ] **Step 2: Create `src/common/sensors/Sht41.cpp`**

```cpp
#include "Sht41.h"
#include <Wire.h>

bool Sht41::begin() {
    _ok = false;
    _serial = 0;
    _dev.begin(Wire, I2C_ADDRESS);
    if (_dev.softReset() != 0) return false;
    delay(2);  // datasheet: soft reset completes within 1 ms
    if (_dev.serialNumber(_serial) != 0) return false;
    _ok = true;
    return true;
}

bool Sht41::read(float& tempC, float& rh) {
    if (!_ok) return false;
    return _dev.measureHighPrecision(tempC, rh) == 0;
}
```

- [ ] **Step 3: Extend `src/common/SensorManager.h`**

Replace the file with:

```cpp
// Owns the load-switched sensor rail (VCC_SENS) and the sensor drivers behind it.
// Reused unchanged by the full node firmware.
#pragma once
#include <Arduino.h>
#include "sensors/Sht41.h"

class SensorManager {
public:
    // Time to wait after enabling VCC_SENS before touching the sensors.
    static constexpr uint16_t RAIL_SETTLE_MS = 50;

    void powerOn();            // enable MIC94069, wait RAIL_SETTLE_MS
    void powerOff();           // disable MIC94069; sensors must be re-begun after powerOn()
    bool isPowered() const { return _powered; }

    // Initialise every sensor on the rail. Returns true if at least one answered.
    bool beginSensors();
    bool sht41Ok() const { return _sht.ok(); }

    Sht41& sht41() { return _sht; }

private:
    Sht41 _sht;
    bool _powered = false;
};
```

- [ ] **Step 4: Extend `src/common/SensorManager.cpp`**

Replace the file with:

```cpp
#include "SensorManager.h"
#include "board.h"

void SensorManager::powerOn() {
    digitalWrite(board::PIN_MIC_ENA, HIGH);
    delay(RAIL_SETTLE_MS);
    _powered = true;
}

void SensorManager::powerOff() {
    digitalWrite(board::PIN_MIC_ENA, LOW);
    _powered = false;
    _sht = Sht41();   // drop stale "ok" state; begin() again after powerOn()
}

bool SensorManager::beginSensors() {
    if (!_powered) return false;
    const bool shtOk = _sht.begin();
    return shtOk;
}
```

- [ ] **Step 5: Update `src/apps/sensor_test/main.cpp` — init SHT41 and print a reading every 2 s**

Replace the file with:

```cpp
// sensor_test: bring-up firmware for the sensor rail, I2C bus, SHT41 and ENS160.
#include <Arduino.h>
#include "common/board.h"
#include "common/I2cScan.h"
#include "common/SensorManager.h"

static constexpr uint32_t READ_PERIOD_MS = 2000;

static SensorManager sensors;
static uint32_t lastReadMs = 0;

static void blink(uint8_t times, uint16_t periodMs) {
    for (uint8_t i = 0; i < times; ++i) {
        digitalWrite(board::PIN_LED, HIGH);
        delay(periodMs / 2);
        digitalWrite(board::PIN_LED, LOW);
        delay(periodMs / 2);
    }
}

static void runScan() {
    Serial.println(F("I2C scan:"));
    const uint8_t n = i2cScan(Serial);
    Serial.print(F("  -> ")); Serial.print(n); Serial.println(F(" device(s)"));
}

static void initSensors() {
    sensors.beginSensors();
    Serial.print(F("SHT41:  "));
    if (sensors.sht41Ok()) {
        Serial.print(F("OK  serial=0x")); Serial.println(sensors.sht41().serialNumber(), HEX);
    } else {
        Serial.println(F("NOT FOUND"));
    }
}

static void printReadings() {
    Serial.print(F("t=")); Serial.print(millis() / 1000.0f, 1); Serial.print(F("s | SHT41: "));
    float t = 0, h = 0;
    if (sensors.sht41().read(t, h)) {
        Serial.print(t, 2); Serial.print(F(" C ")); Serial.print(h, 1); Serial.print(F(" %RH"));
    } else {
        Serial.print(F("--"));
    }
    Serial.println();
}

void setup() {
    board::init();
    delay(200);  // let the serial monitor attach
    Serial.println();
    Serial.println(F("=== SDP EH sensor node: sensor_test ==="));
    Serial.print(F("build: ")); Serial.print(F(__DATE__)); Serial.print(' '); Serial.println(F(__TIME__));
    blink(3, 200);

    Serial.println(F("Sensor rail: ON"));
    sensors.powerOn();
    runScan();
    initSensors();
    lastReadMs = millis();
}

void loop() {
    const uint32_t now = millis();
    if (now - lastReadMs >= READ_PERIOD_MS) {
        lastReadMs = now;
        digitalWrite(board::PIN_LED, !digitalRead(board::PIN_LED));
        printReadings();
    }
}
```

- [ ] **Step 6: Build**

Run: `"$HOME/.platformio/penv/Scripts/pio.exe" run -e sensor_test`
Expected: `[SUCCESS]`. Record Flash/RAM.

- [ ] **Step 7: Hardware check (user)**

Flash and monitor. Expected:
```
SHT41:  OK  serial=0x1234ABCD
t=2.4s | SHT41: 24.51 C 41.2 %RH
t=4.4s | SHT41: 24.53 C 41.1 %RH
```
Breathe on the sensor: humidity should jump by tens of %RH within a few readings and decay back. If `NOT FOUND` while the scan showed `0x44`, that indicates a CRC/bus-speed issue — report the exact output.

- [ ] **Step 8: Commit**

```bash
git add src/common/sensors/Sht41.h src/common/sensors/Sht41.cpp src/common/SensorManager.h src/common/SensorManager.cpp src/apps/sensor_test/main.cpp
git commit -m "feat: SHT41 wrapper and periodic temperature/humidity readout"
```

---

### Task 4: ENS160 status mapping (host-tested) and ENS160 driver wrapper

**Files:**
- Create: `src/common/sensors/Ens160Status.h`
- Create: `test/test_ens160_status/test_main.cpp`
- Create: `src/common/sensors/Ens160.h`
- Create: `src/common/sensors/Ens160.cpp`
- Modify: `src/common/SensorManager.h`
- Modify: `src/common/SensorManager.cpp`
- Modify: `src/apps/sensor_test/main.cpp`

**Interfaces:**
- Consumes: `SensorManager` from Task 3; SparkFun `SparkFun_ENS160` (`begin(TwoWire&, uint8_t addr)`, `setOperatingMode(uint8_t)`, `getFlags()` → 0..3 or 0xFF, `getECO2()`, `getTVOC()`, `getAQI()`), constants `ENS160_ADDRESS_HIGH` (0x53), `ENS160_ADDRESS_LOW` (0x52), `SFE_ENS160_RESET`, `SFE_ENS160_STANDARD`.
- Produces:
  - `enum class Ens160Status : uint8_t { Normal = 0, Warmup = 1, InitialStartup = 2, Invalid = 3, Error = 0xFF }`
  - `Ens160Status ens160StatusFromFlags(uint8_t flags)`, `const char* ens160StatusName(Ens160Status s)`, `bool ens160StatusIsValid(Ens160Status s)` — pure, Arduino-free.
  - `struct Ens160Reading { uint16_t eco2_ppm; uint16_t tvoc_ppb; uint8_t aqi_uba; Ens160Status status; }`
  - `class Ens160` with `bool begin()`, `bool read(Ens160Reading& r)`, `bool ok() const`, `uint8_t address() const`.
  - `SensorManager` gains `bool ens160Ok() const`, `Ens160& ens160()`.

- [ ] **Step 1: Write the failing host test `test/test_ens160_status/test_main.cpp`**

```cpp
#include <unity.h>
#include <cstring>
#include "common/sensors/Ens160Status.h"

void setUp() {}
void tearDown() {}

static void test_flags_map_to_status() {
    TEST_ASSERT_EQUAL(Ens160Status::Normal,         ens160StatusFromFlags(0));
    TEST_ASSERT_EQUAL(Ens160Status::Warmup,         ens160StatusFromFlags(1));
    TEST_ASSERT_EQUAL(Ens160Status::InitialStartup, ens160StatusFromFlags(2));
    TEST_ASSERT_EQUAL(Ens160Status::Invalid,        ens160StatusFromFlags(3));
}

static void test_error_and_unknown_flags_map_to_error() {
    TEST_ASSERT_EQUAL(Ens160Status::Error, ens160StatusFromFlags(0xFF));
    TEST_ASSERT_EQUAL(Ens160Status::Error, ens160StatusFromFlags(4));
    TEST_ASSERT_EQUAL(Ens160Status::Error, ens160StatusFromFlags(200));
}

static void test_status_names() {
    TEST_ASSERT_EQUAL_STRING("NORMAL",  ens160StatusName(Ens160Status::Normal));
    TEST_ASSERT_EQUAL_STRING("WARMUP",  ens160StatusName(Ens160Status::Warmup));
    TEST_ASSERT_EQUAL_STRING("STARTUP", ens160StatusName(Ens160Status::InitialStartup));
    TEST_ASSERT_EQUAL_STRING("INVALID", ens160StatusName(Ens160Status::Invalid));
    TEST_ASSERT_EQUAL_STRING("ERROR",   ens160StatusName(Ens160Status::Error));
}

static void test_status_is_valid_only_when_normal() {
    TEST_ASSERT_TRUE (ens160StatusIsValid(Ens160Status::Normal));
    TEST_ASSERT_FALSE(ens160StatusIsValid(Ens160Status::Warmup));
    TEST_ASSERT_FALSE(ens160StatusIsValid(Ens160Status::InitialStartup));
    TEST_ASSERT_FALSE(ens160StatusIsValid(Ens160Status::Invalid));
    TEST_ASSERT_FALSE(ens160StatusIsValid(Ens160Status::Error));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_flags_map_to_status);
    RUN_TEST(test_error_and_unknown_flags_map_to_error);
    RUN_TEST(test_status_names);
    RUN_TEST(test_status_is_valid_only_when_normal);
    return UNITY_END();
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `"$HOME/.platformio/penv/Scripts/pio.exe" test -e native`
Expected: build error `Ens160Status.h: No such file or directory`.

- [ ] **Step 3: Create `src/common/sensors/Ens160Status.h` (pure, no Arduino include)**

```cpp
// ENS160 data-validity status, decoded from the DEVICE_STATUS register's VALIDITY_FLAG.
// Pure header: no Arduino dependency so it can be unit-tested on the host.
#pragma once
#include <stdint.h>

enum class Ens160Status : uint8_t {
    Normal         = 0,    // outputs valid
    Warmup         = 1,    // first ~3 min after power-up: outputs settling
    InitialStartup = 2,    // first 1 h of the sensor's life: outputs not trustworthy
    Invalid        = 3,    // sensor reports invalid output
    Error          = 0xFF  // I2C read failed or unknown code
};

inline Ens160Status ens160StatusFromFlags(uint8_t flags) {
    switch (flags) {
        case 0:  return Ens160Status::Normal;
        case 1:  return Ens160Status::Warmup;
        case 2:  return Ens160Status::InitialStartup;
        case 3:  return Ens160Status::Invalid;
        default: return Ens160Status::Error;
    }
}

inline const char* ens160StatusName(Ens160Status s) {
    switch (s) {
        case Ens160Status::Normal:         return "NORMAL";
        case Ens160Status::Warmup:         return "WARMUP";
        case Ens160Status::InitialStartup: return "STARTUP";
        case Ens160Status::Invalid:        return "INVALID";
        default:                           return "ERROR";
    }
}

inline bool ens160StatusIsValid(Ens160Status s) { return s == Ens160Status::Normal; }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `"$HOME/.platformio/penv/Scripts/pio.exe" test -e native`
Expected: `4 Tests 0 Failures 0 Ignored` / `[PASSED]`.

- [ ] **Step 5: Create `src/common/sensors/Ens160.h`**

```cpp
// Thin wrapper over the SparkFun ENS160 driver. Probes 0x53 then 0x52.
#pragma once
#include <Arduino.h>
#include <SparkFun_ENS160.h>
#include "Ens160Status.h"

struct Ens160Reading {
    uint16_t eco2_ppm = 0;
    uint16_t tvoc_ppb = 0;
    uint8_t  aqi_uba  = 0;   // 1 (excellent) .. 5 (unhealthy)
    Ens160Status status = Ens160Status::Error;
};

class Ens160 {
public:
    // Find the sensor (0x53, then 0x52), reset it and put it in STANDARD gas-sensing mode.
    // Returns true if found. Safe to call again after a power cycle.
    bool begin();

    // Read validity flag + eCO2/TVOC/AQI. Returns false if the sensor is absent or the
    // status register could not be read. Values are still filled in when status != Normal;
    // callers decide whether to trust them via ens160StatusIsValid(r.status).
    bool read(Ens160Reading& r);

    bool ok() const { return _ok; }
    uint8_t address() const { return _addr; }

private:
    static constexpr uint16_t RESET_SETTLE_MS = 100;
    SparkFun_ENS160 _dev;
    uint8_t _addr = 0;
    bool _ok = false;
};
```

- [ ] **Step 6: Create `src/common/sensors/Ens160.cpp`**

```cpp
#include "Ens160.h"
#include <Wire.h>

bool Ens160::begin() {
    _ok = false;
    _addr = 0;
    const uint8_t candidates[] = { ENS160_ADDRESS_HIGH, ENS160_ADDRESS_LOW };
    for (uint8_t addr : candidates) {
        if (_dev.begin(Wire, addr)) { _addr = addr; break; }
    }
    if (_addr == 0) return false;

    if (!_dev.setOperatingMode(SFE_ENS160_RESET)) return false;
    delay(RESET_SETTLE_MS);
    if (!_dev.setOperatingMode(SFE_ENS160_STANDARD)) return false;
    _ok = true;
    return true;
}

bool Ens160::read(Ens160Reading& r) {
    if (!_ok) return false;
    const uint8_t flags = _dev.getFlags();
    r.status = ens160StatusFromFlags(flags);
    if (r.status == Ens160Status::Error) return false;
    r.eco2_ppm = _dev.getECO2();
    r.tvoc_ppb = _dev.getTVOC();
    r.aqi_uba  = _dev.getAQI();
    return true;
}
```

- [ ] **Step 7: Extend `src/common/SensorManager.h`**

Replace the file with:

```cpp
// Owns the load-switched sensor rail (VCC_SENS) and the sensor drivers behind it.
// Reused unchanged by the full node firmware.
#pragma once
#include <Arduino.h>
#include "sensors/Sht41.h"
#include "sensors/Ens160.h"

class SensorManager {
public:
    // Time to wait after enabling VCC_SENS before touching the sensors.
    static constexpr uint16_t RAIL_SETTLE_MS = 50;

    void powerOn();            // enable MIC94069, wait RAIL_SETTLE_MS
    void powerOff();           // disable MIC94069; sensors must be re-begun after powerOn()
    bool isPowered() const { return _powered; }

    // Initialise every sensor on the rail. Returns true if at least one answered.
    bool beginSensors();
    bool sht41Ok() const  { return _sht.ok(); }
    bool ens160Ok() const { return _ens.ok(); }

    Sht41&  sht41()  { return _sht; }
    Ens160& ens160() { return _ens; }

private:
    Sht41  _sht;
    Ens160 _ens;
    bool _powered = false;
};
```

- [ ] **Step 8: Extend `src/common/SensorManager.cpp`**

Replace the file with:

```cpp
#include "SensorManager.h"
#include "board.h"

void SensorManager::powerOn() {
    digitalWrite(board::PIN_MIC_ENA, HIGH);
    delay(RAIL_SETTLE_MS);
    _powered = true;
}

void SensorManager::powerOff() {
    digitalWrite(board::PIN_MIC_ENA, LOW);
    _powered = false;
    _sht = Sht41();    // drop stale "ok" state; begin() again after powerOn()
    _ens = Ens160();
}

bool SensorManager::beginSensors() {
    if (!_powered) return false;
    const bool shtOk = _sht.begin();
    const bool ensOk = _ens.begin();
    return shtOk || ensOk;
}
```

- [ ] **Step 9: Update `src/apps/sensor_test/main.cpp` — init and print the ENS160 too**

Replace `initSensors()` and `printReadings()` with:

```cpp
static void initSensors() {
    sensors.beginSensors();
    Serial.print(F("SHT41:  "));
    if (sensors.sht41Ok()) {
        Serial.print(F("OK  serial=0x")); Serial.println(sensors.sht41().serialNumber(), HEX);
    } else {
        Serial.println(F("NOT FOUND"));
    }
    Serial.print(F("ENS160: "));
    if (sensors.ens160Ok()) {
        Serial.print(F("OK  addr=0x")); Serial.println(sensors.ens160().address(), HEX);
    } else {
        Serial.println(F("NOT FOUND"));
    }
}

static void printReadings() {
    Serial.print(F("t=")); Serial.print(millis() / 1000.0f, 1); Serial.print(F("s | SHT41: "));
    float t = 0, h = 0;
    if (sensors.sht41().read(t, h)) {
        Serial.print(t, 2); Serial.print(F(" C ")); Serial.print(h, 1); Serial.print(F(" %RH"));
    } else {
        Serial.print(F("--"));
    }

    Serial.print(F(" | ENS160: "));
    Ens160Reading r;
    if (sensors.ens160().read(r)) {
        Serial.print(F("eCO2=")); Serial.print(r.eco2_ppm); Serial.print(F(" ppm TVOC="));
        Serial.print(r.tvoc_ppb); Serial.print(F(" ppb AQI=")); Serial.print(r.aqi_uba);
        Serial.print(F(" status=")); Serial.print(ens160StatusName(r.status));
    } else {
        Serial.print(F("--"));
    }
    Serial.println();
}
```

- [ ] **Step 10: Build both environments**

Run: `"$HOME/.platformio/penv/Scripts/pio.exe" run -e sensor_test && "$HOME/.platformio/penv/Scripts/pio.exe" test -e native`
Expected: `[SUCCESS]` for `sensor_test` (record Flash/RAM) and `[PASSED]` for native.

- [ ] **Step 11: Hardware check (user)**

Flash and monitor. Expected:
```
SHT41:  OK  serial=0x1234ABCD
ENS160: OK  addr=0x53
t=2.5s | SHT41: 24.51 C 41.2 %RH | ENS160: eCO2=400 ppm TVOC=0 ppb AQI=1 status=WARMUP
...
t=185.1s | SHT41: 24.60 C 40.9 %RH | ENS160: eCO2=421 ppm TVOC=23 ppb AQI=1 status=NORMAL
```
`status` should go `WARMUP` → `NORMAL` within ~3 min (`STARTUP` on a brand-new sensor for up to an hour). Breathe on the ENS160 once `NORMAL`: eCO2/TVOC should spike.

- [ ] **Step 12: Commit**

```bash
git add src/common/sensors/Ens160Status.h test/test_ens160_status/test_main.cpp src/common/sensors/Ens160.h src/common/sensors/Ens160.cpp src/common/SensorManager.h src/common/SensorManager.cpp src/apps/sensor_test/main.cpp
git commit -m "feat: ENS160 wrapper with host-tested validity status mapping"
```

---

### Task 5: Serial commands (rail power toggle, rescan, help) and README

**Files:**
- Modify: `src/apps/sensor_test/main.cpp`
- Create: `README.md`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: the finished `sensor_test` app; project README.

- [ ] **Step 1: Add command handling to `src/apps/sensor_test/main.cpp`**

Add these functions above `setup()`:

```cpp
static void printHelp() {
    Serial.println(F("commands:  p = toggle sensor rail power   s = I2C scan   ? = help"));
}

static void handleCommand(char c) {
    switch (c) {
        case 'p':
            if (sensors.isPowered()) {
                sensors.powerOff();
                Serial.println(F("Sensor rail: OFF"));
            } else {
                Serial.println(F("Sensor rail: ON"));
                sensors.powerOn();
                initSensors();
            }
            break;
        case 's':
            runScan();
            break;
        case '?':
            printHelp();
            break;
        case '\r':
        case '\n':
        case ' ':
            break;  // ignore line endings from the terminal
        default:
            Serial.print(F("unknown command '")); Serial.print(c); Serial.println(F("' (try ?)"));
            break;
    }
}
```

In `setup()`, after `initSensors();` add `printHelp();`.

Replace `loop()` with:

```cpp
void loop() {
    while (Serial.available() > 0) {
        handleCommand(static_cast<char>(Serial.read()));
    }

    const uint32_t now = millis();
    if (now - lastReadMs >= READ_PERIOD_MS) {
        lastReadMs = now;
        digitalWrite(board::PIN_LED, !digitalRead(board::PIN_LED));
        if (sensors.isPowered()) {
            printReadings();
        } else {
            Serial.print(F("t=")); Serial.print(now / 1000.0f, 1); Serial.println(F("s | rail OFF"));
        }
    }
}
```

- [ ] **Step 2: Create `README.md`**

````markdown
# SDP EH Sensor Node Firmware

Firmware for the custom ATmega4809 energy-harvesting LoRaWAN sensor node
(senior design project). Hardware sources live in `sensor-nodes-hardware/`.

## Toolchain

- [PlatformIO Core](https://platformio.org/) (VS Code extension or CLI)
- JTAG2UPDI programmer on a USB serial port (auto-detected; pin it with `upload_port` in `platformio.ini` if needed)

```
pio run -e sensor_test              # build
pio run -e sensor_test -t upload    # flash over UPDI
pio device monitor                  # 115200 baud
pio test -e native                  # host unit tests
```

## Apps

| env | source | purpose |
|---|---|---|
| `sensor_test` | `src/apps/sensor_test/` | Bring-up: powers the sensor rail, scans I2C, prints SHT41 + ENS160 readings every 2 s. Serial commands: `p` toggle rail, `s` rescan, `?` help. |

Shared code (board pin map, sensor drivers, `SensorManager`) is in `src/common/` and is reused by every app.

## Pin map (PCB rev 1.0)

| Net | MCU pin | Use |
|---|---|---|
| MIC_ENA | PD6 | sensor rail load-switch enable |
| LED1 | PD7 | status LED |
| SDA / SCL | PA2 / PA3 | SHT41 (0x44) + ENS160 (0x53/0x52) |
| TX0 / RX0 | PA0 / PA1 | debug UART |
| NSS / RST / DIO0 / DIO1 / DIO2 | PA7 / PF3 / PF2 / PF4 / PF5 | SX1276 (SPI0 on PA4–PA6) |

Do not use `LED_BUILTIN` — MegaCoreX maps it to PA7, the radio's NSS.

## Design docs

- `docs/superpowers/specs/` — design specs
- `docs/superpowers/plans/` — implementation plans
````

- [ ] **Step 3: Build**

Run: `"$HOME/.platformio/penv/Scripts/pio.exe" run -e sensor_test`
Expected: `[SUCCESS]`. Record Flash/RAM.

- [ ] **Step 4: Hardware check (user) — full acceptance**

Flash and monitor, then:
1. Confirm banner, scan (`0x44` + `0x52/0x53`), both sensors `OK`, help line.
2. Readings every 2 s; ENS160 reaches `status=NORMAL` within ~3 min.
3. Send `p` → `Sensor rail: OFF`; lines show `rail OFF`. Wait at least 10 s, then send `s` → the scan must no longer list `0x52`/`0x53`; `0x44` MAY still appear (the SHT41 is back-powered through the I2C pull-ups on this PCB revision — expected, not a load-switch fault).
4. Wait at least 10 s after the rail went off, then send `p` → `Sensor rail: ON`, both sensors re-initialise, ENS160 goes back to `WARMUP`. Readings resume.
5. Send `x` → `unknown command 'x' (try ?)`.

- [ ] **Step 5: Commit**

```bash
git add src/apps/sensor_test/main.cpp README.md
git commit -m "feat: serial commands for rail power and rescan; project README"
```

---

## Self-review notes

- Spec coverage: pin map → T1; build system/layout → T1; `board.h` → T1; `Sht41` → T3; `Ens160` + status enum → T4; `SensorManager` power/begin/accessors → T2–T4; app steps 1–6 → T2 (banner, blink, scan), T3–T4 (readings), T5 (commands; rail-on default already in T2); error handling (never halts, re-init after power) → T3/T5; verification → each task's build + hardware step.
- Names used consistently across tasks: `board::PIN_MIC_ENA`, `board::PIN_LED`, `SensorManager::powerOn/powerOff/isPowered/beginSensors/sht41Ok/ens160Ok/sht41()/ens160()`, `Sht41::begin/read/ok/serialNumber`, `Ens160::begin/read/ok/address`, `Ens160Reading`, `ens160StatusFromFlags/ens160StatusName/ens160StatusIsValid`, `i2cScan(Print&)`.
- Deviation from spec: spec listed the status name `INITIAL_STARTUP`; plan uses `STARTUP` to keep the log line short, and adds `ERROR`. Spec updated to match.
