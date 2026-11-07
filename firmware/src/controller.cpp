#include "controller.h"
#include <cmath>
#include <cstdio>
#include <algorithm>

static const float R_AIR = 287.05f;

Controller::Controller(Hal &hal) : hal_(hal) {}

const char *Controller::state_name(State s) {
    switch (s) { case State::IDLE: return "IDLE"; case State::RUNNING: return "RUNNING";
                 case State::SWEEP: return "SWEEP"; default: return "FAULT"; }
}

std::string Controller::fault_names(uint16_t f) {
    std::string s;
    struct { uint16_t b; const char *n; } T[] = {
        {F_ESTOP, "ESTOP"}, {F_FAN_STALL, "FAN_STALL"}, {F_OVERLOAD_LIFT, "OVERLOAD_LIFT"},
        {F_OVERLOAD_DRAG, "OVERLOAD_DRAG"}, {F_CLIENT_TIMEOUT, "CLIENT_TIMEOUT"},
        {F_SENSOR_STALE, "SENSOR_STALE"}, {F_VBUS_LOW, "VBUS_LOW"}, {F_AOA_SENSOR, "AOA_SENSOR"}};
    for (auto &t : T) if (f & t.b) { if (!s.empty()) s += ","; s += t.n; }
    return s;
}

void Controller::fault(uint16_t bit) {
    if (!(tel_.faults & bit)) {
        char buf[64]; snprintf(buf, sizeof buf, "FAULT %s", fault_names(bit).c_str()); hal_.log(buf);
    }
    tel_.faults |= bit;
    state_ = State::FAULT;
    fan_cmd_ = 0; fan_out_ = 0;
    hal_.set_fan(0);
    sweep_done_ = true; sweep_i_ = -1;
}

void Controller::client_seen() { last_client_ms_ = hal_.millis(); }

std::string Controller::cmd_fan(float d) {
    if (state_ == State::FAULT) return "fault active: clear faults first";
    if (state_ == State::SWEEP) return "sweep running: stop it first";
    d = std::max(0.0f, std::min(1.0f, d));
    fan_cmd_ = d;
    state_ = (d > 0) ? State::RUNNING : State::IDLE;
    tel_.state = state_;
    return "ok";
}

std::string Controller::cmd_aoa(float deg) {
    if (state_ == State::SWEEP) return "sweep running";
    aoa_cmd_ = std::max(cfg_.aoa_min, std::min(cfg_.aoa_max, deg));
    update_servo();
    return "ok";
}

std::string Controller::cmd_tare() {
    if (fan_out_ > 0.02f) return "fan must be off (wind-off tare)";
    taring_ = true; tare_start_ms_ = hal_.millis();
    tare_sum_l_ = tare_sum_d_ = tare_sum_dp_ = 0; tare_n_l_ = tare_n_d_ = tare_n_dp_ = 0;
    return "taring 2 s";
}

std::string Controller::cmd_zero_aoa() {
    if (!aoa_seen_) return "no angle sensor reading";
    cfg_.aoa_zero_deg = aoa_last_;
    return "ok";
}

std::string Controller::cmd_sweep(const SweepSpec &s) {
    if (state_ == State::FAULT) return "fault active";
    if (s.aoas.empty()) return "empty list";
    if (!tared_) return "tare first (wind off)";
    sweep_ = s;
    sweep_list_ = s.aoas;
    if (s.up_and_down) for (int i = (int)s.aoas.size() - 2; i >= 0; --i) sweep_list_.push_back(s.aoas[i]);
    sweep_pts_.clear();
    sweep_i_ = 0; sweep_done_ = false; sweep_settling_ = true; sweep_timer_ = 0; acc_ = Acc();
    fan_cmd_ = std::max(0.0f, std::min(1.0f, s.fan));
    aoa_cmd_ = std::max(cfg_.aoa_min, std::min(cfg_.aoa_max, sweep_list_[0]));
    update_servo();
    state_ = State::SWEEP;
    tel_.state = state_;
    return "ok";
}

