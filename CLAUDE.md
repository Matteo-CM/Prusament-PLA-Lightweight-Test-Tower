# CLAUDE.md: instructions for Claude working in this repo

This repo has two halves:

1. **`com.community.pla-lw-temp-test/`** is a PrusaSlicer 3 Lua plugin that prints a 10-band test box
   (205 → 250 °C, each band with its own extrusion multiplier, "EM") for Lightweight / foaming PLA.
2. **`tools/`** turns the result into a PrusaSlicer 3 **filament preset**. That is the job you will usually be
   asked to do.

## Scope (say this to users when relevant)
This project is **only for PrusaSlicer 3.0 while it is in alpha**, which has no Prusament PLA Lightweight profile by
default. It does not work with PrusaSlicer 2.x (no plugins there). Once Prusa ships an official profile for
PrusaSlicer 3, recommend that instead. It is a community project, not affiliated with or supported by Prusa Research.

## The main request: "make a Lightweight PLA profile for PrusaSlicer 3 with the 240 °C / 0.37 combo"

The user read a label off the printed tower (`temperature / extrusion multiplier`, e.g. `240 / 0.37`) or measured
the walls and worked out their own multiplier. Produce a ready-to-use filament preset and verify it with the real
slicer. Do these steps in order and do not skip the verification.

### 0. Understand the numbers
- `240 °C / 0.37` means temperature 240 and **extrusion multiplier 0.37** (a factor, not a percentage; "0.37%" is
  just a typo). `--temp 240 --em 0.37`.
- If the user gives *measured* wall thicknesses instead (e.g. "210 is 0.62, 230 is 0.50"), run the analyzer rather
  than doing the arithmetic by hand. It reads the multiplier each band was printed with from the plugin's curve:
  ```bash
  python3 tools/analyze_results.py 210=0.62 230=0.50 240=0.47 [--perimeters 2] [--pick 230]
  ```
  `EM_needed = EM_band × target / measured` (target 0.48 mm for 1 perimeter, 0.9 mm for 2). Report its table
  honestly, including its warnings (too cold / too hot band, measurement slips, a hotter band needing more flow).
  The choice of temperature is the user's: tell them to weigh foaming (palest, lightest), stringing and strength.
- **Safety and range (never skip this).** 250 °C is a hard limit: Prusa says the filament emits toxic fumes above
  it. Never generate, suggest or help someone print a profile above 250 °C, and never help bypass the plugin's or
  tools' refusals. The usable range found by the first test print is **210 to 240 °C**: below 210 °C the filament
  does not foam (too cold), above 240 °C the surface degrades (too hot). If the user asks for a temperature outside
  210-240 °C, say so plainly, explain why, and suggest the nearest usable band; only continue if they explicitly
  want it (the generator prints a WARNING). EM must be 0.2 to 1.2. The tools enforce 190-250 °C and 0.2-1.2.
- If the printer or nozzle is not stated, **ask** (or read it from their slicer: step 2). Never guess.

### 1. Locate PrusaSlicer 3 and its data folder
`tools/resolve_stock.py` auto-detects the Flatpak, `prusa-slicer`/`PrusaSlicer` on PATH, and the data folder
(`~/.var/app/com.prusa3d.PrusaSlicer/config/PrusaSlicer3-dev`, `~/.config/PrusaSlicer3-dev`,
`~/Library/Application Support/PrusaSlicer3-dev`, `%APPDATA%\PrusaSlicer3-dev`). Override with `--slicer "<cmd>"`
and `--datadir <folder>`. It only ever works on a **throwaway copy** of the presets, never on the real folder.

### 2. Find the exact profile names for the user's printer
```bash
python3 tools/resolve_stock.py --list-printers
python3 tools/resolve_stock.py --list-materials "Prusa CORE One & One+ 0.4 HF"
```
`--list-materials` prints the print profiles and the filament profiles available for that printer. Pick the
stock Prusament PLA entry for that printer/nozzle (CORE One 0.4 HF looks like
`Prusament PLA @COREONE HF0.4@COREONE 0.4`) and one normal print profile (e.g. `0.20mm BALANCED @COREONE 0.4HF`).

