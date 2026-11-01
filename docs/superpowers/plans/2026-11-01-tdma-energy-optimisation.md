# TDMA firmware energy optimisation — implementation plan (2026-11-01)

**Spec (binding):** the energy audit at `docs/superpowers/specs/2026-11-01-tdma-energy-audit.md`
(read-only review of the firmware at f99731d, 2026-11-01, nothing measured). Section 5.3 defines the fixes, section 6 is the functional contract every task is held
to, section 8 lists observations that are NOT in scope. Line numbers below ("L…") refer to
`sensor node tdma/sensor_node_1_tdma/sensor_node_1_tdma.ino` as of commit f99731d (HEAD firmware).

**Why:** the nodes empty their 384 J store in days. The audit found the firmware alone spends
about 64 J/day, of which about 16 J/day is pure waste (idle before every slot), with larger
conditional wastes (about 287 J/day while the gateway is unreachable; 0.2-2.5 J per brown-out
rest; 2.8 J per gas task the node cannot afford). This plan removes the firmware waste with
zero functional loss. Hardware (R9-R12 back-feed) and design choices (gas heating time, 30 s
cadence, server RX window) are left to the user.

## Global constraints

1. **Files that may change:** `sensor node tdma/sensor_node_1_tdma/sensor_node_1_tdma.ino`,
   `sensor node tdma/sensor_node_2_tdma/sensor_node_2_tdma.ino`, `sensor node tdma/README.md`.
   Nothing else in the repo. No library edits. No new libraries.
2. **Node 2 is a copy of node 1.** Today the two sketches differ in exactly 4 lines: lines 1-3
   (header comment: "sensor_node_2.ino", "NODE 2 keys (DevEUI 3609e0641306e11c)", "sensor 2") and
   `#define NODE_NUMBER 2` (L74). After every task, regenerate node 2 from node 1 and re-apply
   those 4 lines; `diff` of the two files must show only those 4 lines. Both sketches are
   committed together in every commit.
3. **Zero functional loss:** every checklist item in audit report section 6 holds after each
   task. In particular: the switch-on ramp `railRamp` is untouched; `LMIC_setClockError`, SF7,
   ADR off, LinkCheck off, the TX-cap logic, the DevNonce save, the TDMA slot maths, the payload
   bytes, the brown-out culprit rules and the EEPROM layout are untouched.
4. **Build flags stay:** `DEBUG 1`, `USE_ENS160 1`, `VSTO_SENSE 1`, `TEST_IGNORE_ENERGY 1`
   keep their current values (the user flips them at flash time).
5. **Compile after every task**, both sketches, with the scratchpad script:
   `bash "C:/Users/ahmad/AppData/Local/Temp/claude/C--Users-ahmad-Desktop-GitHubRepos-sdp-sensor-nodes/bc946f32-9fb5-4659-8d0e-5e337436dce1/scratchpad/compile.sh" "<sketch dir>"`
   (arduino-cli, FQBN MegaCoreX:megaavr:4809:pinout=48pin_standard,clock=internal_8MHz,
   bootloader=no_bootloader; it copies the sketch to a scratch folder and uses
   secrets.example.h as secrets.h). Baseline at HEAD: 37124 B flash, 1604 B RAM. Record the size
   after each task. Zero new warnings from the sketch itself (the LMIC "Board not supported"
   pragma note is pre-existing and fine).
6. **No hardware here.** Nothing can be flashed or measured in this session; the report must say
   "compile-tested only" wherever that is the truth.
7. **Commits:** one commit per task, both sketches (and README where touched) in it. Message in
   the team's style (see `git log -3 -- "sensor node tdma"`): a lower-case imperative subject
   line that says what changed and why, a body with concrete bullets, "Compile-tested only, not
   flashed" where true. **No `Co-Authored-By` trailer, no "Generated with" line, no emoji.**
   Do not push; the controller pushes after review.
8. The implementer never dispatches subagents.

## Task order and dependencies

Task 1 (16 Hz sleep clock) must come before Task 5 (power-down in LMIC waits), because a 2 s
power-down chunk with a 1 s tick would be mostly edge-wait. Tasks 2-4 are independent of each
other. Task 6 is documentation and final verification.

