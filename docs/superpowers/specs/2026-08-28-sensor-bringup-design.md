# Sensor Bring-up Firmware — Design (sub-project 1)

**Date:** 2026-08-28
**Status:** approved in chat
**Scope:** first firmware slice for the custom ATmega4809 EH sensor node: verify wiring, load switch, I2C bus, SHT41 and ENS160. No LoRaWAN yet.

## Context

The full node firmware (MCCI LMIC Class A, 60 s heartbeat, one task at a time, power-down sleep) is designed separately. This sub-project lays the PlatformIO scaffolding and the sensor layer that the full firmware will reuse unchanged.

Hardware today: custom PCB, ATmega4809-QFN48, powered from a bench supply on the 3V3 rail (no PMIC / supercap / solar yet). Sensors are generic SHT41 and ENS160 breakout modules, both on the shared I2C bus, both powered from `VCC_SENS` (MIC94069 load switch, enable = `MIC_ENA`).

## Pin map (from PCB netlist, `sensor-nodes-hardware/sensor-node-json.json`)

| Net | Port pin | Role |
|---|---|---|
| MOSI / MISO / SCK / NSS | PA4 / PA5 / PA6 / PA7 | SPI0 default — SX1276 (later) |
| SXRST / DIO0 / DIO1 / DIO2 | PF3 / PF2 / PF4 / PF5 | SX1276 (later) |
| SDA / SCL | PA2 / PA3 | TWI0 default — sensors |
| TX0 / RX0 | PA0 / PA1 | USART0 default — debug serial |
| MIC_ENA | PD6 | load switch enable (active high → `VCC_SENS` on) |
| LED1 | PD7 | status LED (through 1 k) |
| CO_ANLG | PD5 | unused |
| A0–A4 header | PD0–PD4 | spare |

All peripherals are on MegaCoreX default pin muxes; no `swap()` calls. Code uses MegaCoreX `PIN_Pxn` macros, never Arduino D-numbers.

## Build system

PlatformIO, `atmelmegaavr` platform, `board = ATmega4809`, MegaCoreX Arduino core, 16 MHz internal oscillator, `upload_protocol = jtag2updi`, monitor 115200 baud. `upload_port` left commented for auto-detect.

One `[env]` base plus one env per app. Apps are selected with `build_src_filter`:

```
platformio.ini
src/common/board.h                   pin definitions + boardInit()
src/common/sensors/Sht41.{h,cpp}     wrapper around Sensirion arduino-i2c-sht4x
src/common/sensors/Ens160.{h,cpp}    wrapper around SparkFun ENS160 library
src/common/SensorManager.{h,cpp}     rail power control + owns both sensors
src/apps/sensor_test/main.cpp        this sub-project's app
```

Libraries pinned by exact version in `platformio.ini`: `sensirion/Sensirion I2C SHT4x@1.1.2` (official, pulls `Sensirion Core`) and `sparkfun/SparkFun Indoor Air Quality Sensor - ENS160@1.1.0` (chosen over the ScioSense v2 library for its smaller footprint and explicit `begin(address)` / validity-flag API).

## Modules

### `board.h`
- `constexpr` pin aliases: `PIN_MIC_ENA`, `PIN_LED`, `PIN_SX_NSS`, `PIN_SX_RST`, `PIN_SX_DIO0/1/2`.
- `void boardInit()` — sets LED and MIC_ENA as outputs (both low), starts `Serial` at 115200, starts `Wire`.

### `Sht41`
- `bool begin()` — soft reset + serial-number read to confirm presence at `0x44`.
- `bool read(float& tempC, float& rh)` — high-precision single-shot measurement; returns `false` on I2C/CRC error.
- No heater use.

### `Ens160`
- `bool begin()` — tries `0x53` then `0x52`; verifies part ID; sets standard operating mode. Stores the address that answered.
- `bool read(Reading& r)` — fills `eco2_ppm`, `tvoc_ppb`, `aqi_uba`, `status` where `status` ∈ {`NORMAL`, `WARMUP`, `STARTUP`, `INVALID`, `ERROR`} from the device's validity flag.
- `uint8_t address()` — which address it found.

### `SensorManager`
- `void powerOn()` / `void powerOff()` / `bool isPowered()` — drives `MIC_ENA`; `powerOn()` waits a fixed settle delay (≈50 ms) before returning.
- `bool beginSensors()` — calls `begin()` on both; returns true if at least one succeeded; exposes per-sensor `ok` flags.
- `Sht41& sht41()`, `Ens160& ens160()` accessors.
- Reused as-is by the full firmware.

### `sensor_test` app
1. `boardInit()`; print banner with `__DATE__ __TIME__`; blink LED 3×.
2. `powerOn()`; run an I2C scan (addresses 0x08–0x77), print each ACKing address. Expected: `0x44`, and `0x52` or `0x53`.
3. `beginSensors()`; print which sensor initialised and at what address.
4. Every 2 s: read both, print one line:
   `t=12.3s | SHT41: 24.51 C 41.2 %RH | ENS160: eCO2=412 ppm TVOC=18 ppb AQI=1 status=WARMUP`
   A sensor that failed `begin()` or `read()` prints `--` in its slot rather than stopping the loop. LED toggles each cycle.
5. Serial commands (single characters): `p` toggle rail power (on power-up, sensors are re-initialised); `s` re-run the I2C scan; `?` help.
6. Rail stays ON by default so the ENS160 can complete its ~3 min warm-up.

## Error handling
- Any sensor failure is reported and retried every cycle; the app never halts.
- Power-off then power-on re-runs `beginSensors()`.

## Verification
- `pio run -e sensor_test` compiles cleanly here; flash and RAM usage recorded in the build output.
- On hardware: scan shows both addresses; SHT41 values plausible (room temp / humidity); ENS160 status progresses `INITIAL_STARTUP`/`WARMUP` → `NORMAL` within ~3 min; `p` removes the ENS160 (`0x52`/`0x53`) from the bus and restores it; the SHT41 may stay visible because the I2C pull-ups back-power it.

## Out of scope
LoRaWAN, sleep, energy model, payload codec, task execution — all in the full-firmware design.
