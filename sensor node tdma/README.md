# Sensor node firmware, TDMA version

TDMA variant of the PCB firmware in `sensor node to send/` (the ALOHA version, unchanged).
Same board, sensors, keys and build settings; what differs is when the node transmits and when the
sensors are powered.

**`TEST_IGNORE_ENERGY` is 1 in both sketches** (bench tests, 2026-10-28): the node answers every task
whatever its energy. Set it to 0 for real runs, so a task the node cannot afford is skipped.

## Radio: TDMA

- One uplink per 30 s frame, only at the start of the node's own slot (node 1: slot 0, node 2: slot 1,
  15 s apart), so the uplinks and the gateway's answers never overlap.
- The schedule comes in every TDMA downlink (fPort 20, 6 bytes): task command, slot index, slots per
  frame, frame length in seconds, and a slot correction in ms relative to the uplink it answers.
- A task is answered in the node's next slot.
- Every uplink ends with the node's energy, 0..200 units from the storage voltage:
  200 x (V^2 - 2.80^2) / (3.60^2 - 2.80^2), the AEM10330's cut-off and full levels (1 unit = 1.92 J
  for the 150 F store).

## Sensors: powered per task

- Both sensor headers are used: the SHT41 and the ENS160 are each found on J3 or J4 at boot, and the
  single TWI is moved to a sensor's header (Wire.swap) before every access.
- Nothing is powered between tasks. Status packets switch no sensor on and carry voltage and energy
  only (temperature / humidity sent as 0x7FFE "not measured", gas status 0xFC).
- Temperature / humidity task: the SHT41's header is switched on in the reply slot, read, switched off.
- Gas task: the ENS160's header is switched on as soon as the task arrives and heats until the reply
  slot one frame (30 s) later; that reading goes out with the ENS160's validity flag (warm-up until
  about 3 min, "first hour" while the sensor itself is new). Then it is switched off.
- Headers are switched on with a pulsed ramp (on-times 50 to 800 us in 5 us steps, 20 us off): a plain
  switch-on of the ENS160 board browned the node out every time. See `bench/sequence_test/RESULTS.md`.

## Brown-outs

- After a brown-out reset the node rests in power-down (30 s, doubling up to 8 min) before switching
  anything on, so the storage can recharge.
- A brown-out is pinned on what was going on: switching J3 on, switching J4 on, or the ENS160 heater.
  After 3 in a row that part stays off (the rest keeps working); an unexplained run of 3 starts the node
  without sensors. A power-on, a flash, or the hourly retry clears it.
- A brown-out during a transmission lowers the stored TX power cap by 2 dB (floor 2 dBm).

## Bench sketches (`bench/`)

- `sensor_test`: no LoRa, powers both headers and prints both sensors and the storage voltage every 2 s.
- `sequence_test`: tries power-up sequences over and over, survives its own brown-outs, and ranks them.

Server side (not in this repo): `task-service-tdma` (port 5002, 2 slots x 15 s) and the Node-RED tab
"Workflow 4 - TDMA". Workflow 3 (ALOHA) should be off for these nodes.

Build and flash exactly as the ALOHA sketches (MegaCoreX ATmega4809, 48 pin standard, internal 8 MHz,
BOD 2.6 V, EEPROM retained, JTAG2UPDI). Put the node's keys in `secrets.h` next to the sketch
(see `secrets.example.h`; secrets.h is kept out of git).
