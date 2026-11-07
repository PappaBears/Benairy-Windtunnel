# Aerodynamic design

Benairy desktop wind tunnel · Schreiber AI

This document explains the design choices. The numbers come from `tools/design_calcs.py`. Run the script to update `docs/generated/design_numbers.md` after you change a parameter.

## Layout

The tunnel is an open-circuit suction tunnel. Air enters through a bellmouth, passes a honeycomb and two screens, speeds up in a 4:1 contraction, flows through the test section, slows down in a short diffuser, and leaves through the fan. The fan is downstream of the test section. This keeps the fan swirl out of the test section.

| Station | Size | Length | Printed part |
|---|---|---|---|
| Bellmouth | 200 x 200 mm opening, 22 mm lip radius | 22 mm | 4 x `bellmouth_quarter` |
| Settling chamber | 200 x 200 mm | 100 mm | `settling_chamber` with the honeycomb and screen stack |
| Contraction | 200 x 200 to 100 x 100 mm, 5th-order polynomial | 200 mm | `contraction_1`, `contraction_2` |
| Test section | 100 x 100 mm | 250 mm | `test_section_1`, `test_section_2` |
| Diffuser | 100 x 100 mm square to 116 mm round | 150 mm | `diffuser` |
| Fan and guard | 120 mm frame | 44 mm | fan, `fan_guard` |

Total length is about 790 mm. The balance bay under the test section is 80 mm deep.

## Speed prediction

The fan curve is modelled as a quadratic from 37 mmH2O at zero flow to zero pressure at 220 CFM. The tunnel loss coefficients are referenced to the test-section dynamic pressure. The exit loss is the largest term because there is no exit diffuser after the fan.

| Quantity | Value |
|---|---|
| Total loss coefficient | 1.63 |
| Operating point | 0.091 m³/s (194 CFM), 82 Pa |
| Test-section speed | 9.1 m/s |
| Dynamic pressure | 50 Pa |

Expect 8 to 10 m/s. The uncertainty is mostly the fan curve: axial fans have a stall dip at mid flow that the quadratic model does not show. Measure the real speed with the pitot wand before you trust the prediction.

## Flow quality

The honeycomb has 6 mm cells, 0.5 mm walls, and 36 mm length (length to cell ratio 6). Two screens follow it. The contraction ratio of 4 reduces axial turbulence by about a factor of 4 and the screens add another factor of about 1.7. Expect a turbulence intensity near 1 % in the test section. This is good for a printed tunnel but it is not a low-turbulence facility. Transition on the models will happen earlier than in free flight.

The floor boundary layer at the model station is 3 to 7 mm thick. The raised ground board for car tests starts a new boundary layer 45 mm upstream of the car.

## Models and forces

| Model | Reynolds number | Lift | Drag | Blockage |
|---|---|---|---|---|
| Wing 80 x 35 mm, NACA 0012 | 21 000 (chord) | 11.5 gf at CL 0.8 | 0.6 to 3.6 gf | 7 % at 15 deg |
| 1:64 car, 75 x 29 x 24 mm | 45 000 (length) | 0.6 gf at CL 0.2 | 1.5 gf at CD 0.5 | 6 % |
| Strut, airfoil section 14 x 4.5 mm | | | 0.06 gf | 2 % |

The Reynolds numbers are low. Wing polars will show laminar separation, a lift slope below the thin-airfoil value, and an early stall near 10 to 12 degrees. This is correct physics for this scale, not a tunnel fault. Compare your data with low-Reynolds-number references, not with full-scale data.

## Force balance

The balance is an external two-component balance under the floor.

* The **drag cell** (100 g) stands vertically. Its lower end is bolted to the bay. Its upper end carries the bracket.
* The **lift cell** (200 g) lies horizontally across the flow. Its fixed end hangs under the bracket arm. Its free end carries the metric platform.
* The **platform** carries the pitch drum, the servo, the angle sensor, the strut, and the model.

Bar load cells reject moments to first order, so the position of the force along the strut does not change the reading. Cross-talk between the two axes is calibrated out with a 2 x 2 matrix. Overload stops limit the platform travel to 0.6 mm in each direction.

Why these cells: the drag of a 1:64 car is about 1.5 gf. A 100 g cell with an HX711 resolves 0.01 g after one second of averaging, so the drag reading has about 1 % noise. The lift cell must carry the platform, the servo, and the model (up to 90 g in the car configuration), so it is a 200 g cell. Its resolution is 0.1 g, which is 1 % of the wing lift.

| Error source | Drag cell (100 g) | Lift cell (200 g) |
|---|---|---|
| Noise after 1 s average | 0.010 g | 0.010 g |
| Non-linearity (0.05 % of full scale) | 0.050 g | 0.100 g |
| Creep, half remains after tare | 0.015 g | 0.030 g |
| Combined, 1 sigma | 0.053 g | 0.105 g |

A multi-point calibration over the real force range reduces the non-linearity term by about a factor of 3. The `tools/calibrate.py` fit reports the residuals so you know what you achieved.

## Angle of attack

The strut is fixed to a pitch drum. The drum turns on the servo shaft. The model pitches about the drum axis, which is 63 mm below the floor. The model therefore moves along an arc: 16 mm streamwise at 15 degrees. This is accepted in a 250 mm test section. The gain is a direct angle measurement: the AS5600 sensor reads the drum shaft, so servo backlash does not enter the data. Expect 0.1 degree resolution and 0.3 degree systematic uncertainty from the zero setting and strut flex.

## Dynamic pressure

The dashboard reads q from the pressure difference between the contraction inlet taps and the test-section static ring. The ideal ratio q / Δp is 1.067 for a 4:1 contraction (`kq` in the settings). Calibrate `kq` once with the pitot wand at the model station. The SDP810 has 0.01 Pa resolution and about 3 % span accuracy, so q is known to 3 % and speed to 1.5 %.

## Tares and corrections

1. **Wind-off tare** with the model installed, at each angle of the sweep. Removes the zero and the cable spring.
2. **Strut tare**: a wind-on sweep without the model. Removes the strut drag, scaled by the q ratio.
3. **Wall corrections** (closed test section, Barlow, Rae and Pope): solid blockage from the model volume, wake blockage from CD, streamline curvature on α and CD. For cars the Maskell correction is used. At this size the total correction is 1 to 2 % on q and up to 1.3 degrees on α at CL 0.6.

The simulator produces in-tunnel forces with these effects built in, and the analysis recovers the free-air truth within 1 %. On the real tunnel, the corrections themselves carry perhaps 30 % uncertainty, which is small against the 3 % q uncertainty.
