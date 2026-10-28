# Sensor node firmware, TDMA version

TDMA variant of the PCB firmware in `sensor node to send/` (the ALOHA version, unchanged).
Same board, sensors, keys and build settings; what differs is when the node transmits.

- One uplink per 30 s frame, only at the start of the node's own slot (node 1: slot 0, node 2: slot 1,
  15 s apart), so the uplinks and the gateway's answers never overlap.
- The schedule comes in every TDMA downlink (fPort 20, 6 bytes): task command, slot index, slots per
  frame, frame length in seconds, and a slot correction in ms relative to the uplink it answers.
- A task is answered in the node's next slot.
- Every uplink ends with the node's energy, 0..200 units from the storage voltage:
  200 x (V^2 - 2.80^2) / (3.60^2 - 2.80^2), the AEM10330's cut-off and full levels (1 unit = 1.92 J
  for the 150 F store). A task the node cannot afford is skipped and a status packet goes instead.
- Brown-out back-off: after a brown-out reset the node sleeps 30 s, then 60, 120... (up to 8 min) before
  switching anything on; from the 3rd in a row it runs without the sensor rail (radio only) and retries
  the sensors after an hour. The sensor rail is switched on with a pulsed soft start.

Server side (not in this repo): `task-service-tdma` (port 5002, 2 slots x 15 s) and the Node-RED tab
"Workflow 4 - TDMA". Workflow 3 (ALOHA) should be off for these nodes.

Build and flash exactly as the ALOHA sketches (MegaCoreX ATmega4809, 48 pin standard, internal 8 MHz,
BOD 2.6 V, EEPROM retained, JTAG2UPDI). Put the node's keys in `secrets.h` next to the sketch
(see `secrets.example.h`; secrets.h is kept out of git).
