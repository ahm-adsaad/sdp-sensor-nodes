# Sensor node firmware, TDMA version

TDMA variant of the PCB firmware in `sensor node to send/` (the ALOHA version, unchanged).
Same board, sensors, keys and build settings; what differs is when the node transmits and when the
sensors are powered.

Four sketch folders, `sensor_node_1_tdma` to `sensor_node_4_tdma`, one per board. They are the same
code; only the header comment and `NODE_NUMBER` differ (nodes 3 and 4, added 2026-11-09, have no
ALOHA version). The node number is the sensor number the server knows the board by (`num_to_eui`)
and picks the node's default slot (node N in slot N-1).

**`TEST_IGNORE_ENERGY` is 1 in all four sketches** (bench tests, 2026-10-28): the node answers every task
whatever its energy. Set it to 0 for real runs, so a task the node cannot afford is skipped.

## Radio: TDMA

- One uplink per 60 s frame, only at the start of the node's own slot (4 slots of 15 s: node 1 slot 0,
  node 2 slot 1, node 3 slot 2, node 4 slot 3), so the uplinks and the gateway's answers never overlap.
  `DEFAULT_SLOTS` (4) and `DEFAULT_SLOT_MS` (15000) are the free-run schedule until the first downlink
  and must match `TDMA_SLOTS` / `TDMA_SLOT_S` on the server, which then sets the real schedule.
- The schedule comes in every TDMA downlink (fPort 20, 6 bytes): task command, slot index, slots per
  frame, frame length in seconds, and a slot correction in ms relative to the uplink it answers.
- A task is answered in the node's next slot.
- Every uplink ends with the node's energy, 0..200 units from the storage voltage:
  200 x (V^2 - 2.80^2) / (3.60^2 - 2.80^2), the AEM10330's cut-off and full levels (1 unit = 1.92 J
  for the 150 F store).

## Sleep

- The node sleeps in power-down between frames, between join attempts and while LMIC waits out its
  duty cycle. It idles while a TX/RX cycle runs (uplink to the end of RX1 or RX2), where LMIC's
  receive windows need the 1 ms clock, for the last 1-3 s before each LMIC job, and while LMIC holds
  a frame past the node's slot.
- The sleep clock is the RTC PIT at 16 Hz (62.5 ms) from the internal ULP oscillator, measured
  against the main clock at boot, so the node wakes for its slot to the millisecond after about
  0.1 s of idle.

## Sensors: powered per task

- Both sensor headers are used. Nothing is powered at boot: the first task that needs the SHT41 or
  the ENS160 looks for it on J3, then J4, and the single TWI is moved to a sensor's header
  (Wire.swap) before every access.
- Nothing is powered between tasks. Status packets switch no sensor on and carry voltage and energy
  only (temperature / humidity sent as 0x7FFE "not measured", gas status 0xFC).
- Temperature / humidity task: the SHT41's header is switched on in the reply slot, read, switched off.
- Gas task: the ENS160's header is switched on as soon as the task arrives and heats until the reply
  slot one frame (60 s) later; that reading goes out with the ENS160's validity flag (warm-up until
  about 3 min, "first hour" while the sensor itself is new). Then it is switched off. With
  TEST_IGNORE_ENERGY 0, a gas task the node cannot afford is skipped as it arrives, before the heater
  runs, and the reply slot sends a status packet.
- Headers are switched on with a pulsed ramp (on-times 50 to 800 us in 5 us steps, 20 us off): a plain
  switch-on of the ENS160 board browned the node out every time. See `bench/sequence_test/RESULTS.md`.

## Brown-outs

- After a brown-out reset the node puts the radio to sleep, then rests in power-down (30 s, doubling
  up to 8 min) before switching anything on, so the storage can recharge.
- A brown-out is pinned on what was going on: switching J3 on, switching J4 on, or the ENS160 heater.
  After 3 in a row that part stays off (the rest keeps working); a power-on, a flash, or the hourly
  retry clears it. An unexplained brown-out (the radio, a low storage) only lengthens the rest: the
  sensors are off anyway, so it never blocks them.
- A brown-out during a transmission lowers the stored TX power cap by 2 dB (floor 2 dBm).

## Bench sketches (`bench/`)

- `sensor_test`: no LoRa, powers both headers and prints both sensors and the storage voltage every 2 s.
- `sequence_test`: tries power-up sequences over and over, survives its own brown-outs, and ranks them.

Server side (not in this repo): `task-service-tdma` (port 5002) and the Node-RED tab "Workflow 4 - TDMA".
For four nodes it needs `TDMA_SLOTS = 4` (with `TDMA_SLOT_S = 15`, a 60 s frame) and the DevEUIs of
nodes 3 and 4 in `num_to_eui`; the two new devices are registered in ChirpStack like nodes 1 and 2.
Workflow 3 (ALOHA) should be off for these nodes.

Build and flash exactly as the ALOHA sketches (MegaCoreX ATmega4809, 48 pin standard, internal 8 MHz,
BOD 2.6 V, EEPROM retained, JTAG2UPDI). Each sketch folder needs its own `secrets.h`
(copy `secrets.example.h` and fill in that node's DevEUI and AppKey from ChirpStack; secrets.h is kept
out of git, so a fresh clone has none).
