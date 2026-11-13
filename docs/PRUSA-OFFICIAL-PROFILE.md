# Prusa's official Lightweight PLA profile vs. what this project builds

Prusa **does** publish official Prusament PLA Lightweight profiles. They are in the PrusaSlicer **2.x** settings
bundle, in Prusa's GitHub repository
[prusa3d/PrusaSlicer-settings-prusa-fff](https://github.com/prusa3d/PrusaSlicer-settings-prusa-fff)
(file `PrusaResearch/<version>.ini`; added in config version 2.5.10, commit
[`65c5c8f`](https://github.com/prusa3d/PrusaSlicer-settings-prusa-fff/commit/65c5c8f) on 2026-09-17, and unchanged for
the CORE One and MK4S variants since). The PrusaSlicer **3.0 alpha** uses a different profile format and, on the build
this project was developed on, does not contain them. That gap is why this project exists (see the disclaimer in the
README).

Everything below was read from that repository (config version 2.5.16, resolved with the same inheritance rules as
PrusaSlicer) and compared with what this project generates. Re-run it any time:

```bash
python3 tools/official_lw.py --list
python3 tools/official_lw.py --variant "COREONE HF0.4" --compare profiles/<your preset>.yaml
```

## What Prusa's official profile sets (every variant, all printers)

| Setting | Official value | What it does |
|---|---|---|
| Extrusion multiplier | **0.45** (0.4 and 0.6 nozzles) | the same 230 °C / 0.45 point as Prusa's blog post |
| Temperature | **230 °C** (0.4 mm nozzle), **225 °C** (0.6 mm nozzle), first layer the same | |
| Bed | 60 °C | |
| Auto-cooling (`cooling`) | **off** | no layer-time slowdown and no automatic fan changes |
| Fan (`min_fan_speed`) | **30 %** on CORE One, MK4S, XL+; **45 %** on MK4 / MK3.9; **50 %** on XL 0.4 HF | with auto-cooling off the fan simply runs at this value |
| Bridge / overhang fan | 100 % (stock) | |
| Max volumetric speed | **4 mm³/s** on every printer | about 49 mm/s at 0.2 mm layers: the speed limit |
| Pressure advance | **off** (`M572 S0` on every printer) | the foam is compressible |
| Z-hop (`retract_lift`) | **0** | |
| Travel Z-ramping | **0** | |
| Density | 1.18 | |
| Print profile | **unchanged** (the stock 0.20mm BALANCED etc.) | no special print preset, no "Avoid crossing perimeters" |
| Retraction length | **not overridden** | see the conflict below |

## What we adopted, what matches, what differs

| Setting | This project | |
|---|---|---|
| Multiplier at 230 °C | 0.45 (our curve passes through it) | ✅ same |
| Temperature, first layer, bed | 230 / 230 / 60 for the 230 °C profile | ✅ same |
| `cooling` | 0 | ✅ adopted after this cross-check (we had left it on with min = max = 30) |
| Fan | 30 % by default (`--fan`), 100 % on bridges | ✅ for CORE One / MK4S / XL+; use `--fan 45` or `--fan 50` for the others |
| Max volumetric speed | 4 mm³/s by default | ✅ adopted (we had derived 4.07 from the tower's 50 mm/s; now Prusa's exact value) |
| Pressure advance | 0 (off) by default | ✅ adopted. We had kept the stock 0.036 and Prusa turns it off everywhere |
| Z-hop and travel ramping | 0 | ✅ adopted. Stock PLA had 1,360 Z moves in our test print, the new profile has 0 |
| Dynamic overhang fans | left at stock | ✅ adopted (we had switched them off; Prusa keeps them) |
| Print profile | not changed | ✅ same approach; "Avoid crossing perimeters" stays a manual tip from Prusa's blog |
| `slowdown_below_layer_time` | 0 | ≠ Prusa has 8, but with `cooling = 0` it is inactive, so no practical difference |
| **Retraction length** | **0 (off) by default** | ≠ **see below** |

All of the adopted values were checked in real sliced G-code (`tools/check_gcode.py`, CORE One 0.4 HF): retractions
405 → 0, Z moves during travel 1,360 → 0, pressure advance 0.036 → off, speed 150-200 → about 49 mm/s, fan 30 %.

## An open question: retraction

Two official Prusa sources disagree:

- Prusa's [blog post](https://blog.prusa3d.com/prusament-pla-lw-65-lighter-than-regular-pla-perfect-choice-for-aircraft-cosplay-and-more_138059/)
  lists **"Retractions: Off"** for the default profile, and the
  [Knowledge Base](https://help.prusa3d.com/article/lw-pla_304914) says retractions are ineffective on foaming filament.
- The **shipped profile does not override the retraction length**. On the CORE One the printer's own 0.7 mm retraction
  stays active; only the Z-hop is removed.

This project defaults to the **blog and Knowledge Base** (retraction off). To match the shipped profile instead, pass
`--keep-retraction` to `tools/make_profile.py`. The best evidence would be your own prints: a print with retraction off
versus on, on your printer. Treat the default as unproven until someone has measured it.

## Where the numbers in our own curve come from

Our flow curve (1.0 at 215 °C, 0.45 at 230 °C, 0.38 at 235 °C) uses Prusa's datasheet and blog. The official profile
independently confirms the 230 °C / 0.45 point. It has no values at other temperatures, so the rest of the curve, and
the 210-240 °C usable window, still come from the datasheet and from the first test print.
