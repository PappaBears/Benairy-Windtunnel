// Unit tests for the Benairy controller core (host build, no Arduino).
#include "../src/controller.h"
#include "sim_hal.h"
#include <cassert>
#include <cstdio>
#include <cstring>

void SimHal::advance(Controller &c, int ms) { for (int i = 0; i < ms / 10; ++i) { t += 10; c.tick(); } }

static int fails = 0;
#define CHECK(cond) do { if (!(cond)) { printf("  FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); fails++; } } while (0)

static void tare(SimHal &h, Controller &c) { c.cmd_tare(); h.advance(c, 2200); }

static void test_fan_slew() {
    printf("test_fan_slew\n");
    SimHal h; Controller c(h);
    h.advance(c, 100);
    CHECK(c.cmd_fan(1.0f) == "ok");
    h.advance(c, 1000);
    CHECK(h.fan > 0.2f && h.fan < 0.3f);         // 0.25 per second
    h.advance(c, 3500);
    CHECK(std::fabs(h.fan - 1.0f) < 1e-3f);
    c.cmd_fan(0.0f); h.advance(c, 10);
    CHECK(h.fan == 0.0f);                          // down is immediate
}

static void test_estop_and_clear() {
    printf("test_estop_and_clear\n");
    SimHal h; Controller c(h); h.advance(c, 100);
    c.cmd_fan(0.5f); h.advance(c, 3000);
    h.estop = true; h.advance(c, 20);
    CHECK(c.telemetry().state == State::FAULT);
    CHECK(h.fan == 0.0f);
    CHECK(c.cmd_fan(0.5f) != "ok");               // refused while faulted
    CHECK(c.cmd_clear_faults() != "ok");          // loop still open
    h.estop = false;
    CHECK(c.cmd_clear_faults() == "ok");
    CHECK(c.telemetry().state == State::IDLE);
}

static void test_fan_stall() {
    printf("test_fan_stall\n");
    SimHal h; Controller c(h); h.advance(c, 100);
    h.fan_works = false;
    c.cmd_fan(0.6f); h.advance(c, 6000);
    CHECK(c.telemetry().faults & F_FAN_STALL);
    CHECK(h.fan == 0.0f);
}

static void test_overload() {
    printf("test_overload\n");
    SimHal h; Controller c(h); h.advance(c, 300); tare(h, c);
    c.cmd_fan(0.3f); h.advance(c, 2000);
    h.extra_lift_n = 2.0f; h.advance(c, 300);
    CHECK(c.telemetry().faults & F_OVERLOAD_LIFT);
    CHECK(h.fan == 0.0f);
}

static void test_client_timeout() {
    printf("test_client_timeout\n");
    SimHal h; Controller c(h); h.advance(c, 100);
    c.client_seen(); c.cmd_fan(0.5f); h.advance(c, 3000);
    CHECK(c.telemetry().state == State::RUNNING);
    h.advance(c, 9000);                            // 12 s without a poll
    CHECK(c.telemetry().faults & F_CLIENT_TIMEOUT);
    CHECK(h.fan == 0.0f);
}

static void test_sensor_stale() {
    printf("test_sensor_stale\n");
    SimHal h; Controller c(h); h.advance(c, 300);
    c.cmd_fan(0.5f); h.advance(c, 1000);
    h.cells_work = false; h.advance(c, 2000);
    CHECK(c.telemetry().faults & F_SENSOR_STALE);
}

static void test_tare_and_calibration() {
    printf("test_tare_and_calibration\n");
    SimHal h; Controller c(h); h.advance(c, 300);
    h.extra_lift_n = 0.05f; h.extra_drag_n = 0.01f;      // model weight before tare
    tare(h, c);
    CHECK(c.telemetry().tared);
    CHECK(std::fabs(c.telemetry().lift_n) < 1e-4f);
    h.extra_lift_n += 0.100f;                             // +100 mN applied
    h.advance(c, 300);
    CHECK(std::fabs(c.telemetry().lift_n - 0.100f) < 2e-3f);
    // calibration matrix with cross-talk
    c.set_config("m21", 0.1e-6f); h.advance(c, 300);
    CHECK(std::fabs(c.telemetry().drag_n - 0.010f) < 2e-3f);
    CHECK(c.set_config("nonsense", 1) != "ok");
}

static void test_aoa_zero_and_sign() {
    printf("test_aoa_zero_and_sign\n");
    SimHal h; Controller c(h); h.advance(c, 300);
    CHECK(c.cmd_zero_aoa() == "ok");
    c.cmd_aoa(10.0f); h.advance(c, 100);
    CHECK(std::fabs(c.telemetry().aoa_deg - 10.0f) < 1e-3f);
    c.cmd_aoa(99.0f); h.advance(c, 100);
    CHECK(std::fabs(c.telemetry().aoa_cmd - 30.0f) < 1e-3f);   // clamped
    c.set_config("aoa_sign", -1.0f); h.advance(c, 100);
    CHECK(std::fabs(c.telemetry().aoa_deg + 30.0f) < 1e-3f);
}

static void test_sweep() {
    printf("test_sweep\n");
    SimHal h; Controller c(h); h.advance(c, 300); c.cmd_zero_aoa();
    SweepSpec s; s.aoas = {-5, 0, 5, 10}; s.fan = 0.8f; s.settle_s = 1.0f; s.samples = 10; s.up_and_down = false;
    CHECK(c.cmd_sweep(s) != "ok");                 // not tared yet
    tare(h, c);
    CHECK(c.cmd_sweep(s) == "ok");
    CHECK(c.telemetry().state == State::SWEEP);
    h.advance(c, 30000);
    CHECK(c.sweep_done());
    CHECK(c.sweep_results().size() == 4);
    CHECK(c.telemetry().state == State::IDLE);
    CHECK(h.fan == 0.0f);                           // fan off after the sweep
    const auto &r = c.sweep_results();
    CHECK(std::fabs(r[3].aoa_mean - 10.0f) < 0.01f);
    CHECK(r[3].lift_mean > r[0].lift_mean);
    CHECK(r[0].n == 10);
    CHECK(std::fabs(r[1].q_mean - 32.0f) < 0.5f);  // 50 * 0.8^2
    std::string csv = c.sweep_csv();
    CHECK(csv.find("point,aoa_cmd_deg") == 0);
    int lines = 0; for (char ch : csv) if (ch == '\n') lines++;
    CHECK(lines == 5);
    // up and down doubles the points minus one
    SweepSpec s2 = s; s2.up_and_down = true; c.cmd_sweep(s2); h.advance(c, 60000);
    CHECK(c.sweep_results().size() == 7);
}

static void test_json() {
    printf("test_json\n");
    SimHal h; Controller c(h); h.advance(c, 500);
    std::string j = c.telemetry_json();
    CHECK(j.front() == '{' && j.back() == '}');
    CHECK(j.find("\"state\":\"IDLE\"") != std::string::npos);
    std::string s = c.samples_json(0);
    CHECK(s.front() == '[' && s.find("\"seq\":1") != std::string::npos);
    std::string s2 = c.samples_json(c.telemetry().seq);
    CHECK(s2 == "[]");
    CHECK(c.config_json().find("\"kq\":1.067") != std::string::npos);
}

int main() {
    test_fan_slew(); test_estop_and_clear(); test_fan_stall(); test_overload(); test_client_timeout();
    test_sensor_stale(); test_tare_and_calibration(); test_aoa_zero_and_sign(); test_sweep(); test_json();
    printf(fails ? "\n%d CHECK(S) FAILED\n" : "\nALL CONTROLLER TESTS PASSED\n", fails);
    return fails ? 1 : 0;
}
