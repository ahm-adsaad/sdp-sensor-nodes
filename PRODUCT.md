# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static HTML/CSS rendered to PDF with headless Chromium for print deliverables (posters). Chosen by Claude on 2026-10-19; the user was not asked about tooling.

## Users

AUS senior design team (Ahmad Saad, Abdulrahman Hanifa, Mohammad Alatrash, Abdalrahman Al-Zaharna; advisor Dr. Anastassia Gharib) presenting their work to judges and visitors from government, industry and academia, e.g. the EWSERC / SEWA Student Poster Competition, "Infrastructure Resilience in Action: Preparing Sharjah for the Future" (22 Oct 2026, Hall A, AUS).

## Product Purpose

A solar energy-harvesting wireless sensor network: custom ATmega4809 sensor nodes (SHT41 temperature/humidity, ENS160 CO2/TVOC) talk LoRaWAN to a RAK WisGate Edge Lite 2 gateway, which forwards to a VPS (ChirpStack, Node-RED, InfluxDB, Grafana). Sensor nodes are virtualized: one node serves different sensing tasks over time. The VPS assigns dynamically arriving user tasks to nodes based on their stored energy. Goal: battery-free, maintenance-free environmental monitoring.

## Positioning

Couples solar EH, sensor-node virtualization and energy-aware dynamic task assignment in one hardware-implemented system; prior work covers these separately and mostly in simulation.

## Capabilities and Constraints

- Report of record: `paper/SDP___…/SDP-Template-v3.tex` (design-stage; implementation, power profiling and validation are future work there).
- Poster content is restricted to what the report states (user decision, 2026-10-19). Forecasting results in `forecast/` and rev-2 hardware changes are not on the poster.
- One cluster of four sensor nodes and one gateway; EU868 band.

## Brand Commitments

- Report title: "A Practical Implementation of a Virtualized Energy Harvesting IoT".
- American University of Sharjah seal (`paper/SDP___…/AUSlogo.png`), maroon #880E12.
- Poster style pinned by the user: IEEE poster conventions; no captions, no subtitles, no filler text.

## Evidence on Hand

- Figures in `paper/SDP___…/` (system model, hardware architecture, WSN schedule, schematic, UI screenshots).
- No measured results in the report. The Grafana screenshot shows test values, not field data. Do not present any number as a measured result.

## Product Principles

- Every claim traces to the report or a datasheet; unknowns stay off the page.
- Show the mechanism (energy-aware assignment over virtualized nodes) rather than describe it.
- Plain engineering language, no marketing tone.
