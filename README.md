# LW-PLA-test-tower

**Find the right temperature and flow for Lightweight (foaming) PLA, then let Claude turn it into a PrusaSlicer 3 filament profile.**

A **PrusaSlicer 3.0 plugin** that prints a 10-band test tower from a **standard PLA profile**, plus tools that
convert your result into a ready-to-use filament preset.

<p align="center">
  <img src="docs/images/tower-annotated.png" alt="The test tower in PrusaSlicer 3: ten bands from 205 °C to 250 °C, each labelled with temperature and extrusion multiplier" width="640">
</p>

> **Status: early.** The plugin runs in PrusaSlicer 3 alpha (that is the preview above) and the generated profiles
> load and resolve correctly in the slicer CLI. The first real print of the tower is in progress, so expect rough
> edges and please [open an issue](../../issues) with what you see.

<p align="center">
  <img src="docs/images/workflow.svg" alt="Workflow: print the tower, measure, calculate, ask Claude, print with the new profile" width="900">
</p>

## Why a normal temperature tower fails

Lightweight PLA foams in the hot end. **Temperature sets how much it expands** (foaming starts around 215 °C and
peaks around 235 °C), and expansion changes the width of the extruded line. So the extrusion multiplier is only
correct at *one* temperature; judging a normal tower by eye is misleading.

This tower steps **temperature and flow together**. Every band is printed at a different temperature with the
multiplier Prusa's own numbers suggest for it, so you can measure each wall and find the multiplier that is
actually right for your printer at any temperature.

<p align="center">
  <img src="docs/images/em-curve.svg" alt="Extrusion multiplier against temperature: 1.0 at 215 °C, 0.45 at 230 °C, 0.38 at 235 °C" width="760">
</p>

## 1. Print the tower

1. In PrusaSlicer 3 load the standard **Prusament PLA** profile.
2. Copy the folder [`com.community.pla-lw-temp-test`](com.community.pla-lw-temp-test) into the `lua` folder of your
   PrusaSlicer 3 data directory (the folder that contains `PrusaSlicer.ini`), then restart PrusaSlicer 3.

   | Install | `lua` folder |
   |---|---|
   | Flatpak | `~/.var/app/com.prusa3d.PrusaSlicer/config/PrusaSlicer3-dev/lua/` |
   | Linux | `~/.config/PrusaSlicer3-dev/lua/` |
   | macOS | `~/Library/Application Support/PrusaSlicer3-dev/lua/` |
   | Windows | `%APPDATA%\PrusaSlicer3-dev\lua\` |

   Copy the folder, don't symlink it.
3. Run **Plugins → Calibration → PLA Lightweight Temp Test**, slice, and print.
4. **Don't save the edited profile over Prusament PLA.** The plugin edits the *active* presets (unsaved), so save
   it under a new name or discard the changes afterwards.

The plugin converts the standard profile for the test: first layer 215 °C, 30 % fan (100 % on bridges), no
layer-time slowdown, constant print speed (50 mm/s), bed 60 °C and retraction off, plus per-band `M104`
(temperature) and `M221` (flow). The full table and a pre-print checklist are in the
[plugin README](com.community.pla-lw-temp-test/README.md).

## 2. Measure the walls

Each band is a single wall, so the wall *is* the extruded line. Measure it with calipers on the two **30 mm side
walls**, in the **upper half of each band** (the lower half is where the nozzle is still changing temperature).
Average two or three readings.

<p align="center">
  <img src="docs/images/box-layout.svg" alt="Top view of the 50 by 30 mm test box: measure the left and right side walls, not the rear seam or the front tab" width="520">
</p>

The target wall is **0.45 to 0.5 mm** for 1 perimeter (about 0.9 mm for 2). Then:

```
EM_needed = EM_band × 0.48 / measured wall
```

*Example:* the 215 °C band (EM 1.00) measures 0.55 mm → 1.00 × 0.48 / 0.55 ≈ **0.87** is the multiplier your
filament wants at 215 °C. Pick the temperature by looking at everything else too: the palest, lightest band is the
most foamed, hotter bands string more, and above 235 °C there is little extra weight saving.

## 3. Let Claude make the profile

Once you have your combination, open this repo in [Claude Code](https://claude.com/claude-code) (or point Claude at
it) and ask in plain language:

> Look at this repo and make me a Lightweight PLA filament profile for PrusaSlicer 3 with the 240 °C / 0.37 combo.
> I have a Prusa CORE One with a 0.4 high-flow nozzle.

Claude follows [`CLAUDE.md`](CLAUDE.md): it finds your printer's stock Prusament PLA profile, generates the preset,
**checks it against the real slicer**, and asks before installing it. You then restart PrusaSlicer 3 and pick the
new filament.

The generated preset inherits from *Prusament PLA* and sets temperature, first-layer temperature, extrusion
multiplier, bed 60 °C, a constant 30 % fan (100 % on bridges), no layer-time slowdown and retraction off. It also
copies your printer's own values back in (for example the CORE One heatbreak G-code and high-flow volumetric
limit), which a plain "inherit from Prusament PLA" would silently lose.

You can also run the tools yourself (Python 3.8+, no dependencies):

```bash
python3 tools/resolve_stock.py --list-printers
python3 tools/resolve_stock.py --list-materials "Prusa CORE One & One+ 0.4 HF"
python3 tools/resolve_stock.py --printer "Prusa CORE One & One+ 0.4 HF" \
    --print "0.20mm BALANCED @COREONE 0.4HF" \
    --material "Prusament PLA @COREONE HF0.4@COREONE 0.4" --out stock.json
