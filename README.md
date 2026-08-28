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

The sensor rail is powered on at boot. The ENS160 reports `status=WARMUP` for roughly the first 3 minutes after power-up (and `STARTUP` for up to an hour on a brand-new sensor) — this is normal; readings become `NORMAL` on their own.

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
