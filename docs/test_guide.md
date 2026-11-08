# Test guide

Benairy desktop wind tunnel · Schreiber AI

This guide gives the calibration procedures and six experiments. Do the calibrations first. Do them again after you move the tunnel or change a model mount.

## Safety rules

WARNING: Keep fingers, hair, and loose items away from the fan exit. The guard stops fingers, not long hair or cables.

CAUTION: Never push on the model with the fan running. The overload stops protect the cells against 0.6 mm of travel, not against a hard push.

* The dashboard `STOP FAN` button and the `Esc` key stop the fan.
* The fan stops by itself if the dashboard stops polling for 10 seconds, if a load cell reads above its limit, if the tach signal is lost, or if the stop loop opens.

## Calibration 1: balance

Tools: a set of calibration masses (1, 2, 5, 10, 20 g), thread, a small pulley or a smooth rod clamped to the tunnel exit.

1. Install the long strut and the NACA 0012 wing. Fan off.
2. Set the angle to 0. Press "Tare".
3. Hang the masses from the wing centre, one at a time, up to 20 g. Record the lift and drag raw counts from the Live data tiles after 10 seconds at each step. Record a zero reading between each step.
4. Tie the thread to the wing, pass it over the pulley downstream, and hang the same masses. Record the raw counts.
5. Pull in the lift direction with 20 g and read the drag channel. Pull in the drag direction with 20 g and read the lift channel. These rows measure the cross-talk.
6. Put the rows in a CSV file with the columns `applied_lift_g, applied_drag_g, lift_raw, drag_raw`. Lift up and drag downstream are positive. Masses hung from the wing are negative lift.
7. Run:

```bash
python3 tools/calibrate.py my_calibration.csv --out cal_out
```

8. Enter the four `m` values in the dashboard Settings. Check: hang 10 g and read 98 mN of lift.

Accept the calibration when the residual RMS is below 0.5 mN and the cross-talk is below 3 %. A larger cross-talk means the lift cell is not square to the drag cell. Loosen the bracket screws, square it, and tighten.

## Calibration 2: angle zero

1. Put the zero gauge on the floor against the flat face of the strut. The strut is vertical when the gauge touches it along its full height.
2. Press "Set angle zero".
3. Command +10 and -10 degrees. Check with the gauge turned by 10 degrees on a printed wedge, or with a phone inclinometer on the wing. Set `aoa_sign` to -1 if the sign is wrong.

## Calibration 3: dynamic pressure factor kq

1. Remove the model and the strut. Push the probe plug out of the top hole. Push the pitot wand in until its collar sits on the wall. The head points upstream.
2. Connect the wand to the sensor + port and the model-station static tap to the - port.
3. Fan off: press "Tare".
4. Run the fan at 40, 60, 80, and 100 %. Record q at each step. This q is the true dynamic pressure at the model station because `kq` only scales the reading.
5. Move the tubing back to the contraction taps. Repeat the four fan settings. Record q again.
6. Set `kq` = (pitot q) / (tap q) averaged over the four points. Expect 1.0 to 1.15. Record the standard deviation of the four ratios. It is your `kq` uncertainty.

## Calibration 4: speed check and fan map

Record q against fan percent from 20 to 100 % in steps of 10. Keep the table. It is the fan map for the test plan. Compare the speed at 100 % with the prediction of 9.1 m/s. Record the difference in your log.

## Tare procedure for every run

1. Install the model. Fan off. Press "Tare".
2. Run a sweep with Fan = 0 over the angle list of the test. Download it as the tare file.
3. Run a sweep without the model (strut only) at the test fan setting. Download it as the strut file. Do this once per fan setting.
4. Run the test sweep. Download it as the run file.
5. Analyze:

```bash
python3 tools/analyze.py --run run.csv --tare tare.csv --strut strut.csv --out results
```

## Experiment 1: NACA 0012 lift curve and drag polar

Model: `wing_naca0012`. Angles: -6 to 16 in steps of 2. Fan: 80 %. Samples: 40. Tick "up and down".

What to expect: lift slope 0.06 to 0.08 per degree, stall at 10 to 13 degrees, CD min 0.03 to 0.05. The up and down legs show hysteresis around stall. That is real at this Reynolds number.

What to report: the fit slope with its standard error, alpha zero, CD min, and the maximum L/D with k = 2 uncertainty from `summary.json`.

## Experiment 2: camber effect

Models: `wing_naca0012` and `wing_naca4412`. Same sweep. Plot both lift curves together.

What to expect: the 4412 curve is shifted up by about 0.3 in CL and alpha zero is near -3 to -4 degrees. The slopes are similar.

## Experiment 3: flat plate at low Reynolds number

Model: `wing_flat_plate`. Angles: -4 to 20 in steps of 2.

What to expect: a thin flat plate often has a higher CL max than the NACA 0012 at Re 20 000, with a gentle stall. This is a well-known low Reynolds number result and a good check of the tunnel.

## Experiment 4: Reynolds number sweep

Model: `wing_naca0012` at 6 degrees. Fan: 40, 55, 70, 85, 100 %. Record CL and CD at each speed.

What to expect: CL rises and CD falls with speed as the laminar separation bubble shrinks. Plot CL and CD against Re. Include the q uncertainty bars: at 40 % the q uncertainty dominates.

## Experiment 5: 1:64 car drag

Models: three die-cast cars with different shapes. Install the short strut, the ground board, and the car tray. Fan: 100 %. Angles: 0 only, 5 repeats of 60 samples.

Do the tare with the empty tray on the strut (wind off and wind on). Use `--kind bluff --area <frontal area>` in the analysis. Measure the frontal area from a photo against a grid.

What to expect: CD 0.4 to 0.7 for most toy cars. A smooth sports car shape gives the lower values. Open wheels add drag.

What to report: CD with k = 2 uncertainty. The repeat scatter tells you the repeatability of the tray mount. Remount the car between repeats.

## Experiment 6: ride height and rake

Model: one car. Set `aoa_min` to -3 and `aoa_max` to 3 in the dashboard settings first: the tray ends touch the ground board beyond 3 degrees (see `cad/sweep_report.md`). Pitch the tray by -3, 0, and +3 degrees with the angle command.

What to expect: nose-down rake lowers lift and often lowers drag a little. The effect is small at this scale. This experiment shows the resolution limit of the balance: compare the differences with the k = 2 bars.

## Repeatability test

Run Experiment 1 three times on three days. Plot the three lift curves together. The spread at 6 degrees is your long-term repeatability. Put it in the test log. If it is larger than the k = 2 bars, the uncertainty budget in `tools/benairy_analysis.py` needs larger Type B terms.

## Known limits

| Limit | Effect | What to do |
|---|---|---|
| Model moves on an arc with angle | 16 mm streamwise at 15 degrees | Keep the model in the window centre at 0 degrees. |
| Wind-off tare does not remove weight shift | None for a rigid mount | Check the tare file: lift must be constant with angle within 1 mN. |
| Cable spring | A small offset that changes with angle | The wind-off tare per angle removes it. Use loose loops. |
| Turbulence near 1 % | Earlier transition than free flight | Compare with low-turbulence data with care. |
| q accuracy 3 % | 3 % on all coefficients | Calibrate `kq` with the pitot wand. Report the k = 2 bars. |