---

## Task 1: Sleep clock at 16 Hz so the node idles ~0.1 s instead of ~2 s before every slot (audit F2, S4)

**Problem.** The PIT runs at 1 Hz (`RTC.PITCTRLA = RTC_PERIOD_CYC1024_gc | RTC_PITEN_bm;`, L1256,
clock `RTC_CLKSEL_INT1K_gc` L1253). `sleepUntil()` (L394-433) waits for a PIT edge in idle
(0-1 s), power-downs for `ticks-1` whole ticks, then idles until `millis()` reaches the target
(1-2 s). Mean ≈ 2 s of idle at ≈ 0.86 mA per 30 s frame ≈ 5.7 mJ, ≈ 16 J/day, 26 % of a status
frame. The idle tail buys nothing: millis is credited by computation (`timer_millis += us / 1000UL`,
L422-425), so the only thing the tail absorbs is the floor() remainder of one tick.

**Change.**
- Introduce one named constant for the tick rate and derive everything from it, e.g.
  `const uint16_t PIT_TICKS_PER_S = 16;` with `RTC_PERIOD_CYC64_gc` (1.024 kHz / 64 = 16 Hz,
  nominal 62.5 ms) and the default `usPerTick = 1000000UL / PIT_TICKS_PER_S` (L174, today
  `1000000`). Add a comment that 1.024 kHz ÷ 64 is 16 Hz, so the nominal tick is 62500 us.
- `measurePitTick()` (L378-387): measure 64 ticks (≈ 4 s, same calibration length as today's
  4 ticks of 1 s) and divide accordingly, so the printed "Sleep clock: one PIT tick = N us" is
  ≈ 62500 ± 10 %.
- `brownOutBackOff()` (L610-632): `wait` is in seconds and is compared against PIT ticks
  (L625-628). Convert: ticks to rest = `wait * PIT_TICKS_PER_S` (the nominal rate; `usPerTick` is
  not measured yet at that point and does not need to be for a rest). The rest must still last
  30, 60, 120, 240, 480, 480 … s and the log line "Brown-out reset N in a row: sleeping N s"
  must still print seconds.
- `sleepUntil()` keeps its structure (edge wait, power-down `ticks-1`, idle tail, millis credit
  with `usCarry`). Only the arithmetic through `usPerTick` changes by itself. Keep the "never
  wake past the target" property.
- **Counter range:** `volatile uint16_t pitTicks` (L355) is compared with a 32-bit tick count in
  the power-down loop (L417). Longest sleep ≈ MAX_FRAME_MS 1800 s + 65.5 s correction ≈ 1866 s
  → 29,856 ticks at 16 Hz, fits. Add a `static_assert` that documents and enforces this:
  `((MAX_FRAME_MS / 1000UL + 66UL) * PIT_TICKS_PER_S) < 65535UL`. Also check that
  `(uint32_t)left * 1000UL` (L410) and `ticks * usPerTick` (L422) still fit in 32 bits with
  the new values (they do: ≤ 1.87e9 and ≤ 2.05e9) and say so in a comment next to the maths.
- Update every comment that says "one interrupt per second", "nominally 1 s", "1 s tick" or
  similar, and the PIT ISR comment (L357-361).
- Any other place that assumes a 1 s tick (search the sketch for `pitTicks`, `usPerTick`,
  `PIT`, `1000000`): fix it or state in the report that none exists.

**Do not touch:** the WDT (8 s, kicked in the ISR and loop), `RTC.CLKSEL`, the PIT sync wait
`while (RTC.PITSTATUS > 0)` (L1255).

**Verify:** both sketches compile; report size. Walk through `sleepUntil(millis() + 30000)` and
`sleepUntil(millis() + 1866000)` by hand in the report with the new numbers (ticks, idle tail
length, credited us). Walk through `brownOutBackOff()` for run 1 and run 6.

**Commit** subject suggestion: `tick the sleep clock at 16 Hz so the node idles 0.1 s, not 2 s, before each slot`.

---

