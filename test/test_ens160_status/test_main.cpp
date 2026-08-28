#include <unity.h>
#include <cstring>
#include "common/sensors/Ens160Status.h"

void setUp() {}
void tearDown() {}

static void test_flags_map_to_status() {
    TEST_ASSERT_EQUAL(Ens160Status::Normal,         ens160StatusFromFlags(0));
    TEST_ASSERT_EQUAL(Ens160Status::Warmup,         ens160StatusFromFlags(1));
    TEST_ASSERT_EQUAL(Ens160Status::InitialStartup, ens160StatusFromFlags(2));
    TEST_ASSERT_EQUAL(Ens160Status::Invalid,        ens160StatusFromFlags(3));
}

static void test_error_and_unknown_flags_map_to_error() {
    TEST_ASSERT_EQUAL(Ens160Status::Error, ens160StatusFromFlags(0xFF));
    TEST_ASSERT_EQUAL(Ens160Status::Error, ens160StatusFromFlags(4));
    TEST_ASSERT_EQUAL(Ens160Status::Error, ens160StatusFromFlags(200));
}

static void test_status_names() {
    TEST_ASSERT_EQUAL_STRING("NORMAL",  ens160StatusName(Ens160Status::Normal));
    TEST_ASSERT_EQUAL_STRING("WARMUP",  ens160StatusName(Ens160Status::Warmup));
    TEST_ASSERT_EQUAL_STRING("STARTUP", ens160StatusName(Ens160Status::InitialStartup));
    TEST_ASSERT_EQUAL_STRING("INVALID", ens160StatusName(Ens160Status::Invalid));
    TEST_ASSERT_EQUAL_STRING("ERROR",   ens160StatusName(Ens160Status::Error));
}

static void test_status_is_valid_only_when_normal() {
    TEST_ASSERT_TRUE (ens160StatusIsValid(Ens160Status::Normal));
    TEST_ASSERT_FALSE(ens160StatusIsValid(Ens160Status::Warmup));
    TEST_ASSERT_FALSE(ens160StatusIsValid(Ens160Status::InitialStartup));
    TEST_ASSERT_FALSE(ens160StatusIsValid(Ens160Status::Invalid));
    TEST_ASSERT_FALSE(ens160StatusIsValid(Ens160Status::Error));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_flags_map_to_status);
    RUN_TEST(test_error_and_unknown_flags_map_to_error);
    RUN_TEST(test_status_names);
    RUN_TEST(test_status_is_valid_only_when_normal);
    return UNITY_END();
}
