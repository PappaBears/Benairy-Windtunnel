// Benairy controller: pins and limits. Change the pins here only.
#pragma once

// ---- ESP32 pins (ESP32-WROOM DevKit) ----------------------------------------
#define PIN_FAN_PWM      25   // to 2N7000 gate -> fan PWM wire (open drain), 25 kHz
#define PIN_FAN_TACH     26   // fan tach (open collector), pull-up to 3V3
#define PIN_SERVO        27   // MG90S signal, 50 Hz
#define PIN_HX_LIFT_DT   32   // HX711 lift DOUT
#define PIN_HX_LIFT_SCK  33   // HX711 lift PD_SCK
#define PIN_HX_DRAG_DT   34   // HX711 drag DOUT (input only pin is fine)
#define PIN_HX_DRAG_SCK  14   // HX711 drag PD_SCK
#define PIN_I2C_SDA      21   // SDP810 + AS5600
#define PIN_I2C_SCL      22
#define PIN_ESTOP        4    // normally closed loop to GND; open = stop (internal pull-up)
#define PIN_VBUS_ADC     35   // 12 V bus through 47k/10k divider (12 V -> 2.1 V)
#define PIN_STATUS_LED   2
#define PIN_LED_STRIP    13   // WS2812B data through 330 ohm; two bars of 12 LEDs in series
#define NUM_LEDS         24

// ---- I2C addresses -----------------------------------------------------------
#define ADDR_SDP810      0x25
#define ADDR_AS5600      0x36

// ---- control loop ------------------------------------------------------------
#define TICK_HZ          100
#define FAN_PWM_HZ       25000
#define FAN_PWM_BITS     10
#define FAN_TACH_PULSES_PER_REV 2

// ---- default safety limits (changeable from the dashboard, stored in NVS) ----
#define DEF_LIFT_LIMIT_N    1.50f   // 200 g cell: stop the fan above this
#define DEF_DRAG_LIMIT_N    0.80f   // 100 g cell
#define DEF_FAN_SLEW_UP     0.25f   // fraction per second
#define DEF_AOA_MIN_DEG   -30.0f
#define DEF_AOA_MAX_DEG    30.0f
#define DEF_CLIENT_TIMEOUT_S 10.0f  // no dashboard poll for this long -> fan off
#define DEF_VBUS_MIN_V     10.5f
#define DEF_STALL_RPM      300.0f
#define DEF_STALL_GRACE_S   3.0f

// ---- Wi-Fi: the controller starts an access point. Join it, open http://192.168.4.1
#define WIFI_AP_SSID     "Benairy"
#define WIFI_AP_PASS     "windtunnel"