## Task 2: Idle instead of busy-waiting in the boot calibration and the ENS160 poll; input-disable the TWI pins at boot (audit F8, F9, F1 firmware part)

**Change A (F8).** `measurePitTick()` busy-spins ≈ 4 s at 2.9 mA (L382 `while (readPitTicks() == t) { watchdogKick(); }` and L385). Put `LowPower.idle();` inside both loops (the PIT ISR wakes the CPU every tick; idle wake-up is 2.4 µs, DS Table 32-7, so the measurement is unchanged within 0.1 %). Keep `watchdogKick()`.

**Change B (F9).** In the ENS160 NEWDAT poll (L871-878) replace the busy `delay(100)` (L877) with an idle wait of the same length: record `millis()`, then `while (millis() - t0 < 100) { LowPower.idle(); }` (the 1 kHz millis tick wakes the CPU). The poll's 15-try limit, its log line and the returned values stay exactly as they are. Do not touch `gasStart()`'s `delay(100)`/`delay(10)` (L788, L794): those are the ENS160's reset/idle dwell times and are 110 ms once per gas task.

**Change C (F1 firmware part).** At boot, next to the `UNUSED_PINS` input-disable loop (L1228-1229), also input-disable the four TWI pins PA2, PA3, PC2, PC3 (`LowPower.disablePinISC(...)`), with a comment: with R9-R12 on the always-on 3V3 this changes nothing (the lines are held high), and once R9-R12 are removed or moved to VCC_SENS the pins would otherwise float until the first task. `headerOn()` already re-enables them (L689-690) and `headerOff()` disables them (L704-705), so boot now matches the "header off" state. Do NOT add them to `UNUSED_PINS` itself (that array documents pins that are never used).

**Verify:** compile both; report size. Confirm in the report that `headerOn()` re-enables PA2/PA3 or PC2/PC3 before `Wire.begin()` for the bus it selects (cite lines), so change C cannot break the first sensor access.

**Commit** subject suggestion: `idle through the boot calibration and the ENS160 poll, and park the TWI pins at boot`.

---

## Task 3: Put the radio to sleep at the very top of setup(), before the brown-out rest (audit F4, S9)

**Problem.** `setup()` runs `brownOutBackOff()` (L1258, power-down for 30-480 s after a brown-out),
then `measurePitTick()` (4 s), and only then `os_init()` (L1274), which resets the SX1276 and
sleeps it. Until then the radio sits in its reset state (RegOpMode 0x01 = standby, ≈ 1.6 mA) after
a power-on, or in standby after a brown-out that cut a TX/RX short (the SX1276 returns to standby
on its own when a TX/RX ends). A 480 s rest with the radio in standby costs ≈ 2.5 J, which works
against the recharge the rest is for. ≈ 24 mJ per plain boot.

