// Host HAL with a simple tunnel model, used by the unit tests.
#pragma once
#include "../src/hal.h"
#include <cmath>
#include <string>
#include <vector>

class SimHal : public Hal {
public:
    uint32_t t = 0; float fan = 0, servo = 0; bool estop = false; float vbus = 12.0f;
    bool fan_works = true; bool cells_work = true; float extra_lift_n = 0, extra_drag_n = 0;
    std::vector<std::string> logs; int led_on = 0;
    uint32_t last_hx = 0;
    void read(SensorFrame &f) override {
        if (cells_work && t - last_hx >= 100) {   // 10 SPS
            last_hx = t;
            float q = 50.0f * fan * fan;
            float lift = extra_lift_n + 0.1f * q * 0.0028f * (servo * 0.1f);   // CL ~ 0.1/deg
            float drag = extra_drag_n + 0.02f * q * 0.0028f;
            f.lift_ok = f.drag_ok = true;
            f.lift_raw = 100000 + (int32_t)(lift / 1.0e-6f);
            f.drag_raw = 200000 + (int32_t)(drag / 1.0e-6f);
        }
        f.dp_ok = true; f.dp_pa = 50.0f * fan * fan / 1.067f; f.temp_c = 21.0f;
        f.aoa_ok = true; f.aoa_raw_deg = 120.0f + servo;
        f.fan_rpm = fan_works ? 8000.0f * fan : 0.0f;
        f.vbus_v = vbus; f.estop_open = estop;
    }
    void set_fan(float d) override { fan = d; }
    void set_servo_deg(float d) override { servo = d; }
    void set_led(bool on) override { led_on = on; }
    std::vector<uint8_t> strip; int strip_writes = 0;
    void set_leds(const uint8_t *rgb, int n) override { strip.assign(rgb, rgb + 3 * n); strip_writes++; }
    uint32_t millis() override { return t; }
    void log(const char *m) override { logs.push_back(m); }
    void advance(class Controller &c, int ms);
};