std::string Controller::cmd_stop() {
    fan_cmd_ = 0; fan_out_ = 0; hal_.set_fan(0);
    if (state_ != State::FAULT) state_ = State::IDLE;
    if (!sweep_done_) { sweep_done_ = true; sweep_i_ = -1; }
    tel_.state = state_;
    return "stopped";
}

std::string Controller::cmd_clear_faults() {
    SensorFrame f; hal_.read(f);
    if (f.estop_open) return "stop loop is open";
    tel_.faults = 0; state_ = State::IDLE; fan_cmd_ = 0; fan_out_ = 0; stall_timer_ = 0;
    last_client_ms_ = hal_.millis();
    tel_.state = state_;
    return "ok";
}

std::string Controller::cmd_light(bool on) { cfg_.led_on = on ? 1.0f : 0.0f; return "ok"; }

static void px(uint8_t *rgb, int i, float r, float g, float b, float k) {
    rgb[3 * i] = (uint8_t)(255 * std::min(1.0f, r * k)); rgb[3 * i + 1] = (uint8_t)(255 * std::min(1.0f, g * k));
    rgb[3 * i + 2] = (uint8_t)(255 * std::min(1.0f, b * k));
}

void Controller::led_frame(uint8_t *rgb) const {
    // Colours follow the Schreiber AI palette: cyan running, amber progress, red fault.
    float B = std::max(0.0f, std::min(1.0f, cfg_.led_brightness)) * (cfg_.led_on > 0.5f ? 1.0f : 0.0f);
    uint32_t t = hal_.millis();
    float phase = 0.5f + 0.5f * std::sin(t / 1000.0f * 2.0f * 3.14159f);     // 1 Hz breathing
    for (int i = 0; i < NUM_PIXELS; ++i) {
        if (state_ == State::FAULT) { float f = ((t / 250) % 2) ? 1.0f : 0.15f; px(rgb, i, 1.0f, 0.1f, 0.15f, B * f); }
        else if (taring_) px(rgb, i, 0.93f, 0.96f, 1.0f, B * (0.3f + 0.7f * phase));
        else if (state_ == State::SWEEP) {
            float prog = sweep_list_.empty() ? 0 : (float)sweep_i_ / sweep_list_.size();
            bool filled = (i + 0.5f) / NUM_PIXELS <= prog;
            if (filled) px(rgb, i, 1.0f, 0.78f, 0.43f, B); else px(rgb, i, 0.4f, 0.89f, 1.0f, B * 0.7f);
        }
        else if (state_ == State::RUNNING) px(rgb, i, 0.4f, 0.89f, 1.0f, B * (0.5f + 0.5f * fan_out_));
        else px(rgb, i, 0.55f, 0.7f, 0.85f, B * 0.35f);                        // idle: dim slate white
    }
}

std::string Controller::set_config(const std::string &k, float v) {
    struct { const char *n; float *p; } T[] = {
        {"m11", &cfg_.m11}, {"m12", &cfg_.m12}, {"m21", &cfg_.m21}, {"m22", &cfg_.m22},
        {"kq", &cfg_.kq}, {"p_station_pa", &cfg_.p_station_pa}, {"aoa_zero_deg", &cfg_.aoa_zero_deg},
        {"aoa_sign", &cfg_.aoa_sign}, {"servo_gain", &cfg_.servo_gain}, {"servo_offset_deg", &cfg_.servo_offset_deg},
        {"lift_limit_n", &cfg_.lift_limit_n}, {"drag_limit_n", &cfg_.drag_limit_n}, {"fan_slew_up", &cfg_.fan_slew_up},
        {"aoa_min", &cfg_.aoa_min}, {"aoa_max", &cfg_.aoa_max}, {"client_timeout_s", &cfg_.client_timeout_s},
        {"vbus_min_v", &cfg_.vbus_min_v}, {"stall_rpm", &cfg_.stall_rpm}, {"stall_grace_s", &cfg_.stall_grace_s},
        {"led_brightness", &cfg_.led_brightness}, {"led_on", &cfg_.led_on}};
    for (auto &t : T) if (k == t.n) { *t.p = v; return "ok"; }
    return "unknown key";
}