**Change (audit option a, the smallest).** Add a small function, e.g. `radioSleepEarly()`, called
as the first thing in `setup()` after the reset-flag read and before `brownOutBackOff()`:
1. Drive NSS (`lmic_pins.nss`, PA7) as an output, high. `SPI.begin()` (MegaCoreX SPI on PA4-PA6;
   LMIC's `hal_init()` calls `SPI.begin()` again later, harmless).
2. Wait 10 ms for the SX1276 power-on reset to be over (POR to SPI-ready is 10 ms in the SX1276
   datasheet, from memory — say so in the comment). `delay(10)` is fine: 0.1 mJ once per boot.
3. `SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0))`, NSS low, read RegOpMode
   (address 0x01, read = address with bit 7 clear, then one dummy transfer), NSS high. Then NSS
   low, write RegOpMode (address 0x01 | 0x80) with bits 2:0 cleared (mode 000 = SLEEP in both FSK
   and LoRa mode) and every other bit as read (bit 7 LongRangeMode may only be changed in sleep,
   bit 3 LowFrequencyModeOn is the module's setting), NSS high, `SPI.endTransaction()`.
4. Leave NSS high. Do not touch RST (PF3) or the DIO pins: LMIC's `os_init()` does its own
   reset later, exactly as today.
Keep `brownOutBackOff()`'s "first, before anything draws current" comment true by adjusting it:
the radio sleep draws < 1 mA for about 1 ms and is what makes the rest cheap.

**Risk to note in the report:** a radio still transmitting after an MCU brown-out is cut off
(that frame is lost anyway since LMIC's state is gone).

**Verify:** compile both; report size. Quote the SX1276 register read/write SPI format you used
(address byte, wnr bit) and the RegOpMode bit layout, labelled "from memory" if not verified
against a datasheet on disk (there is none on disk).

**Commit** subject suggestion: `put the radio to sleep first thing at boot, so a brown-out rest really rests`.

---

## Task 4: Check the gas task's energy when it arrives, before the heater runs (audit F5, S2 bug part)

**Problem.** With `TEST_IGNORE_ENERGY 0`, a task the node cannot afford is skipped at the reply
slot (L942-955: `tasksSkipped++`, "Skipping task 0x…", `pendingCommand = 0`, `gasStop()`, and a
status packet is sent). For a gas task that is one frame **after** `gasStart()` (L1169, in
EV_TXCOMPLETE) has already heated the ENS160 for ≈ 29 s at 29 mA ≈ 2.8 J — the skip then saves
nothing.

**Change.** In EV_TXCOMPLETE, where a gas task starts the heater (L1168-1169), add the energy
check first: if `!TEST_IGNORE_ENERGY` and `energyUnits(readVstoMv()) < taskCost(CMD_GAS)`, do
exactly what the reply-slot skip does — `tasksSkipped++`, the same "Skipping task 0x3" style log
line (say "at arrival" in it so the bench can tell the two apart), `pendingCommand = 0` — and do
not call `gasStart()`. The next slot then sends a status packet, as a skipped task does today.
`readVstoMv()` is ≈ 3 ms with the radio asleep at that point; it enables and disables the ADC
itself (L903, L916).
- The reply-slot check at L942 stays unchanged (it still covers T/RH and remains a safety net).
- With `TEST_IGNORE_ENERGY 1` (the current value) the heater must start exactly as today —
  make sure the `readVstoMv()` call is also skipped in that case (no extra ADC read).
- `tasksSkipped` must count a skipped gas task once, not twice.

**Functional note (accepted by the controller, record it in the commit body):** the decision moves
one frame earlier. If the storage climbed above the gas cost within those 30 s, today's code would
have sent the gas reply and the new code sends a status packet instead; the server already handles
skipped tasks.

**Verify:** compile both, with `TEST_IGNORE_ENERGY` at 1 (as committed) AND once with it set to 0
in a scratch copy (the compile script copies the sketch; set the define in the copy, not in the
repo) to prove the new branch compiles. Report both sizes.

**Commit** subject suggestion: `skip a gas task the node cannot afford before the heater runs, not after`.

---

## Task 5: Power down instead of idling while LMIC has nothing to do for a while (audit F3, S11)

**Problem.** `loop()` (L1294-1328) power-downs only through `sleepUntil()` when
`sleepPending && !lmicTxBusy()` (L1312). `sleepPending` is set only by EV_JOINED, EV_TXCOMPLETE
and EV_TXCANCELED. While the node is **not joined**, `OP_JOINING` stays set (LMIC clears it only in
processJoinAccept, lmic.c:1625, or LMIC_setSession), so `lmicTxBusy()` is always true and the
node idles at ≈ 0.96 mA around the clock between join attempts: ≈ 287 J/day — it empties the
store in about 1.3 days while the gateway is unreachable. The same idle covers LMIC's duty-cycle
waits for forced uplinks (OP_POLL / OP_TXDATA after MAC commands, ≈ 7 s each, ≈ 20 mJ) and the
random 0-8 s before the first JoinRequest.

**Change.** In `loop()`'s else-branch (today just `LowPower.idle();`, L1324-1328), power down in
bounded chunks when it is provably safe:
- Conditions (all must hold):
  1. `!(LMIC.opmode & OP_TXRXPEND)` — no TX/RX cycle is in progress, so no receive window can be
     missed and no DIO edge needs the 1 ms polling (hal.cpp polls DIO in `lmic_hal_enableIRQs`).
  2. `!os_queryTimeCriticalJobs(ms2osticks(3000))` — no timed LMIC job is due within 3 s
     (oslmic.c:176-178; join attempts, duty-cycle waits and the sketch's own 1 s `do_send`
     retry are timed jobs, so they keep the node awake as today).
  3. The chunk is bounded: target = `millis() + 2000`. If the node is joined (`nextSlotAt` is
     meaningful), cap the target at `nextSlotAt` so the node never sleeps past its slot; if the
     capped chunk is shorter than, say, 200 ms, idle instead of power-down.
- Sleep with the existing `sleepUntil(target)` so the millis/micros credit, the WDT kicks and the
  Serial flush are exactly the same mechanism the per-frame sleep already uses (LMIC's
  `os_getTime()` follows `micros()`, so its scheduled jobs and band-availability times stay
  consistent, as they do across today's 30 s sleeps).
- Otherwise fall back to `LowPower.idle();` as today.
- `sleepPending` semantics do not change; this branch never posts `do_send`.
- Keep the existing comment at L1326 about idle keeping the millis tick running during TX/RX and
  extend it with why power-down is safe under the conditions above.

**Things the report must state explicitly (the reviewer will check them):**
- `os_queryTimeCriticalJobs` only sees timed jobs; a runnable job posted with `os_setCallback`
  could wait up to the chunk length (2 s). Explain why that is harmless here (it can only be a
  join or MAC step, never an RX window — those exist only while OP_TXRXPEND is set) — or, if you
  find a case where it is not harmless, stop and report BLOCKED with the case.
- Why the TX→RX1→RX2 timing cannot be affected (condition 1).
- That the join cadence (EV_JOINING / EV_JOIN_TXCOMPLETE lines) is unchanged: LMIC's timed job
  fires when due because `sleepUntil` credits millis.
- The bootTrace phase: if `sleepUntil` or the loop sets a `.noinit` phase, make sure a brown-out
  during this new sleep is classified the same way as one during the per-frame sleep.

**Verify:** compile both; report size. Hand-trace the unjoined case (join TX scheduled 20 s away:
how many chunks, what happens at the chunk that is within 3 s of it) and the OP_POLL case (a
forced uplink due in 7 s) in the report.

**Commit** subject suggestion: `power down between join attempts and LMIC waits instead of idling all day`.

---

## Task 6: README and final build check

- Update `sensor node tdma/README.md`: in "Brown-outs" say the radio is put to sleep before the
  rest; add a short "Sleep" paragraph (PIT at 16 Hz, calibrated at boot; the node power-downs
  between frames, between join attempts and during LMIC's duty-cycle waits; it idles only while a
  TX/RX cycle is running); in "Sensors: powered per task" note that a gas task the node cannot
  afford (TEST_IGNORE_ENERGY 0) is skipped when it arrives, before the heater runs. Keep the
  README's existing voice and length discipline.
- Final compile of both sketches as committed, plus a scratch-copy compile with `DEBUG 0` (and
  the others unchanged) to prove the deployment variant still builds. Report all sizes against the
  baseline 37124 B / 1604 B.
- Final `diff` of node 1 vs node 2: exactly the 4 known lines.

**Commit** subject suggestion: `describe the 16 Hz sleep clock, the early radio sleep and the arrival-time gas check`.

---

## Out of scope (recorded for the user, do not implement)

- Audit F1 hardware: R9-R12 back-feed (≈ 114 J/day, the largest sink) — needs a board change.
- Audit F6: standby instead of idle in the Class A gap (BOD off in standby; needs a measurement).
- Audit F7: `DEBUG 0` — the user's flash-time choice.
- Audit F10: stopping TCA0/TCB PWM clocks (≈ 0.5 J/day; needs a wiring.c check for the millis TCB).
- Audit F11-F13: gas heating time, cadence, server RX window / RX2 DR / confirmed downlinks.
- Audit section 8 observations (gas-reply retry after `gasStop()` sends "absent"; join-power
  comment says 16 dBm but LMIC uses 14; data forced to SF7 after a weak join; forced uplinks land
  in another node's slot).
