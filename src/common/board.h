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
