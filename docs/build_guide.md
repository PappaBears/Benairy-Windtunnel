# Build and wiring guide

Benairy desktop wind tunnel · Schreiber AI

Read the full guide before you start. Follow the steps in order.

## 1. Print the parts

Print settings: 0.4 mm nozzle, 0.2 mm layers, 3 walls, 15 % infill. Use PETG for the duct. Use PLA or PETG for the balance parts. Each part fits a 256 x 256 x 256 mm bed. `cad/check_report.md` lists the print orientation, the size, and the support need of every part.

| Part | Qty | Note |
|---|---|---|
| bellmouth_quarter | 4 | Flat face down. |
| settling_chamber | 1 | Open end up. |
| honeycomb | 1 | 853 cells. Set 2 walls and no infill. About 9 hours. Or fill `spacer_28` with 6 mm drinking straws cut to 36 mm and skip this part. |
| screen_frame | 2 | Glue the mesh on one face. |
| spacer_12 | 2 | |
| spacer_28 | 1 | |
| contraction_1, contraction_2 | 1 each | Large end down. |
| test_section_1, test_section_2 | 1 each | Stand on a flange. |
| window_clip | 2 | |
| diffuser | 1 | Fan plate up. |
| fan_guard | 1 | Fan cowl with exit grille. Open side up. |
| balance_bay | 1 | Open side up. Supports under the stop fingers. |
| platform, bracket, drum | 1 each | Supports as noted in the check report. |
| strut_long, strut_short | 1 each | Vertical, with a brim. |
| wing_naca0012, wing_naca4412, wing_flat_plate | 1 each | Upside down. Supports only in the socket. |
| car_tray, ground_board | 1 each | |
| stand_settling, stand_test_section, stand_fan | 1 each | |
| tap_barb | 6 | |
| pitot_wand, probe_plug, zero_gauge | 1 each | |
| electronics_box, electronics_lid | 1 each | |
| cam_clip | 1 | Optional. |

Check the printed load cell pockets before you continue. Measure your load cells. If they are not 45 x 6.4 x 6.4 mm with M2 holes at 4.5 and 10.5 mm from each end, change `cell_L`, `cell_w`, `cell_t`, and `cell_holes` in `cad/benairy_cad.py` and print the platform, bracket, and bay again.

## 2. Assemble the duct

1. Glue the mesh on the two screen frames. Pull it tight. Trim the edge.
2. Push the stack into the settling chamber from the upstream end, in this order: screen frame, spacer 12, screen frame, spacer 12, honeycomb, spacer 28. The last screen must touch the lip at the downstream end.
3. Bolt the four bellmouth quarters to the settling chamber with M3 x 12 screws. This clamps the stack.
4. Bolt the segments together in order: settling chamber, contraction 1, contraction 2, test section 1, test section 2, diffuser. Use M3 x 12 screws and nuts at each flange. Put a bead of silicone or a strip of foam tape on each flange face.
5. Glue a tap barb over each 1.2 mm hole: three on test section 1 at 20 mm, one on the contraction inlet at the top, one on test section 2 at the model station. Use thick CA glue. Keep the glue out of the hole.
6. Cut two window sheets 100 x 74 mm. Push each into its recess. Put four magnets in the wall pockets and four in each window clip. Check that the poles attract. Put the clips on.
7. Cut two WS2812B strips of 12 LEDs. Stick one in each light bar on top of test section 2, LEDs facing down. Solder the data out of the first bar to the data in of the second. Lead the three wires out through the notch at the downstream end. The 1 mm printed floor under the strip is the diffuser: print test section 2 in natural or white PETG for the most light, or in a dark colour for a dimmer, more even glow.
8. Put the fan in the cowl. The fan label faces the grille. Put the cowl with the fan on the diffuser plate. Fix it with four M4 x 50 screws through the grille face, the fan, and the plate. The air must flow out of the tunnel.
9. Put the stands under the settling chamber, under test section 1, and under the fan plate. The balance bay is the fourth support.

WARNING: Do not run the fan without the guard. The fan turns at 8000 rpm.

## 3. Assemble the balance

1. Bolt the drag cell to the bay post with two M2 x 6 screws. The cell stands vertically. Its free end points up. Its cable exits at the lower end.
2. Bolt the bracket to the top of the drag cell with two M2 screws. The arm points toward the tunnel centre.
3. Bolt the lift cell under the bracket arm with two M2 screws from above. The free end points to the -y side (the side with the overload stops).
4. Bolt the platform foot on the free end of the lift cell with two M2 screws from above.
5. Check the gaps. The platform must not touch the stop fingers, the bay, or the bracket. Move the platform by hand. It must move freely by about 0.5 mm in each direction and then touch a stop.
6. Fix the servo in the hanger with two M2 screws through the tabs. The output shaft points toward the tunnel centre.
7. Screw a single-arm servo horn to the servo. Press the horn into the pocket on the drum. Push the drum stub axle into the bushing boss. Set the servo to its centre position before you fix the horn: use the dashboard "Set angle" at 0 degrees.
8. Press the angle magnet into the stub end. Fix the AS5600 board on the sensor post with two M2 screws or glue. The chip faces the magnet. The gap is 1 to 2 mm.
9. Route the three servo wires and the four lift-cell wires in a loose loop to the bay wall. Use thin silicone wire (30 AWG). Tape the loop to the wall so it cannot touch the platform.
10. Bolt the bay under test section 2 with four M3 x 12 screws through the floor.
11. Put the strut tongue in the drum socket. Push a 1.5 mm pin through the pin hole. Cut the pin flush.

