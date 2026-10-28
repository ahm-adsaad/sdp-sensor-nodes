# Sensor-header power-up tests (2026-10-28)

Board: rev-2 PCB (node 1, SN-1), SHT41 breakout on J3, ENS160 breakout on J4, storage 3.04-3.25 V,
radio asleep. Each trial: both headers off and drained (the MIC94069 discharges its outputs), rest,
switch on, find both sensors, start ENS160 gas sensing, read both every 2 s. Pass = no brown-out and
both sensors read. `sequence_test.ino` is the tester as it stood for round 4; rounds 1-3 only
differed in the `SEQUENCES` table and the timings noted below.

## Round 1 - order and gaps (15 s rest, 15 s reading, 6 trials each)

| Sequence | Pass | Brown-outs |
|---|---|---|
| J3, 5 ms, J4 | 0/6 | 6, all at J4 |
| J4, 5 ms, J3 | 0/6 | 6, all at J4 |
| J3, 1 s, J4 | 0/6 | 6, all at J4 |
| J4, 1 s, J3 | 0/6 | 6, all at J4 |
| both at once | 0/6 | 6 |
| J3, 1 s, J4, heater 5 s later | 0/6 | 6, all at J4 |

Every plain switch-on of the ENS160 board browned the node out; the SHT41 on J3 never did. The
heater never got to start.

## Round 2 - pre-charging J4 in pulses (5 trials each)

J4's enable is pulsed: on for part of the switch's 800 us soft-start ramp, off again, repeated, then
left on. "ramp a-b/s, off o" = on-times from a to b us in steps of s, o us off between pulses.

| Pattern | Pass |
|---|---|
| plain switch-on (control) | 0/5 |
| ramp 100-800/25, off 20 | 0/5 |
| 200 us on / 20 off x 60 | 0/5 |
| 400 us on / 20 off x 40 | 0/5 |
| 50 us on / 5 off x 400 | 0/5 |
| **ramp 50-800/10, off 50** | **5/5** |

## Round 3 - what makes the ramp work (8 s rest, 8 s reading, 5 trials each)

| Pattern | Pass |
|---|---|
| ramp 50-800/10, off 50 (round 2 winner) | 3/5 |
| off 20 (else as above) | **5/5** |
| first pulse 100 us (else as above) | 3/5 |
| step 25 (else as above) | 0/5 |
| **step 5** (else as above) | **5/5** |
| off 100 (else as above) | 3/5 |

Fine steps matter most, short off-gaps help (the switch drains the board while off). Storage was
about 0.1 V lower than in round 2, which is where the round-2 winner lost its margin.

## Round 4 - the combination (8 trials each)

| Pattern | Pass |
|---|---|
| **ramp 50-800/5, off 20** (used in the TDMA firmware, `railRamp`) | **8/8** at 3.05 V |
| ramp 50-800/2, off 20 | 8/8 at 3.04 V |

The firmware switches both headers on with the 50-800 us / step 5 / off 20 us ramp (about 70 ms).
In the TDMA task tests that followed (task-driven power, one header at a time), 3 of 3 gas tasks ran
without a brown-out at 2.94-2.97 V storage.
