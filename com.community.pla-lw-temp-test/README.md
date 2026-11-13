# PLA Lightweight Temperature Test (PrusaSlicer 3.0 plugin)

Menu: **Plugins → Calibration → PLA Lightweight Temp Test**

Prusament PLA Lightweight foams in the hot end. Nozzle temperature controls how much it
expands, and expansion changes the line width, so the extrusion multiplier is only right for
one temperature. A tower judged by eye is misleading. This plugin prints a **single-perimeter,
open-top box** (Prusa's own recommended density test: 1 perimeter, 0% infill, 0 top layers)
in bands, one band per temperature, and steps the flow in each band so you can measure the
wall with calipers.

## Official facts the defaults come from
- **Prusament PLA Lightweight Technical Datasheet v1.0** (Prusa Polymers, 09-2026): nozzle
  **215-250 °C**, bed 60 ± 10 °C, print speed up to 100 mm/s, fan 30 % (100 % on bridges). Its
  test specimens were printed with **extrusion multiplier 1.0 @ 215 °C and 0.38 @ 235 °C**, cooling disabled.
- Prusa's [Prusament PLA Lightweight article](https://blog.prusa3d.com/prusament-pla-lw-65-lighter-than-regular-pla-perfect-choice-for-aircraft-cosplay-and-more_138059/):
  default profile **230 °C / EM 0.45**, bed 60 °C, **retraction off**, smooth PEI/Satin. Foaming starts at
  215 °C (barely) and peaks at 235 °C; never exceed **250 °C** (fumes). Test method: hollow cube, 0.4 mm
  nozzle, 0 infill, 0 top layers, 1 perimeter, wall target **0.45-0.5 mm**. Dry 5 h at 55 °C; use
  "Avoid crossing perimeters" (max 40 mm detour) against stringing.
- Prusa Knowledge Base [LW PLA](https://help.prusa3d.com/article/lw-pla_304914): foaming depends on temperature
  **and speed** (faster needs hotter); EM range 1 to 0.35.

The plugin's flow curve is piecewise-linear through those three published points
(215 °C → 1.00, 230 °C → 0.45, 235 °C → 0.38). Points between them are interpolation, so the measured
wall decides, not the curve.

## How it turns a standard PLA profile into a Lightweight PLA test
Start from the standard **Prusament PLA** profile (extrusion multiplier 1.0, 215 °C, auto-cooling with fan
100 %, retraction on) and run the plugin. It converts the profile:

| What | Standard Prusament PLA | What the plugin does | How |
|---|---|---|---|
| Body temperature | 215 °C (CORE One 225 °C) | 205 → 250 °C in 5 °C bands | `temperature` = band 1's value, then `M104` per band from layer 3 |
| First-layer temperature | 215 °C (CORE One 230 °C) | 215 °C (the datasheet's EM 1.0 corresponds to ~215 °C) | `first_layer_temperature` |
| Flow | EM 1.0 | EM 1.0 at ≤215 °C down to 0.35 at 250 °C (Prusa's published points) | `M221` per band, relative to the loaded multiplier |
| Print speed | profile speeds | **50 mm/s** on every extrusion type of the test object (datasheet: up to 100); parameter, 20-100 | object settings only, no preset edit |
| Fan | auto 100 % (CORE One 85 %) | 30 %, 100 % on bridges, none on the first layers, CORE One overhang fans also 30 % | `min/max/bridge/overhang_fan_speed`, `disable_fan_first_layers` |
| Layer-time slowdown | slows short layers | off (`slowdown_below_layer_time` 0, `min_print_speed` 5), so speed and foaming stay constant | preset edit |
| Bed | 60 °C | 60 °C (datasheet 60 ± 10) | `bed_temperature`, `first_layer_bed_temperature` |
| Retraction | on | off (Prusa's LW default) | best-effort, **check manually** |
| Test shape | n/a | 1 or 2 perimeters, 0 infill, no top layers, 3 bottom layers | object settings on the test object only |

**How each setting is checked.** The slicer's setter silently ignores some keys (booleans and vectors), so the
plugin reads each fan, temperature and slowdown setting back. If `min_fan_speed` and `max_fan_speed` took, the
profile holds the fan at 30 % and **no `M106` is emitted**. If they did not, the plugin falls back to an
`M106 S77` on every layer from layer 3 (about 400 entries on the layer slider, and the slicer's own cooling may
still compete with it).

**Do not save the edited profile over Prusament PLA.** All the edits above are unsaved changes to the active
presets. Save under a new name (for example "Prusament PLA - LW test") or discard them afterwards.

**Before printing, check in the preview/G-code or settings:**
1. *Printer Settings → Extruder → Retraction length* is 0 (or enable Filament → Filament Overrides →
   Retraction length = 0). If retraction still happens it only matters at the layer change/seam of this box,
   but it adds a small blob there.
2. First-layer temperature is 215 °C (Filament → Temperature). On CORE One the PLA profile uses 230 °C; if
   the setter did not take, set 215 °C yourself, otherwise the first layer is over-extruded at EM 1.0.
3. The fan is 30 %: Filament → Cooling shows min/max fan 30 % and the exported G-code has no competing
   `M106 S255` or `S217`. The CORE One also uses dynamic fan speeds; if other values appear, set the fan
   manually (auto-cooling off, fan 30 %).
4. Pressure advance: the standard profile may set it (`M900 K…` start filament G-code on some printers). Foaming
   filament usually does not want it; set it to 0 if your printer supports that.
5. Ventilate: 250 °C is Prusa's stated limit for this filament, because of fumes.

## Install
1. Select **Prusament PLA** and your normal 0.4 mm print profile. Leave *Loaded Profile Extrusion
   Multiplier* at **1.0** (the plugin uses the real value instead when the slicer lets it read it).
2. Copy the folder `com.community.pla-lw-temp-test` (the folder name must equal the id) into
   the PrusaSlicer 3 data directory `lua/` folder, then restart PrusaSlicer (or use
   *Plugins → Rescan*). For the Flatpak that is
   `~/.var/app/com.prusa3d.PrusaSlicer/config/PrusaSlicer3-dev/lua/`. Copy, don't symlink.
   Unsigned bundles load from this folder with no key needed; don't use the ZIP importer.

## Range, warnings and safety

The first test print (205 to 250 °C on a CORE One 0.4 HF) showed where this filament is usable:

| Zone | Temperatures | What happens |
|---|---|---|
| **Too cold** | below 210 °C | dense and dark, not foaming (205 °C band) |
| **Usable** | 210 to 240 °C | foamed, clean surface, readable labels |
| **Too hot** | above 240 °C | the surface degrades and the engraving blurs (245 and 250 °C bands) |
| **Forbidden** | above 250 °C | Prusa: toxic fumes. **The plugin refuses.** |

So the plugin **defaults to 210-240 °C** (7 bands, 56 mm tall). A **Wide test** switch gives the full 205-250 °C
range if you want to see both failure ends on your own printer, and **Custom range** lets you pick Min / Max / Steps
(Min = Max tests a single temperature).

You are warned in four places, because the plugin API cannot pop up a message box (errors are only written to the
slicer log):
1. **In the dialog:** the Min and Max labels state the limits (below 210 too cold, above 240 too hot, hard limit 250).
2. **In the model:** a band outside 210-240 °C is engraved `COLD` or `HOT` (for example `245/0.36 HOT`).
3. **In the G-code:** a `; WARNING: ...` comment on that band.
4. **On the printer display:** `M117` shows `LW 3/7 220C EM0.82` for a normal band and `COLD 205C no foam` /
   `HOT 245C degrades` for a flagged one (switch off with *Show band / warning messages*; a firmware without `M117`
   ignores it).

**Above 250 °C (or below 190 °C) is refused, not clamped.** The plugin changes nothing (no presets, no G-code, no
tower) and puts a text object in the plater that reads `NO - ABOVE 250 C = TOXIC FUMES` (or `NO - BELOW 190 C = TOO
COLD`). Delete it and run again with a legal range. Even if validation were bypassed, the planner never emits a
temperature outside 190-250 °C.

The labels are larger and deeper than in the first version (foamed bands blur shallow engraving), and a groove across the tab
marks every band boundary, so a band is identifiable even when its text is unreadable.

## Parameters
| Parameter | Default | Meaning |
|---|---|---|
| Wide test 205-250 C | off | Shows too-cold and too-hot bands (10 bands, 80 mm). |
| Custom range | off | Use Min / Max / Steps below instead of the 210-240 °C default. |
| Custom Min / Max | 210 / 240 | Clamped to **190-250 °C**; outside that the plugin refuses. Below 210 / above 240 is flagged COLD / HOT. |
| Custom Num Steps | 7 | 2-10 bands. Min = Max tests one temperature. |
| Band Height | 8 mm | Taller bands let the hot end settle. |
| Box Front/Back Width | 50 mm | X size: the 5 cm faces (front carries the label tab, rear carries the seam). |
| Box Side Length | 30 mm | Y size: the 3 cm **side walls, which you measure**. |
| Perimeters | 1 | 1 or 2 (clamped). With 2 the two lines overlap at 0.2 mm layers: target about **0.85-0.9 mm**, and the EM formula below is only approximate. |
| Loaded Profile Extrusion Multiplier | 1.0 | The multiplier of the profile you have loaded (1.0 for Prusament PLA). |
| Convert Flow For Foaming | on | Off = every band at 100 % (pure temperature test). |
| Print Speed | 50 mm/s | 20-100 (datasheet: up to 100). Faster needs hotter for the same foaming (Prusa KB). |
| Fan Speed | 30 % | 0 = leave the profile's fan alone. |
| Try To Turn Retraction Off | on | Best-effort, see above. |
| Hottest Band On Top | on | Order of bands. |
| Engrave Labels And Band Grooves | on | Front tab shows `temp/EM` per band plus a groove at every band boundary. |
| Show Band / Warning Messages (M117) | on | Band number and COLD / HOT alerts on the printer display. |
| Clear Existing Custom G-code | on | Prevents stacked temperature changes on re-runs. |
| Disable Layer-time Slowdown | on | Sets `slowdown_below_layer_time` to 0 on the **active filament preset (unsaved edit)**. |

## What it emits
Per band, at the first layer that starts at or above the band boundary (snapped to the real layer grid):
`M104 S<temp>` (no wait, so the nozzle doesn't park and ooze a blob on the wall) and `M221 S<flow>`.
Band 1's `M104` goes on layer 3 (never layer 2: on the CORE One the slicer itself changes the temperature there). If its flow is above 100 % that `M221` is held back until the solid bottom layers plus ~2 mm are done; a flow reduction is applied immediately. Because `M104` doesn't wait,
**measure the upper half of each band**, on the **30 mm left/right side walls** (not the rear seam, not the
front label tab).

`M221` is relative to the profile's multiplier and stays active until reset. Most Prusa start G-code
contains `M221 S100`; check yours. During a band, *Tune → Flow* on the printer should show the labelled
percentage; if it shows more or less, the printer clamped it.

## Reading the result
Measure the wall at mid-height of the upper half of each band (calipers, target **0.45-0.5 mm for 1 perimeter**). Only 210-240 °C bands are worth measuring. To skip the arithmetic, type your readings into `python3 tools/analyze_results.py 210=0.62 220=0.55 230=0.50` (see the repository README); it prints the multiplier each band needs and flags anything out of range.
The band's effective multiplier is the label value (`temp / EM`). The multiplier that gives the target wall:

`EM_needed = EM_band × target_width / measured_width`

e.g. band 215 °C / EM 1.00, wall 0.55 mm, target 0.48 → 1.00 × 0.48 / 0.55 ≈ 0.87. Enter the result as the
filament's extrusion multiplier for that temperature. The lightest, palest band is the most foamed; surface
quality and stringing tell you where to stop. To confirm, re-run with Min = Max at one temperature.

## Known limits / not verified
- Developed against the documented alpha13/14 Lua API and Prusa's own `temp_tower.lua`; logic tested with a mock
  API in LuaJIT (`luajit tests/plugin_test.lua`, kept next to the bundle folder, not inside it). The first version
  was printed and measured (see the repository README); the CLI has no plugin validate command.
- **Confirmed by the first print:** the tower, the front tab and the engraved labels work, and the usable range is
  210-240 °C. **Not yet seen in the slicer since:** the larger/deeper labels, the band grooves, the `COLD`/`HOT` tags,
  the refusal plate and the `M117` display messages, so check the preview.
- A dropdown parameter exists in the plugin API, but its exact type name could not be confirmed against the
  slicer, so only verified types (switches and numbers) are used. That is why the range is two switches plus
  Min / Max / Steps.
- The dialog cannot show alerts and plugin errors only reach the log, which is why warnings are put in the
  model, the G-code and the printer display, and why a refusal is a visible plate.
- The datasheet multipliers (1.0 @ 215 °C, 0.38 @ 235 °C) came from dense specimens (2 perimeters, 100 % infill,
  MK4S, PrusaSlicer 2.9.6), not from a single-wall box, so expect your measured values to differ.
- `seam_position`, per-volume `perimeters` on the modifier and the preset edits are set through a setter
  that fails silently on unsupported keys; check the preview and the checklist above.
- Flow is held at EM 1.0 below 215 °C and slides to Prusa's 0.35 floor at 250 °C; those two ends are
  assumptions (and both lie outside the usable range).
- "5 cm × 3" was read as a 50 × 30 mm footprint (3 cm side walls measured); the default height is
  7 bands × 8 mm = 56 mm (80 mm in the wide test).
- The 210-240 °C range comes from one print on one printer and one spool. Treat it as a strong default, and use the
  wide test to check your own setup.

## Next: turn the result into a filament profile
Once you know your temperature and extrusion multiplier, see the [repository README](../README.md#5-make-your-filament-profile): Claude (or `tools/make_profile.py`) can generate a PrusaSlicer 3 filament preset for you.
