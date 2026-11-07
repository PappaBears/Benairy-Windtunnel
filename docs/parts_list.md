# Parts list

Benairy desktop wind tunnel · Schreiber AI

All prices are in US dollars for one unit. The **Confirmed** column says how the price was checked on 7 November 2026. "Listing" means a live retailer listing was found by web search. "Typical" means the usual marketplace price; check it before you order.

## Purchased parts

| # | Part | Qty | Unit price | Line | Confirmed | Source and note |
|---|---|---|---|---|---|---|
| 1 | ARCTIC S12038-8K fan, 120 x 120 x 38 mm, PWM, 12 V 2.2 A, 220 CFM, 37 mmH2O | 1 | 15.99 | 15.99 | Listing | Newegg single-fan listing. Also sold as a 3-pack for 42.99. |
| 2 | Sensirion SDP810-125Pa differential pressure sensor, I2C, ±125 Pa | 1 | 30.86 | 30.86 | Listing | Digi-Key part 1649-1073-ND. Mouser 403-SDP810-125PA is about 34.72. |
| 3 | Mini bar load cell, 100 g (drag) | 1 | 7.00 | 7.00 | Typical | Generic aluminium bar cell, 45 x 6.4 x 6.4 mm class. SparkFun TAL221 100 g is 14.50 (listing). |
| 4 | Mini bar load cell, 200 g (lift) | 1 | 7.00 | 7.00 | Typical | Same family. If you can only find 100 g and 500 g, use 500 g for lift. |
| 5 | HX711 load cell amplifier module | 2 | 2.50 | 5.00 | Typical | Sold in packs of 5 for about 8. SparkFun single board is 4.95 (listing). |
| 6 | AS5600 magnetic angle sensor module | 1 | 3.00 | 3.00 | Typical | Needs a diametric magnet: see the magnet note below. |
| 7 | MG90S metal-gear micro servo | 1 | 2.50 | 2.50 | Listing | Walmart 4-pack 9.98. Spares are useful. |
| 8 | 12 V 5 A power supply, barrel plug | 1 | 12.00 | 12.00 | Typical | 60 W class. A listing for the Alitove brand was 25.99; generic units are cheaper. |
| 9 | 2N7000 MOSFET, 10 kΩ and 1 kΩ resistors | 1 | 1.00 | 1.00 | Typical | Fan PWM level shift. |
| 10 | Silicone tubing, 2 mm ID, 2 m | 1 | 4.00 | 4.00 | Typical | Pressure taps to the sensor. |
| 11 | Nylon tulle or window screen, 2 pieces 200 x 200 mm | 1 | 2.00 | 2.00 | Typical | Turbulence screens. |
| 12 | Clear PET or acrylic sheet, 1 mm, 2 pieces 100 x 74 mm | 1 | 0.00 | 0.00 | — | Cut from packaging. Acrylic from a hardware store is about 4. |
| 13 | M3 screws and nuts (about 60), M2 x 6 screws (12), M4 x 50 screws and nuts (4) | 1 | 6.00 | 6.00 | Typical | Skip if you own a hardware assortment. |
| 14 | Music wire, 1.5 mm, 300 mm (joint pins) | 1 | 2.00 | 2.00 | Typical | Hobby shop. A paper clip also works. |
| | **Total** | | | **98.35** | | Confirmed listings: 49.35. Typical: 49.00. |

## Parts you already own

| Part | Where it is used | Why it makes sense |
|---|---|---|
| ESP32 DevKit | Controller: fan PWM, servo, 2 x HX711, I2C sensors, Wi-Fi dashboard | Needs Wi-Fi, two cores, 3.3 V I2C, and enough pins. An Arduino Uno has no Wi-Fi and 5 V I2C. |
| ESP32-CAM | Optional camera on the window clip for tuft and smoke video | Use the stock CameraWebServer example. Open its stream next to the dashboard. |
| Raspberry Pi | Optional host for the simulation server and the analysis tools | Any computer with Python 3 works. The Pi is a good permanent bench host. |
| Arduinos | Not used | The ESP32 does the job alone. One controller keeps the timing simple. |
| Magnets, 10 mm and under | Window clip frames (8), electronics lid (4), car tray (2, optional), angle sensor (1) | Tool-free covers. The angle sensor magnet must be a **diametric** 6 mm disc. If you only have axial discs, glue two 3 mm discs side by side with opposite poles up. |

## Filament

The printed parts need about 1.9 kg of PETG or PLA (see `cad/manifest.json` for volumes). Filament is not in the 100 dollar parts total. PETG is better for the duct because it is tougher and holds the flanges flat. PLA is fine for the balance parts.

## Upgrade options

| Upgrade | Cost | Gain |
|---|---|---|
| BMP280 barometer module | 3 | Station pressure from the bench instead of a weather service. |
| INA219 current sensor on the 12 V line | 3 | Fan power and a second stall indicator. |
| Second ARCTIC fan in series, with a longer diffuser | 16 | About 30 % more speed. Needs a new diffuser part. |
| Sensirion SDP810-500Pa | 31 | Same sensor with range for a faster tunnel. |
