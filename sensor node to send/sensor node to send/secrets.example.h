// Template for a node's secrets.h: copy it into the sketch folder as secrets.h and fill in the
// keys from ChirpStack. secrets.h is git-ignored, so keys never reach GitHub.
#pragma once

// JoinEUI (AppEUI), LSB first; all zeros for ChirpStack
static const u1_t PROGMEM APPEUI[8] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };

// DevEUI, byte-reversed (LSB first) as LMIC requires
static const u1_t PROGMEM DEVEUI[8] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };

// AppKey, normal (MSB-first) order
static const u1_t PROGMEM APPKEY[16] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
