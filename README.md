# LW-PLA-test-tower

**Find the right temperature and flow for Lightweight (foaming) PLA, then let Claude turn it into a PrusaSlicer 3 filament profile.**

A **PrusaSlicer 3.0 plugin** that prints a 10-band test tower from a **standard PLA profile**, plus tools that
convert your result into a ready-to-use filament preset.

<p align="center">
  <img src="docs/images/first-print-annotated.jpg" alt="The first printed tower: 205 °C is too cold, 210 to 240 °C is usable, 245 and 250 °C are too hot" width="720">
</p>

> **The first real print** (above, CORE One 0.4 HF) shows what this tower is for: **below 210 °C the filament does
> not foam, above 240 °C the surface degrades, and 210 to 240 °C is the usable window.** The plugin now defaults to
> that window, flags anything outside it, and **refuses anything above 250 °C** (toxic fumes).
>
> **Status: early.** The plugin and the generated profiles are verified (see [below](#what-is-verified-and-what-isnt));
> please [open an issue](../../issues) with what you see on your printer.

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
3. Run **Plugins → Calibration → PLA Lightweight Temp Test**, slice, and print. The default is the usable
   **210-240 °C** range (7 bands). Tick **Wide test** to see both failure ends (205-250 °C, 10 bands) or **Custom
   range** to choose your own.
4. **Don't save the edited profile over Prusament PLA.** The plugin edits the *active* presets (unsaved), so save
   it under a new name or discard the changes afterwards.

The plugin converts the standard profile for the test: first layer 215 °C, 30 % fan (100 % on bridges), no
layer-time slowdown, constant print speed (50 mm/s), bed 60 °C and retraction off, plus per-band `M104`
(temperature) and `M221` (flow). The full table and a pre-print checklist are in the
[plugin README](com.community.pla-lw-temp-test/README.md).

<p align="center">
  <img src="docs/images/tower-annotated.png" alt="The wide 205-250 °C tower in PrusaSlicer 3: ten bands, each labelled with temperature and extrusion multiplier" width="560"><br>
  <em>The wide 205-250 °C test in the PrusaSlicer 3 preview (first version of the labels).</em>
</p>

### Safety and range alerts

The plugin cannot pop up a message box (plugin errors only reach the slicer's log), so it warns where you will see it:

| | |
|---|---|
| **Dialog** | the Min / Max labels state the limits: below 210 °C too cold, above 240 °C too hot, **hard limit 250 °C** |
| **Model** | a band outside 210-240 °C is engraved `COLD` or `HOT`, for example `245/0.36 HOT` |
| **G-code** | a `; WARNING` comment on that band |
| **Printer display** | `M117` shows `LW 3/7 220C EM0.82`, or `COLD 205C no foam` / `HOT 245C degrades` |
| **Above 250 °C** | **refused.** Nothing is changed and a plate reading `NO - ABOVE 250 C = TOXIC FUMES` appears in the plater |

## 2. Measure the walls

Each band is a single wall, so the wall *is* the extruded line. Measure it with calipers on the two **30 mm side
walls**, in the **upper half of each band** (the lower half is where the nozzle is still changing temperature).
Average two or three readings.

<p align="center">
  <img src="docs/images/box-layout.svg" alt="Top view of the 50 by 30 mm test box: measure the left and right side walls, not the rear seam or the front tab" width="520">
</p>

The grooves on the front tab mark the band boundaries, so a band is identifiable even where foaming blurs the
labels. Only the **210-240 °C** bands are worth measuring. The target wall is **0.45 to 0.5 mm** for 1 perimeter
(about 0.9 mm for 2). Then:

```
EM_needed = EM_band × 0.48 / measured wall
```

*Example:* the 215 °C band (EM 1.00) measures 0.55 mm → 1.00 × 0.48 / 0.55 ≈ **0.87** is the multiplier your
filament wants at 215 °C. Pick the temperature by looking at everything else too: the palest, lightest band is the
most foamed, hotter bands string more and are weaker, and above 235 °C there is little extra weight saving.

Skip the arithmetic: type your readings in and let the analyzer do it. It knows which multiplier each band was
printed with, flags bands outside the usable range, and catches measurement slips.

```bash
python3 tools/analyze_results.py 210=0.62 220=0.55 230=0.50 240=0.47 --pick 230
```

## 3. Let Claude make the profile

Once you have your combination, open this repo in [Claude Code](https://claude.com/claude-code) (or point Claude at
it) and ask in plain language:

> Look at this repo and make me a Lightweight PLA filament profile for PrusaSlicer 3 with the 240 °C / 0.37 combo.
> I have a Prusa CORE One with a 0.4 high-flow nozzle.

Claude follows [`CLAUDE.md`](CLAUDE.md): it checks the temperature is in the usable range (never above 250 °C), finds your printer's stock Prusament PLA profile, generates the preset,
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
| Tower printed | ✅ first print: 205 °C too cold, 210-240 °C usable, 245-250 °C too hot (photo above) |
| Larger labels, band grooves, COLD/HOT tags, refusal plate, `M117` messages | ⏳ added after the first print; not yet seen in the slicer |
| Walls measured and a profile test-printed | ⏳ in progress |
| Fan / retraction / first-layer settings written by the plugin | ⚠️ the plugin API silently ignores some setting types, so the plugin reads them back; see the checklist in the [plugin README](com.community.pla-lw-temp-test/README.md) |
| Flow between Prusa's published points (and the ends, 205 °C and 250 °C) | ⚠️ interpolated or assumed, which is why you measure |

## Tests

```bash
luajit tests/plugin_test.lua          # plugin logic against a mock of the slicer API
python3 -I tests/profile_test.py      # preset generator (PyYAML optional, used for stricter checks)
python3 -I tests/resolve_test.py      # helper functions
python3 -I tests/analyze_test.py      # results analyzer and shared limits
python3 tools/make_diagrams.py        # regenerate docs/images/*.svg from the plugin's numbers
```

## Sources

Everything is linked, with what each page was used for, in **[docs/REFERENCES.md](docs/REFERENCES.md)**. The main ones:

- [Prusa blog: Prusament PLA Lightweight](https://blog.prusa3d.com/prusament-pla-lw-65-lighter-than-regular-pla-perfect-choice-for-aircraft-cosplay-and-more_138059/): 230 °C / EM 0.45, retraction off, foaming 215 to 235 °C, never above 250 °C, the hollow-cube test
- [Prusa Knowledge Base: LW PLA](https://help.prusa3d.com/article/lw-pla_304914): foaming depends on temperature and speed; EM range 1 to 0.35
- Prusament PLA Lightweight Technical Datasheet v1.0 (Prusa Polymers): 215 to 250 °C, bed 60 ± 10 °C, up to 100 mm/s, fan 30 %; EM 1.0 at 215 °C and 0.38 at 235 °C
- [PrusaSlicer Plugin API](https://github.com/prusa3d/PrusaSlicer/blob/master/doc/Plugin_API.md) and the [Plugin Marketplace docs](https://plugin-marketplace.prusa3d.com/docs)
- [Buddy firmware G-codes](https://help.prusa3d.com/article/buddy-firmware-specific-g-code-commands_633112): `M104`, `M221`, `M117`

Not affiliated with Prusa Research. Licensed under AGPL-3.0, see [LICENSE](LICENSE).