## 4. Electronics

Put the ESP32 and the two HX711 boards in the electronics box. Keep the HX711 boards close to the load cells. Keep the HX711 cables away from the fan cable.

### Wiring table

| ESP32 pin | Connect to | Note |
|---|---|---|
| GPIO 25 | 2N7000 gate through 1 kΩ | Fan PWM, 25 kHz |
| 2N7000 drain | Fan PWM wire (blue) | Open drain. The fan has its own pull-up. |
| 2N7000 source | GND | Common ground with the 12 V supply |
| GPIO 26 | Fan tach wire (green or yellow) | Add a 10 kΩ pull-up to 3.3 V |
| GPIO 27 | Servo signal (orange) | |
| 5 V (USB) | Servo + (red), HX711 VCC, AS5600 VCC | Power the ESP32 from a 5 V USB charger of at least 2 A |
| 3.3 V | SDP810 VDD, AS5600 VCC if the board is 3.3 V only | Check your AS5600 board |
| GPIO 21 | SDP810 SDA, AS5600 SDA | 4.7 kΩ pull-ups to 3.3 V if the boards have none |
| GPIO 22 | SDP810 SCL, AS5600 SCL | |
| GPIO 32, 33 | HX711 lift: DT, SCK | |
| GPIO 34, 14 | HX711 drag: DT, SCK | GPIO 34 is input only, which is fine for DT |
| GPIO 4 | Stop switch loop to GND | Normally closed. Open = stop. Use a mushroom button or a wire link. |
| GPIO 13 | LED strip data in, through 330 Ω | Two 12-LED WS2812B bars in series. 5 V and GND from the USB supply, 1000 µF capacitor across the strip supply. |
| GPIO 35 | 12 V bus through 47 kΩ / 10 kΩ divider | Reads the fan supply |
| GND | All grounds, including the 12 V supply negative | One star point |

Fan power: connect the 12 V supply to the fan red and black wires directly. The ESP32 only switches the PWM wire.

Load cell colours (most bar cells): red = E+, black = E-, white = A-, green = A+. If a reading goes the wrong way, swap white and green.

CAUTION: The HX711 boards and the SDP810 are static sensitive. Touch a grounded object before you handle them.

### Pressure tubing

* SDP810 port + : the contraction inlet tap.
* SDP810 port - : the three test-section static taps joined with a T.
* Pitot wand: push it through the top hole at the model station. Connect its barb to port + and the model-station static tap to port - for the `kq` calibration only.

## 5. Firmware

The firmware is in `firmware/`. It needs the Arduino framework for the ESP32 and no external libraries.

With PlatformIO:

```bash
cd firmware
pio run -t upload
```

With the Arduino IDE: create a sketch folder named `benairy`, copy the files from `firmware/src` into it, rename `main.cpp` to `benairy.ino`, select your ESP32 board, and upload.

Before you build, run `python3 tools/embed_dashboard.py` if you changed the dashboard. It regenerates `firmware/src/dashboard_html.h`.

The controller starts a Wi-Fi access point named `Benairy` with password `windtunnel`. Open `http://192.168.4.1`. Change both in `firmware/src/config.h`.

The firmware was built and tested on the host (`firmware/test_host`, 10 tests). The ESP32 cross-compile was not run in the Schreiber AI build environment. If the first upload fails to compile, the likely cause is the LEDC API version: the file selects the API by the Arduino core version in `main.cpp`. Report the compiler message.

## 6. First power-on checks

1. Power the ESP32 only. Join the access point. Open the dashboard. The state shows IDLE.
2. Press lightly on the platform. The lift tile and the drag tile must change. Note which direction is positive.
3. Press "Set angle" at 0, 10, and -10 degrees. The strut must move about 20 degrees between the end points. If it moves the wrong way, set `aoa_sign` to -1 in the settings.
4. Put the zero gauge on the floor against the strut. Press "Set angle zero".
5. Connect the 12 V supply. Set the fan to 30 %. The fan tile must show about 2400 rpm within 2 seconds. If it shows 0, check the tach pull-up. The firmware stops the fan after 3 seconds without a tach signal.
6. Open the stop loop. The state must change to FAULT and the fan must stop at once. The light bars flash red.
7. Check the lighting: dim white in IDLE, cyan when the fan runs, amber filling along the bars during a sweep. Set the brightness in the dashboard. Keep it at or below 60 % if the ESP32 runs from a 2 A USB supply.