python3 tools/make_profile.py --temp 240 --em 0.37 --printers COREONE --nozzle 0.4 --high-flow \
    --stock-json stock.json --out profiles          # add --install to copy it into PrusaSlicer
```

A filament preset cannot hold print settings. For printing with it, also use a print speed of about **50 mm/s**,
"Avoid crossing perimeters" (max detour 40 mm), dry the filament 5 h at 55 °C, and ventilate. **250 °C is Prusa's
limit** for this filament.

## What is verified, and what isn't

| | Status |
|---|---|
| Plugin loads and builds the tower in PrusaSlicer 3 alpha | ✅ (screenshot above) |
| Plugin maths, G-code order and formatting | ✅ mock-API tests (`luajit tests/plugin_test.lua`) |
| Generated preset loads and resolves correctly in the slicer | ✅ checked against the slicer CLI (`tests/` + `tools/resolve_stock.py`) |
| Tower printed and measured | ⏳ first print in progress |
| Fan / retraction / first-layer settings written by the plugin | ⚠️ the plugin API silently ignores some setting types, so the plugin reads them back; see the checklist in the [plugin README](com.community.pla-lw-temp-test/README.md) |
| Flow between Prusa's published points (and the ends, 205 °C and 250 °C) | ⚠️ interpolated or assumed, which is why you measure |

## Tests

```bash
luajit tests/plugin_test.lua          # plugin logic against a mock of the slicer API
python3 -I tests/profile_test.py      # preset generator (PyYAML optional, used for stricter checks)
python3 -I tests/resolve_test.py      # helper functions
python3 tools/make_diagrams.py        # regenerate docs/images/*.svg from the plugin's numbers
```

## Sources

- Prusament PLA Lightweight Technical Datasheet v1.0 (Prusa Polymers): nozzle 215 to 250 °C, bed 60 ± 10 °C, up to
  100 mm/s, fan 30 %; specimens printed at EM 1.0 / 215 °C and 0.38 / 235 °C
- [Prusa blog: Prusament PLA Lightweight](https://blog.prusa3d.com/prusament-pla-lw-65-lighter-than-regular-pla-perfect-choice-for-aircraft-cosplay-and-more_138059/): 230 °C / EM 0.45, retraction off, foaming 215 to 235 °C, the hollow-cube test
- [Prusa Knowledge Base: LW PLA](https://help.prusa3d.com/article/lw-pla_304914): foaming depends on temperature and speed; EM range 1 to 0.35
- [PrusaSlicer Plugin API](https://github.com/prusa3d/PrusaSlicer/blob/master/doc/Plugin_API.md)

Not affiliated with Prusa Research. Licensed under AGPL-3.0, see [LICENSE](LICENSE).
