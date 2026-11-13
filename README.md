# LW-PLA-test-tower

A **PrusaSlicer 3.0 plugin** that builds a temperature + flow test for foaming ("Lightweight") PLA such as
Prusament PLA Lightweight, starting from a **standard PLA profile**. The plugin converts the profile for you
(temperature bands, flow, fan, speed, slowdown) and adds a single-wall test box you measure with calipers.

> **Status: early / untested in the slicer.** The logic is covered by a mock-API test suite (LuaJIT), but the
> plugin has not yet been run inside PrusaSlicer. The first real print is in progress. Expect rough edges
> (especially the engraved labels) and please open an issue with what you see.

## Why a normal temperature tower doesn't work
Lightweight PLA foams in the hot end. Temperature sets how much it expands (foaming starts around 215 °C and
peaks around 235 °C), and expansion changes the extruded line width, so the extrusion multiplier is only right
at one temperature. This test steps **both** temperature and flow per band, so you can measure the wall in each
band and work out the multiplier for any temperature.

## What it does
- Prints a **50 × 30 mm** open-top box, one band per temperature (default **205 → 250 °C**, 10 bands × 8 mm),
  with **1 or 2 perimeters**, 0 % infill and no top layers (Prusa's own density-test method).
- Per band: `M104` (temperature, no wait) and `M221` (flow) following Prusa's published multipliers
  (1.0 @ 215 °C, 0.45 @ 230 °C, 0.38 @ 235 °C).
- Converts the loaded profile: first-layer temperature 215 °C, fan 30 % (100 % on bridges), layer-time
  slowdown off, constant print speed (default 50 mm/s), bed 60 °C, retraction off (best effort).
- Engraves `temp / extrusion multiplier` labels on a front tab.

## Install
1. Load the standard **Prusament PLA** profile.
2. Copy the folder [`com.community.pla-lw-temp-test`](com.community.pla-lw-temp-test) into the `lua` folder of
   your PrusaSlicer 3 data directory (the folder containing `PrusaSlicer.ini`). For the Flatpak:
   `~/.var/app/com.prusa3d.PrusaSlicer/config/PrusaSlicer3-dev/lua/`. Copy, don't symlink.
3. Restart PrusaSlicer, then run **Plugins → Calibration → PLA Lightweight Temp Test**.
4. **Don't save the edited profile over Prusament PLA**; the plugin edits the active presets (unsaved).

Full details (what each setting does, the pre-print checklist, how to read the results and the formula
`EM_needed = EM_band × target_width / measured_width`) are in the
[plugin README](com.community.pla-lw-temp-test/README.md).

## Tests
```bash
luajit tests/plugin_test.lua
```
The tests use a mock of the slicer API: they check the planning maths, G-code order and formatting, and the
settings-readback fallback. They cannot prove the plugin works inside PrusaSlicer.

## Sources
- Prusament PLA Lightweight Technical Datasheet v1.0 (Prusa Polymers)
- [Prusa blog: Prusament PLA Lightweight](https://blog.prusa3d.com/prusament-pla-lw-65-lighter-than-regular-pla-perfect-choice-for-aircraft-cosplay-and-more_138059/)
- [Prusa Knowledge Base: LW PLA](https://help.prusa3d.com/article/lw-pla_304914)
- [PrusaSlicer Plugin API](https://github.com/prusa3d/PrusaSlicer/blob/master/doc/Plugin_API.md)

Not affiliated with Prusa Research. Licensed under AGPL-3.0 (see [LICENSE](LICENSE)).