void Controller::update_servo() {
    hal_.set_servo_deg(cfg_.servo_offset_deg + cfg_.servo_gain * aoa_cmd_);
}

void Controller::update_fan(float dt) {
    if (fan_cmd_ > fan_out_) fan_out_ = std::min(fan_cmd_, fan_out_ + cfg_.fan_slew_up * dt);
    else fan_out_ = fan_cmd_;                 // down: immediate
    hal_.set_fan(fan_out_);
}

void Controller::apply_safety(const SensorFrame &f, float dt) {
    uint32_t now = hal_.millis();
    if (f.estop_open) fault(F_ESTOP);
    if (f.vbus_v < cfg_.vbus_min_v && fan_out_ > 0.05f) fault(F_VBUS_LOW);
    // fan stall: commanded on, no tach
    if (fan_out_ > 0.25f) {
        if (f.fan_rpm < cfg_.stall_rpm) stall_timer_ += dt; else stall_timer_ = 0;
        if (stall_timer_ > cfg_.stall_grace_s) fault(F_FAN_STALL);
    } else stall_timer_ = 0;
    // overload
    if (std::fabs(tel_.lift_n) > cfg_.lift_limit_n) fault(F_OVERLOAD_LIFT);
    if (std::fabs(tel_.drag_n) > cfg_.drag_limit_n) fault(F_OVERLOAD_DRAG);
    // stale sensors while running
    if (fan_out_ > 0.05f && last_lift_ms_ && (now - last_lift_ms_ > 1500 || now - last_drag_ms_ > 1500)) fault(F_SENSOR_STALE);
    // client watchdog: only when the fan runs and a client was ever seen
    if (fan_out_ > 0.05f && last_client_ms_ && cfg_.client_timeout_s > 0 &&
        (now - last_client_ms_) > (uint32_t)(cfg_.client_timeout_s * 1000)) fault(F_CLIENT_TIMEOUT);
}

void Controller::process_frame(const SensorFrame &f) {
    uint32_t now = hal_.millis();
    if (f.lift_ok) { tel_.lift_raw = f.lift_raw; last_lift_ms_ = now; }
    if (f.drag_ok) { tel_.drag_raw = f.drag_raw; last_drag_ms_ = now; }
    if (f.dp_ok) { dp_last_ = f.dp_pa; temp_last_ = f.temp_c; }
    if (f.aoa_ok) { aoa_last_ = f.aoa_raw_deg; aoa_seen_ = true; }
    rpm_last_ = f.fan_rpm; vbus_last_ = f.vbus_v;
    if (taring_) {
        if (f.lift_ok) { tare_sum_l_ += f.lift_raw; tare_n_l_++; }
        if (f.drag_ok) { tare_sum_d_ += f.drag_raw; tare_n_d_++; }
        if (f.dp_ok) { tare_sum_dp_ += f.dp_pa; tare_n_dp_++; }
        if (now - tare_start_ms_ >= 2000) {
            if (tare_n_l_) raw0_l_ = (int32_t)(tare_sum_l_ / tare_n_l_);
            if (tare_n_d_) raw0_d_ = (int32_t)(tare_sum_d_ / tare_n_d_);
            if (tare_n_dp_) dp0_ = (float)(tare_sum_dp_ / tare_n_dp_);
            taring_ = false; tared_ = (tare_n_l_ > 0 && tare_n_d_ > 0);
            hal_.log(tared_ ? "tare done" : "tare failed: no load cell data");
        }
    }
    float dl = (float)(tel_.lift_raw - raw0_l_), dd = (float)(tel_.drag_raw - raw0_d_);
    tel_.lift_n = cfg_.m11 * dl + cfg_.m12 * dd;
    tel_.drag_n = cfg_.m21 * dl + cfg_.m22 * dd;
    tel_.dp_pa = dp_last_ - dp0_;
    tel_.q_pa = cfg_.kq * tel_.dp_pa;
    tel_.temp_c = temp_last_;
    tel_.rho = cfg_.p_station_pa / (R_AIR * (temp_last_ + 273.15f));
    tel_.v_ms = tel_.q_pa > 0 ? std::sqrt(2.0f * tel_.q_pa / tel_.rho) : 0.0f;
    float a = aoa_last_ - cfg_.aoa_zero_deg;
    while (a > 180) a -= 360;
    while (a < -180) a += 360;
    tel_.aoa_deg = cfg_.aoa_sign * a;
    tel_.aoa_cmd = aoa_cmd_; tel_.fan_cmd = fan_cmd_; tel_.fan_out = fan_out_; tel_.fan_rpm = rpm_last_;
    tel_.vbus = vbus_last_; tel_.tared = tared_;
}

