// Hardware abstraction. The controller only talks to this interface, so the
// same controller code runs on the ESP32 and in the host test build.
#pragma once
#include <cstdint>

struct SensorFrame {
    bool lift_ok = false;   // a new HX711 sample is available
    bool drag_ok = false;
    int32_t lift_raw = 0;   // HX711 counts
    int32_t drag_raw = 0;
    bool dp_ok = false;
    float dp_pa = 0.0f;     // differential pressure, Pa
    float temp_c = 20.0f;   // air temperature from the SDP810
    bool aoa_ok = false;
    float aoa_raw_deg = 0.0f;  // AS5600 angle, 0..360
    float fan_rpm = 0.0f;
    float vbus_v = 12.0f;
    bool estop_open = false;   // true = the stop loop is open -> stop
};

class Hal {
public:
    virtual ~Hal() {}
    virtual void read(SensorFrame &f) = 0;
    virtual void set_fan(float duty01) = 0;          // 0..1
    virtual void set_servo_deg(float deg) = 0;        // -90..90 about centre
    virtual void set_led(bool on) = 0;
    virtual void set_leds(const uint8_t *rgb, int n) = 0;   // n pixels, 3 bytes each (R,G,B)
    virtual uint32_t millis() = 0;
    virtual void log(const char *msg) = 0;
};
