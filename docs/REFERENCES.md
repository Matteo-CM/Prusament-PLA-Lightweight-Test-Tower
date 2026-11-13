# Prusa documentation and references

Official Prusa pages this project is built on, with what each one was used for. Links were checked when they were
added; Prusa may move pages. Nothing from these pages is copied into the repo: it is all linked.

## The filament: Prusament PLA Lightweight

| Source | Used for |
|---|---|
| [Prusa blog: Prusament PLA Lightweight](https://blog.prusa3d.com/prusament-pla-lw-65-lighter-than-regular-pla-perfect-choice-for-aircraft-cosplay-and-more_138059/) | Default profile (230 °C, extrusion multiplier 0.45, bed 60 °C, retraction off), foaming from 215 °C to a peak at 235 °C, **never above 250 °C**, the hollow-cube wall test (0.45 to 0.5 mm), drying (5 h at 55 °C), "Avoid crossing perimeters" against stringing |
| [Knowledge Base: LW PLA](https://help.prusa3d.com/article/lw-pla_304914) | Foaming depends on temperature **and speed**; extrusion multiplier range 1 to 0.35; retractions are ineffective; oozing and stringing |
| [Prusament PLA Lightweight product page](https://www.prusa3d.com/product/prusament-pla-lightweight-natural-1kg-nfc/) | Nozzle, bed and filament specifications as sold |
| [Knowledge Base: PLA](https://help.prusa3d.com/article/pla_2062) and [Filament material guide](https://help.prusa3d.com/filament-material-guide) | General PLA background |
| [Prusament materials](https://prusament.com/materials/) | Prusament material overview and datasheet downloads |

**Technical datasheet.** The *Prusament PLA Lightweight Technical Datasheet v1.0* (Prusa Polymers, 09-2026) was used
for the nozzle range (215 to 250 °C), bed (60 ± 10 °C), print speed (up to 100 mm/s), fan (30 %, 100 % on bridges)
and the test-specimen multipliers (**1.0 at 215 °C and 0.38 at 235 °C**, cooling disabled). A public link for the
Lightweight datasheet was not found, and the PDF is Prusa's, so it is not included here. Look for it on the
product page or on prusament.com.

## Calibration and print-quality background

| Source | Used for |
|---|---|
| [Extrusion multiplier calibration](https://help.prusa3d.com/article/extrusion-multiplier-calibration_2257) | What the multiplier does: too much material means lower it, gaps between lines mean raise it |
| [Stringing and oozing](https://help.prusa3d.com/article/stringing-and-oozing_1805) | Why Lightweight PLA strings and what helps |

## Printer firmware G-code

| Source | Used for |
|---|---|
| [Buddy firmware-specific G-code commands](https://help.prusa3d.com/article/buddy-firmware-specific-g-code-commands_633112) | `M104` (temperature), `M221` (flow percentage) and `M117` (display message), which the plugin writes into the G-code |

## Plugin development (PrusaSlicer 3)

| Source | Used for |
|---|---|
| [PrusaSlicer Plugin API (`Plugin_API.md`)](https://github.com/prusa3d/PrusaSlicer/blob/master/doc/Plugin_API.md) | Bundle layout, `manifest.json`, the `info` table and `execute` function, parameter types, install steps, the sandbox |
| [Plugin Marketplace documentation](https://plugin-marketplace.prusa3d.com/docs) | Overview of writing, packaging and publishing plugins |
| [Lua API reference](https://plugin-marketplace.prusa3d.com/docs/lua-api) | The `api` module, `ProjectApi`, config access |
| [Write your first plugin](https://plugin-marketplace.prusa3d.com/docs/first-plugin) | Getting started |
| [Bundle format](https://plugin-marketplace.prusa3d.com/docs/bundle) | Manifest fields and packaging rules |
| [PrusaSlicer 3.0 preview](https://blog.prusa3d.com/prusaslicer-3-0-preview-built-for-the-future-of-3d-printing_137672/) | What PrusaSlicer 3 is and where the plugin system fits |
| [PrusaSlicer releases](https://github.com/prusa3d/PrusaSlicer/releases) | Alpha and beta versions of PrusaSlicer 3 |

Prusa's own `temp_tower.lua` (in the PrusaSlicer 3 installation, under `share/PrusaSlicer/lua/`) was the model for
the plugin's G-code and label placement.

## Community documentation (unofficial)

| Source | Used for |
|---|---|
| [Unofficial PrusaSlicer 3 Lua API docs (jedisct1)](https://github.com/jedisct1/prusaslicer-lua-plugins-api-doc) | Detail the official docs lack: primitive bounds are stale in alpha 14, which setting types can be written, dialog parameter types |
| [Unofficial plugins (leotrax3d)](https://github.com/leotrax3d/prusaslicer-plugins-unofficial) | Working fan-tower and speed-tower plugins used as a reference |

## Not documented by Prusa (so measured, not quoted)

- the extrusion multiplier **between** 215 and 230 °C, and the ends of the range (205 °C and 250 °C): these are
  interpolated or assumed, which is why the tower exists;
- the **210 to 240 °C usable window**: this comes from the first test print in this repo, not from Prusa.