void Controller::sweep_step(float dt) {
    if (sweep_done_ || sweep_i_ < 0) return;
    sweep_timer_ += dt;
    // wait for the fan ramp and the settle time, then accumulate HX711 samples
    bool fan_ready = std::fabs(fan_out_ - fan_cmd_) < 1e-4f;
    if (sweep_settling_) {
        if (fan_ready && sweep_timer_ >= sweep_.settle_s) { sweep_settling_ = false; acc_ = Acc(); }
        return;
    }
    // accumulate once per new lift sample (the slowest sensor)
    static uint32_t last_seq = 0;
    if (tel_.seq == last_seq) return;
    last_seq = tel_.seq;
    acc_.sl += tel_.lift_n; acc_.sl2 += (double)tel_.lift_n * tel_.lift_n;
    acc_.sd += tel_.drag_n; acc_.sd2 += (double)tel_.drag_n * tel_.drag_n;
    acc_.sq += tel_.q_pa; acc_.sq2 += (double)tel_.q_pa * tel_.q_pa;
    acc_.sa += tel_.aoa_deg; acc_.sa2 += (double)tel_.aoa_deg * tel_.aoa_deg;
    acc_.st += tel_.temp_c; acc_.sr += tel_.fan_rpm; acc_.rl += tel_.lift_raw; acc_.rd += tel_.drag_raw;
    acc_.n++;
    if (acc_.n >= sweep_.samples) {
        SweepPoint p; double n = acc_.n;
        auto sd = [&](double s, double s2) { double v = s2 / n - (s / n) * (s / n); return (float)std::sqrt(std::max(0.0, v) * n / std::max(1.0, n - 1)); };
        p.aoa_cmd = sweep_list_[sweep_i_]; p.aoa_mean = (float)(acc_.sa / n); p.aoa_sd = sd(acc_.sa, acc_.sa2);
        p.fan_cmd = fan_cmd_; p.rpm_mean = (float)(acc_.sr / n);
        p.q_mean = (float)(acc_.sq / n); p.q_sd = sd(acc_.sq, acc_.sq2); p.temp_mean = (float)(acc_.st / n);
        p.rho = tel_.rho; p.v_mean = p.q_mean > 0 ? std::sqrt(2.0f * p.q_mean / p.rho) : 0.0f;
        p.lift_mean = (float)(acc_.sl / n); p.lift_sd = sd(acc_.sl, acc_.sl2);
        p.drag_mean = (float)(acc_.sd / n); p.drag_sd = sd(acc_.sd, acc_.sd2);
        p.lift_raw_mean = (int32_t)(acc_.rl / n); p.drag_raw_mean = (int32_t)(acc_.rd / n); p.n = (uint16_t)acc_.n;
        sweep_pts_.push_back(p);
        sweep_i_++;
        if (sweep_i_ >= (int)sweep_list_.size()) {
            sweep_done_ = true; sweep_i_ = -1; fan_cmd_ = 0; state_ = State::IDLE; hal_.log("sweep done");
        } else {
            aoa_cmd_ = std::max(cfg_.aoa_min, std::min(cfg_.aoa_max, sweep_list_[sweep_i_]));
            update_servo(); sweep_settling_ = true; sweep_timer_ = 0;
        }
    }
}

