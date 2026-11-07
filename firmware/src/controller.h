// Benairy controller core: states, safety, averaging, sweeps, calibration.
// Portable C++17, no Arduino dependency. See controller.cpp.
#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include "hal.h"

enum class State : uint8_t { IDLE, RUNNING, SWEEP, FAULT };

enum Fault : uint16_t {
    F_NONE = 0, F_ESTOP = 1, F_FAN_STALL = 2, F_OVERLOAD_LIFT = 4, F_OVERLOAD_DRAG = 8,
    F_CLIENT_TIMEOUT = 16, F_SENSOR_STALE = 32, F_VBUS_LOW = 64, F_AOA_SENSOR = 128,
};

struct Config {
    // balance calibration: F = M * (raw - raw0); N per count
    float m11 = 1.0e-6f, m12 = 0.0f, m21 = 0.0f, m22 = 1.0e-6f;
    float kq = 1.067f;            // q = kq * (dp - dp0), from the contraction ratio
    float p_station_pa = 101325.0f;
    float aoa_zero_deg = 0.0f;    // AS5600 reading when the strut is vertical
    float aoa_sign = 1.0f;        // +1 or -1 so that nose-up is positive
    float servo_gain = 1.0f;      // servo deg per model deg (drum is on the servo shaft)
    float servo_offset_deg = 0.0f;
    float lift_limit_n = 1.5f, drag_limit_n = 0.8f;
    float fan_slew_up = 0.25f;
    float aoa_min = -30.0f, aoa_max = 30.0f;
    float client_timeout_s = 10.0f;
    float vbus_min_v = 10.5f;
    float stall_rpm = 300.0f, stall_grace_s = 3.0f;
};

struct Telemetry {
    uint32_t seq = 0, t_ms = 0;
    State state = State::IDLE;
    uint16_t faults = 0;
    float fan_cmd = 0, fan_out = 0, fan_rpm = 0;
    float aoa_cmd = 0, aoa_deg = 0;
    int32_t lift_raw = 0, drag_raw = 0;
    float lift_n = 0, drag_n = 0;
    float dp_pa = 0, q_pa = 0, v_ms = 0, temp_c = 20, rho = 1.2f, vbus = 12;
    bool tared = false;
};

struct SweepPoint {
    float aoa_cmd = 0, aoa_mean = 0, aoa_sd = 0;
    float fan_cmd = 0, rpm_mean = 0;
    float q_mean = 0, q_sd = 0, v_mean = 0, temp_mean = 20, rho = 1.2f;
    float lift_mean = 0, lift_sd = 0, drag_mean = 0, drag_sd = 0;
    int32_t lift_raw_mean = 0, drag_raw_mean = 0;
    uint16_t n = 0;
};

struct SweepSpec {
    std::vector<float> aoas;
    float fan = 0.0f;           // 0 = wind-off tare sweep
    float settle_s = 2.0f;
    uint16_t samples = 40;      // HX711 samples per point (10 SPS -> 4 s)
    bool up_and_down = false;   // repeat the list in reverse to show hysteresis
};

class Controller {
public:
    explicit Controller(Hal &hal);
    void tick();                               // call at TICK_HZ
    // commands (return a short message)
    std::string cmd_fan(float duty01);
    std::string cmd_aoa(float deg);
    std::string cmd_tare();                    // zero the balance and dp (2 s average)
    std::string cmd_zero_aoa();                // current strut angle = 0 deg
    std::string cmd_sweep(const SweepSpec &s);
    std::string cmd_stop();
    std::string cmd_clear_faults();
    std::string set_config(const std::string &key, float value);
    void client_seen();                        // the dashboard polled us
    // data
    const Telemetry &telemetry() const { return tel_; }
    const Config &config() const { return cfg_; }
    Config &config_mut() { return cfg_; }
    const std::vector<SweepPoint> &sweep_results() const { return sweep_pts_; }
    bool sweep_done() const { return sweep_done_; }
    int sweep_index() const { return sweep_i_; }
    int sweep_total() const { return (int)sweep_.aoas.size(); }
    std::string telemetry_json() const;
    std::string config_json() const;
    std::string sweep_csv() const;
    std::string sweep_json() const;
    // ring buffer of recent telemetry for live plots
    std::string samples_json(uint32_t since_seq) const;
    static const char *state_name(State s);
    static std::string fault_names(uint16_t f);

private:
    void apply_safety(const SensorFrame &f, float dt);
    void update_fan(float dt);
    void update_servo();
    void process_frame(const SensorFrame &f);
    void sweep_step(float dt);
    void fault(uint16_t bit);

    Hal &hal_;
    Config cfg_;
    Telemetry tel_;
    State state_ = State::IDLE;
    float fan_cmd_ = 0, fan_out_ = 0;
    float aoa_cmd_ = 0;
    uint32_t last_ms_ = 0, last_client_ms_ = 0, last_lift_ms_ = 0, last_drag_ms_ = 0;
    float stall_timer_ = 0;
    // tare
    bool taring_ = false; uint32_t tare_start_ms_ = 0;
    double tare_sum_l_ = 0, tare_sum_d_ = 0, tare_sum_dp_ = 0; uint32_t tare_n_l_ = 0, tare_n_d_ = 0, tare_n_dp_ = 0;
    int32_t raw0_l_ = 0, raw0_d_ = 0; float dp0_ = 0; bool tared_ = false;
    // latest sensor values
    float dp_last_ = 0, temp_last_ = 20, aoa_last_ = 0, rpm_last_ = 0, vbus_last_ = 12;
    bool aoa_seen_ = false;
    // sweep
    SweepSpec sweep_; std::vector<float> sweep_list_; int sweep_i_ = -1; bool sweep_done_ = true;
    float sweep_timer_ = 0; bool sweep_settling_ = false;
    struct Acc { double sl=0, sl2=0, sd=0, sd2=0, sq=0, sq2=0, sa=0, sa2=0, st=0, sr=0, rl=0, rd=0; uint32_t n=0, nq=0, na=0; } acc_;
    std::vector<SweepPoint> sweep_pts_;
    // ring buffer
    static const int RING = 200;
    Telemetry ring_[RING]; int ring_head_ = 0; int ring_count_ = 0;
};