### 3. Capture the stock preset's printer-specific values
```bash
python3 tools/resolve_stock.py --printer "<printer>" --print "<print profile>" \
  --material "<stock Prusament PLA name>" --out stock.json
```
This matters. A user preset that inherits "Prusament PLA" does **not** inherit that preset's
printer/nozzle-specific values (verified against the slicer): without step 3 a CORE One user silently loses
the `M142 S36` heatbreak start G-code, the 24 mm³/s high-flow volumetric limit, `min_print_speed`, etc.
`make_profile.py --stock-json stock.json` copies them back in.

### 4. Generate the preset
```bash
python3 tools/make_profile.py --temp 240 --em 0.37 \
  --printers COREONE --nozzle 0.4 --high-flow --stock-json stock.json --out profiles
```
- `--printers` is the `printer.base_model` regex alternative(s), `|`-separated. Known values in the stock presets:
  `COREONE`, `COREONE_INDX`, `MK4`, `MK3.5`, `MK3`, `MK2.5`, `MK2`, `MINI`, `XL`. Take it from the printer name
  (CORE One → `COREONE`, MK4/MK4S → `MK4`, MK3.5 → `MK3.5`, XL → `XL`, MINI → `MINI`).
- Nozzle `0.4` → `--nozzle 0.4`. A `HF` / high-flow nozzle → `--high-flow`; a normal nozzle → `--standard-flow`.
  Omit them to cover every nozzle (then the baked values only match the nozzle used in step 3, so prefer being
  specific).
- Defaults you may change on request: `--name`, `--first-layer-temp` (default = `--temp`), `--bed 60`,
  `--fan 30`, `--bridge-fan 100`, `--slowdown 0`, `--retract 0`, `--speed 50`.
- `--speed` (mm/s, default 50, max 100, 0 = keep the stock limit) is applied as the filament's **maximum volumetric
  speed** (50 mm/s is about 4.07 mm³/s for 0.2 mm layers and 0.45 mm lines). Verified in real G-code: it takes
  perimeters from 150-200 mm/s down to about 50, which matches the tower (printed at about 50 mm/s). Do not drop it:
  foaming depends on speed, so a multiplier measured at 50 mm/s is not valid at 150-200.
- `--pressure-advance <value>` is optional. By default the stock preset's value is kept (CORE One: 0.036). Foaming
  filament is compressible, so only change it when the user asks or wants to experiment; it reaches the G-code as
  `M572 S<value>`.
- The preset name defaults to `Prusament PLA Lightweight <T>C EM<em>`. Ids are derived from the name, so
  re-running with the same name overwrites the same preset instead of making a duplicate.
- What it sets: temperature, first layer temperature, EM, bed 60, constant fan 30 % (100 % on bridges, none on
  first layers, no dynamic overhang fans), no layer-time slowdown, retraction off (length 0, no wipe) and the
  datasheet density. Rationale and sources are in `README.md` and `com.community.pla-lw-temp-test/README.md`.

### 5. Verify with the real slicer (required)
```bash
python3 tools/resolve_stock.py --printer "<printer>" --print "<print profile>" \
  --material "<new preset name>" --with-preset "profiles/<file>.yaml" \
  --diff-against stock.json --out resolved.json
```
The slicer loads the new preset into the throwaway copy and resolves it. The differences from stock must be
**exactly** these (they are the intended edits; anything else means something was lost or mis-set):

`enable_dynamic_fan_speeds`, `extrusion_multiplier`, `filament_density`, `filament_max_volumetric_speed`
(unless `--speed 0`), `filament_notes`, `first_layer_temperature`, `max_fan_speed`, `min_fan_speed`,
`retract_before_wipe`, `retract_length`, `slowdown_below_layer_time`, `temperature`, `wipe`
(plus `pressure_advance_value` if `--pressure-advance` was used).

(Bed temperatures only show up if the stock value was not 60.) If the command says the slicer could not resolve
the profile names, the preset did not load: re-check the `--printers/--nozzle/--high-flow` condition against the
printer (step 4) and that `--list-materials` shows the new name.

