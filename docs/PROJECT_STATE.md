# Project state

Benairy desktop wind tunnel · Schreiber AI · Product mode

## Brief

Operator: an aerospace test engineer who prints at home. Job: measure lift and drag on small printed wings and 1:64 die-cast cars on a desktop. Constraints: under 100 dollars of purchased parts, every printed part fits a 256 mm bed, use the owned ESP32 boards and magnets where they make sense. First successful experience: run the simulation, then print, build, calibrate, and run Experiment 1 of the test guide.

## Scope

* Parametric CAD (`cad/benairy_cad.py`, CadQuery and FreeCAD backends), STL and STEP output, printability and interference checks, renders.
* Aerodynamic design calculations (`tools/design_calcs.py`, `docs/design.md`).
* ESP32 firmware with a portable controller core, host unit tests.
* Web dashboard served by the controller and by the simulation server.
* Analysis tools: calibration fit, tares, wall corrections, polar plots with uncertainty.
* Simulation server for use without hardware; simulated end-to-end test.
* Parts list, build and wiring guide, test guide.

## Decisions

| Decision | Why |
|---|---|
| Suction tunnel, fan downstream | Clean test-section flow, one fan, simple exit guard. |
| 100 x 100 mm test section at about 9 m/s | Blockage of a 1:64 car stays near 6 %. One ARCTIC S12038-8K fan at 16 dollars. |
| Pitch drum under the floor on the servo shaft, AS5600 on the drum | Direct angle measurement with no linkage slop. The model arc of 16 mm at 15 degrees is accepted. |
| 100 g drag cell, 200 g lift cell | 0.01 g drag resolution for 1.5 gf of car drag; the lift cell carries 90 g of platform and car. |
| SDP810-125Pa instead of a cheap analog sensor | 0.01 Pa resolution and low drift; q is the largest error term, so it gets the best sensor. The MPXV7002 supply chain is unreliable. |
| HTTP polling, no WebSocket library | No external firmware dependencies; 10 SPS data does not need more. |
| 2 mm duct walls, arch stands | Keeps the filament near 2.5 kg. |

## Current reality (7 November 2026)

* CAD generated, checked, and rendered with the CadQuery backend. 38 printed parts plus reference envelopes. No interference between parts in any test configuration.
* Firmware controller core passes 10 host tests. The ESP32 cross-compile was not run here (no toolchain allowed in the build environment).
* Dashboard inspected at 1400 px and 390 px against the simulator, no console errors. Lighting controls and strip preview added.
* 10 automated tests pass: analysis, calibration fit, host firmware tests, simulated end-to-end run with fault paths.
* Example data and example analysis output in `data/examples`.

## Checkpoint

Branch `main` on `PappaBears/Benairy-Windtunnel`. Test command: `python3 -m pytest -q tests`.

## Blockers

None. The FreeCAD backend and the ESP32 build need the operator's machine.

## Next exact action

Print `platform`, `bracket`, `drum`, and `balance_bay` first. Check the load cell fit. Then print the duct.