void Controller::tick() {
    uint32_t now = hal_.millis();
    float dt = last_ms_ ? (now - last_ms_) / 1000.0f : 1.0f / 100;
    last_ms_ = now;
    SensorFrame f; hal_.read(f);
    bool new_sample = f.lift_ok || f.drag_ok;
    process_frame(f);
    if (new_sample) {
        tel_.seq++; tel_.t_ms = now; tel_.state = state_;
        ring_[ring_head_] = tel_; ring_head_ = (ring_head_ + 1) % RING; if (ring_count_ < RING) ring_count_++;
    }
    apply_safety(f, dt);
    if (state_ != State::FAULT) { update_fan(dt); sweep_step(dt); }
    tel_.state = state_;
    hal_.set_led(state_ == State::FAULT ? ((now / 150) % 2) : (fan_out_ > 0.02f));
    if (now - led_last_ms_ >= 40) {                 // 25 Hz strip update
        led_last_ms_ = now;
        uint8_t rgb[NUM_PIXELS * 3]; led_frame(rgb); hal_.set_leds(rgb, NUM_PIXELS);
    }
}

// ---- serialisation -----------------------------------------------------------
static void jf(std::string &s, const char *k, double v, bool last = false) {
    char b[64]; if (std::isnan(v) || std::isinf(v)) v = 0; snprintf(b, sizeof b, "\"%s\":%.6g%s", k, v, last ? "" : ","); s += b;
}

std::string Controller::telemetry_json() const {
    std::string s = "{";
    const Telemetry &t = tel_;
    jf(s, "seq", t.seq); jf(s, "t_ms", t.t_ms);
    s += "\"state\":\""; s += state_name(t.state); s += "\",";
    s += "\"faults\":\""; s += fault_names(t.faults); s += "\",";
    jf(s, "fan_cmd", t.fan_cmd); jf(s, "fan_out", t.fan_out); jf(s, "fan_rpm", t.fan_rpm);
    jf(s, "aoa_cmd", t.aoa_cmd); jf(s, "aoa_deg", t.aoa_deg);
    jf(s, "lift_raw", t.lift_raw); jf(s, "drag_raw", t.drag_raw); jf(s, "lift_n", t.lift_n); jf(s, "drag_n", t.drag_n);
    jf(s, "dp_pa", t.dp_pa); jf(s, "q_pa", t.q_pa); jf(s, "v_ms", t.v_ms); jf(s, "temp_c", t.temp_c); jf(s, "rho", t.rho);
    jf(s, "vbus", t.vbus); jf(s, "tared", t.tared ? 1 : 0);
    jf(s, "sweep_i", sweep_done_ ? -1 : sweep_i_); jf(s, "sweep_n", sweep_done_ ? 0 : (double)sweep_list_.size());
    jf(s, "sweep_points", (double)sweep_pts_.size());
    uint8_t rgb[NUM_PIXELS * 3]; led_frame(rgb); s += "\"leds\":\"";
    char hx[8]; for (int i = 0; i < NUM_PIXELS; ++i) { snprintf(hx, sizeof hx, "%02x%02x%02x", rgb[3*i], rgb[3*i+1], rgb[3*i+2]); s += hx; }
    s += "\"}";
    return s;
}