### 5b. Check the real G-code (recommended)
```bash
python3 tools/check_gcode.py --printer "<printer>" --print "<print profile>" \
  --stock "<stock Prusament PLA name>" --material "<new preset name>" --with-preset "profiles/<file>.yaml"
```
It slices a two-cube model (travel between the cubes is where retraction happens) with stock PLA and with the new
preset, on a throwaway copy of the presets, and compares the G-code. Expect: retractions drop to 0, fan about 30 %
(255 only on bridges), speeds about 50 mm/s, the user's temperature, and the printer's own commands
(for example CORE One `M142 S36`) unchanged. If retractions are not 0, or speeds are still 150+ mm/s, something
did not take: tell the user instead of installing.

### 6. Install (ask first)
Writing into the user's PrusaSlicer folder is outside this repo, so **ask before doing it**:
```bash
python3 tools/make_profile.py ... --install        # same arguments as step 4, plus --install
```
(or copy the YAML to `<data folder>/presets/user/prusa-research-fff/PrusaResearch/`). Then tell the user to restart
PrusaSlicer 3, select their printer and pick the new filament. Never touch, rename or delete their existing
presets.

### 7. Tell the user what a filament preset cannot do
Say these in your reply; they live in the print preset or the slicer, not in the filament preset:
- "Avoid crossing perimeters" (max detour 40 mm) against stringing, one model at a time; this is a print setting;
- the printer profile needs no change: the filament preset overrides retraction (verified in G-code);
- dry the filament 5 h at 55 °C; ventilate (250 °C is Prusa's limit).
Be honest about status: the preset is verified to **load and resolve correctly in the slicer CLI**, but it has not
been test-printed unless the user says so.

## Repo map
| Path | What |
|---|---|
| `com.community.pla-lw-temp-test/` | the plugin bundle (`manifest.json`, `pla_lw_temp_test.lua`, README) |
| `tools/make_profile.py` | preset generator (stdlib only) |
| `tools/resolve_stock.py` | asks the slicer for resolved values; verifies presets |
| `tools/check_gcode.py` | slices a test model with stock vs new preset and compares the G-code |
| `tools/analyze_results.py` | caliper readings in, extrusion multiplier per band out; flags bad bands |
| `tools/lwcurve.py` | the flow curve, limits (190/210/240/250 °C) and zones, read from the plugin source |
| `tools/make_diagrams.py` | regenerates `docs/images/*.svg` from the plugin's numbers |
| `tests/` | `luajit tests/plugin_test.lua`; `python3 -I tests/profile_test.py`; `python3 -I tests/resolve_test.py`; `python3 -I tests/analyze_test.py`; `python3 -I tests/gcode_test.py` |

## Sources
Official Prusa documentation is linked (not copied) in `docs/REFERENCES.md`. Cite it, and when a number is not in
Prusa's material, say it is measured or assumed (the REFERENCES page lists which).

## Working on the code
- Run all five test files after any change. The Lua test uses a mock of the slicer API: it cannot prove the plugin
  works inside PrusaSlicer. Say so rather than implying it does.
- The flow curve (`EM_CURVE`, `EM_FLOOR` in the plugin) is built from Prusa's published numbers
  (datasheet 1.0 @ 215 °C and 0.38 @ 235 °C; blog 0.45 @ 230 °C). Do not change it without a source, and re-run
  `tools/make_diagrams.py`.
- The temperature limits (`MIN_TEMP`, `TEMP_OK_MIN`, `TEMP_OK_MAX`, `MAX_SAFE_TEMP`) live in the plugin source; the Python
  tools read them from there. If you change one, `tests/analyze_test.py` checks the fallbacks still agree.
- Plugin errors are only logged, never shown, so user-facing alerts must live in the model, the G-code or the
  printer display; refusals are a visible plate object. Only use dialog parameter types already proven to work
  (`int`, `float`, `bool`); `combobox` could not be verified against the slicer.
- The plugin API silently ignores settings of unsupported types (booleans, vectors); keep every plugin write
  read-back-verified or documented as best effort.
- Never publish personal paths or e-mail addresses in this public repo.
