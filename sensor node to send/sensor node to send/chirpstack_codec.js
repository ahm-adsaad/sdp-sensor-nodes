// ChirpStack v4 payload codec for the sensor nodes (sensor_node_1 / sensor_node_2 sketches).
// Paste into Device profile > Codec > "JavaScript functions".
// Uplinks arrive on fPort 1, commands are sent on fPort 10 (one byte).
//
// Uplink packet types (first byte):
//   0x00 status  - 15 bytes from firmware 2026-10-28 on; 11 bytes (no AQI / ENS160 status / TX power /
//                  reset flags) or 9 bytes (no storage voltage either) from older firmware
//   0x01 humidity reply     - 3 bytes
//   0x02 temperature reply  - 3 bytes
//   0x03 gas reply          - 7 bytes (5 from older firmware: no AQI / ENS160 status)
// 16-bit values are big-endian. Temperature and humidity are x100; 0x7FFF means the SHT41
// did not answer. Storage voltage 0 means not measured.

var NO_READING = 0x7fff;

var COMMANDS = { humidity: 0x01, temperature: 0x02, gas: 0x03 };

var ENS160_STATUS = {
  0x00: "normal",
  0x01: "warmup",            // first ~3 min after the sensor starts gas sensing: values settling
  0x02: "initial_startup",   // first hour of a new sensor's life: values not trustworthy
  0x03: "invalid",
  0xfd: "no_sample",         // sensing, but no fresh sample yet (first second after start)
  0xfe: "no_answer",         // found at boot, no I2C answer now
  0xff: "absent"             // not fitted, or not started yet
};

function u16(b, i) {
  return (b[i] << 8) | b[i + 1];
}

function s16(b, i) {
  var v = u16(b, i);
  return v & 0x8000 ? v - 0x10000 : v;
}

function s8(v) {
  return v & 0x80 ? v - 0x100 : v;
}

function scaled(b, i) {
  var v = s16(b, i);
  return v === NO_READING ? null : v / 100;
}

function resetCauses(flags) {
  var names = ["power_on", "brown_out", "external", "watchdog", "software", "updi"];
  var out = [];
  for (var bit = 0; bit < names.length; bit++) {
    if (flags & (1 << bit)) out.push(names[bit]);
  }
  return out;
}

function gasFields(data, b, aqiIndex) {
  data.tvoc_ppb = u16(b, 1);
  data.eco2_ppm = u16(b, 3);
  if (b.length > aqiIndex + 1) {
    data.aqi_uba = b[aqiIndex] === 0 ? null : b[aqiIndex];
    data.ens160_status_code = b[aqiIndex + 1];
    data.ens160_status = ENS160_STATUS[b[aqiIndex + 1]] || "unknown";
    data.gas_valid = b[aqiIndex + 1] === 0;
  }
}

function decodeUplink(input) {
  var b = input.bytes;
  var data = {};
  var warnings = [];

  if (b.length < 3) {
    return { data: data, errors: ["packet shorter than 3 bytes"] };
  }

  var type = b[0];
  data.packet_type = type;

  if (type === 0x00) {
    data.type = "status";
    if (b.length < 9) {
      return { data: data, errors: ["status packet shorter than 9 bytes"] };
    }
    gasFields(data, b, 11);
    data.temperature_c = scaled(b, 5);
    data.humidity_pct = scaled(b, 7);
    if (data.temperature_c === null || data.humidity_pct === null) {
      warnings.push("SHT41 did not answer");
    }
    if (b.length >= 11) {
      var mv = u16(b, 9);
      data.storage_mv = mv === 0 ? null : mv;
      data.storage_v = mv === 0 ? null : mv / 1000;
    }
    if (b.length >= 15) {
      data.tx_power_dbm = s8(b[13]);
      data.reset_flags = b[14];
      data.reset_causes = resetCauses(b[14]);
      if (b[14] & 0x02) warnings.push("node booted from a brown-out reset");
      if (b[14] & 0x08) warnings.push("node booted from a watchdog reset");
    }
  } else if (type === COMMANDS.humidity) {
    data.type = "humidity";
    data.humidity_pct = scaled(b, 1);
  } else if (type === COMMANDS.temperature) {
    data.type = "temperature";
    data.temperature_c = scaled(b, 1);
  } else if (type === COMMANDS.gas) {
    data.type = "gas";
    if (b.length < 5) {
      return { data: data, errors: ["gas reply shorter than 5 bytes"] };
    }
    gasFields(data, b, 5);
  } else {
    return { data: data, errors: ["unknown packet type 0x" + type.toString(16)] };
  }

  var out = { data: data };
  if (warnings.length) out.warnings = warnings;
  return out;
}

// { "command": "gas" } or { "command": 3 } -> [0x03]
function encodeDownlink(input) {
  var cmd = input.data.command;
  if (typeof cmd === "string") {
    cmd = COMMANDS[cmd.toLowerCase()];
  }
  if (cmd !== 0x01 && cmd !== 0x02 && cmd !== 0x03) {
    return { errors: ["command must be humidity, temperature or gas (1, 2 or 3)"] };
  }
  return { bytes: [cmd], fPort: 10 };
}

function decodeDownlink(input) {
  var names = { 1: "humidity", 2: "temperature", 3: "gas" };
  var cmd = input.bytes[0];
  if (!names[cmd]) {
    return { errors: ["unknown command byte " + cmd] };
  }
  return { data: { command: names[cmd] } };
}