std::string Controller::config_json() const {
    std::string s = "{"; const Config &c = cfg_;
    jf(s, "m11", c.m11); jf(s, "m12", c.m12); jf(s, "m21", c.m21); jf(s, "m22", c.m22); jf(s, "kq", c.kq);
    jf(s, "p_station_pa", c.p_station_pa); jf(s, "aoa_zero_deg", c.aoa_zero_deg); jf(s, "aoa_sign", c.aoa_sign);
    jf(s, "servo_gain", c.servo_gain); jf(s, "servo_offset_deg", c.servo_offset_deg);
    jf(s, "lift_limit_n", c.lift_limit_n); jf(s, "drag_limit_n", c.drag_limit_n); jf(s, "fan_slew_up", c.fan_slew_up);
    jf(s, "aoa_min", c.aoa_min); jf(s, "aoa_max", c.aoa_max); jf(s, "client_timeout_s", c.client_timeout_s);
    jf(s, "vbus_min_v", c.vbus_min_v); jf(s, "stall_rpm", c.stall_rpm); jf(s, "stall_grace_s", c.stall_grace_s);
    jf(s, "led_brightness", c.led_brightness); jf(s, "led_on", c.led_on, true);
    return s + "}";
}

std::string Controller::samples_json(uint32_t since) const {
    std::string s = "[";
    bool first = true;
    for (int i = 0; i < ring_count_; ++i) {
        const Telemetry &t = ring_[(ring_head_ - ring_count_ + i + RING) % RING];
        if (t.seq <= since) continue;
        if (!first) s += ",";
        first = false;
        s += "{"; jf(s, "seq", t.seq); jf(s, "t_ms", t.t_ms); jf(s, "lift_n", t.lift_n); jf(s, "drag_n", t.drag_n);
        jf(s, "q_pa", t.q_pa); jf(s, "aoa_deg", t.aoa_deg); jf(s, "fan_rpm", t.fan_rpm, true); s += "}";
    }
    return s + "]";
}

static const char *CSV_HEADER =
    "point,aoa_cmd_deg,aoa_deg,aoa_sd_deg,fan_cmd,fan_rpm,q_pa,q_sd_pa,v_ms,temp_c,rho_kgm3,"
    "lift_n,lift_sd_n,drag_n,drag_sd_n,lift_raw,drag_raw,n\n";

std::string Controller::sweep_csv() const {
    std::string s = CSV_HEADER; char b[320]; int i = 0;
    for (const auto &p : sweep_pts_) {
        snprintf(b, sizeof b, "%d,%.3f,%.3f,%.3f,%.3f,%.0f,%.3f,%.3f,%.3f,%.2f,%.4f,%.6f,%.6f,%.6f,%.6f,%ld,%ld,%u\n",
                 i++, p.aoa_cmd, p.aoa_mean, p.aoa_sd, p.fan_cmd, p.rpm_mean, p.q_mean, p.q_sd, p.v_mean, p.temp_mean,
                 p.rho, p.lift_mean, p.lift_sd, p.drag_mean, p.drag_sd, (long)p.lift_raw_mean, (long)p.drag_raw_mean, p.n);
        s += b;
    }
    return s;
}

std::string Controller::sweep_json() const {
    std::string s = "["; bool first = true;
    for (const auto &p : sweep_pts_) {
        if (!first) s += ",";
        first = false; s += "{";
        jf(s, "aoa_cmd", p.aoa_cmd); jf(s, "aoa_deg", p.aoa_mean); jf(s, "aoa_sd", p.aoa_sd); jf(s, "fan_cmd", p.fan_cmd);
        jf(s, "fan_rpm", p.rpm_mean); jf(s, "q_pa", p.q_mean); jf(s, "q_sd", p.q_sd); jf(s, "v_ms", p.v_mean);
        jf(s, "temp_c", p.temp_mean); jf(s, "rho", p.rho); jf(s, "lift_n", p.lift_mean); jf(s, "lift_sd", p.lift_sd);
        jf(s, "drag_n", p.drag_mean); jf(s, "drag_sd", p.drag_sd); jf(s, "n", p.n, true); s += "}";
    }
    return s + "]";
}
