#!/usr/bin/env python3
"""Generate a PrusaSlicer 3 filament preset (YAML) for Lightweight / foaming PLA.

Give it the two numbers you found with the test tower (temperature and
extrusion multiplier) and it writes a ready-to-use filament preset that
inherits from the standard "Prusament PLA" profile and overrides what
Lightweight PLA needs: temperature, extrusion multiplier, fan, slowdown,
retraction and bed.

    python3 tools/make_profile.py --temp 240 --em 0.37

Standard library only (Python 3.8+). The output layout mirrors the filament
presets PrusaSlicer 3.0 alpha writes itself into
<datadir>/presets/user/prusa-research-fff/PrusaResearch/filament-<name>.yaml
"""
import argparse
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lwcurve  # noqa: E402  (limits and usable range come from the plugin source)

PARENT_DEFAULT = "Prusament PLA"
# Same printer list and exclusion the stock "Prusament PLA" preset uses.
PRINTERS_DEFAULT = "COREONE|MK4|MK3.5|MK2|XL|MK3|MK2.5|MINI|COREONE_INDX"
BRAND_SLUG = "prusament"
BRAND_UUID = "ae5ff34e-298e-50c9-8f77-92a97fb30b09"  # Prusament, as in the stock presets
NAMESPACE = uuid.UUID("6f1c2d4e-5b7a-4c3e-9d1a-2e8b4f6a7c90")  # for stable ids

# Printer/nozzle-specific values of the stock preset that an inheriting user preset does NOT pick up
# (verified against the slicer: a child of "Prusament PLA" falls back to the generic values).
# They are copied from a resolved stock config (tools/resolve_stock.py) when --stock-json is given.
BAKE_KEYS = [
    "start_filament_gcode",            # CORE One: M142 heatbreak target
    "filament_max_volumetric_speed",   # high-flow nozzles allow more
    "min_print_speed",
    "fan_below_layer_time",
    "filament_purge_multiplier",
    "filament_ramming_parameters",
    "filament_infill_max_crossing_speed",
    "filament_infill_max_speed",
    "pressure_advance",
    "pressure_advance_value",
]

PRUSA_MAX_VOLUMETRIC = 4.0   # mm^3/s: filament_max_volumetric_speed in every official Lightweight profile
MAX_TEMP = lwcurve.MAX_SAFE_TEMP  # Prusa: never above 250 C with this filament (toxic fumes)
MIN_TEMP = lwcurve.MIN_TEMP


def build_condition(printers, nozzle, high_flow):
    """Preset visibility condition, in the same expression language as the stock presets."""
    parts = ["printer.base_model=~/(%s)/" % printers]
    if nozzle is not None:
        parts.append("tool.nozzle_diameter == %s" % format_number(nozzle))
    if high_flow is True:
        parts.append("tool.nozzle_high_flow")
    elif high_flow is False:
        parts.append("not tool.nozzle_high_flow")
    parts.append("! print.high_temp_printhead")
    return " and ".join(parts)


def format_number(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    text = ("%.6f" % v).rstrip("0").rstrip(".")
    return text or "0"


_PLAIN = re.compile(r"^[A-Za-z0-9_./()=<>!|+$ -]+$")


def yaml_scalar(v):
    """Minimal YAML scalar writer: plain when safe, otherwise single-quoted."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return format_number(v)
    s = str(v)
    needs_quote = (
        s == ""
        or not _PLAIN.match(s)
        or s != s.strip()
        or s[0] in "-?:,[]{}#&*!|>'\"%@`"
        or ": " in s
        or " #" in s
        or s.lower() in ("true", "false", "null", "yes", "no", "on", "off", "~")
        or re.match(r"^[0-9.+-]+%?$", s)
    )
    if needs_quote:
        return "'" + s.replace("'", "''") + "'"
    return s


def bake_value(raw):
    """Convert a value from the slicer's resolved JSON to something yaml_scalar can write, or None to skip."""
    if isinstance(raw, list):
        if not raw:
            return None
        raw = raw[0]
    if isinstance(raw, dict):
        if "value" in raw and "is_percent" in raw:
            return format_number(raw["value"]) + ("%" if raw["is_percent"] else "")
        return None
    if isinstance(raw, bool):
        return 1 if raw else 0
    if raw is None:
        return None
    return raw


def load_stock(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if "configuration" in data:  # whole slicer --save output
        data = data["configuration"]["filament_settings"]
    return data


def volumetric_limit(speed, layer_height=0.2, line_width=0.45):
    """mm^3/s that corresponds to `speed` mm/s for a line of that width and height.

    Foaming depends on how long the filament sits in the hot end, i.e. on the volume pushed through per
    second, so the filament-level 'maximum volumetric speed' is the right control: the slicer slows any
    feature that would exceed it. Cross-section as PrusaSlicer models it (rounded rectangle)."""
    area = (line_width - layer_height) * layer_height + 3.141592653589793 * (layer_height / 2.0) ** 2
    return round(speed * area, 2)


def safe_name(name):
    name = re.sub(r"[^A-Za-z0-9 ._+-]", "", name).strip()
    return re.sub(r"\s+", " ", name)


def make_preset(args):
    """Return (preset_name, yaml_text, values_dict)."""
    temp = int(round(args.temp))
    em = float(args.em)
    if not (MIN_TEMP <= temp <= MAX_TEMP):
        raise ValueError("--temp must be between %d and %d C (Prusa: never above %d C)" % (MIN_TEMP, MAX_TEMP, MAX_TEMP))
    if not (0.2 <= em <= 1.2):
        raise ValueError("--em must be between 0.2 and 1.2 (Prusa's LW-PLA range is about 1 to 0.35)")
    first = int(round(args.first_layer_temp)) if args.first_layer_temp is not None else temp
    if not (MIN_TEMP <= first <= MAX_TEMP):
        raise ValueError("--first-layer-temp must be between %d and %d C" % (MIN_TEMP, MAX_TEMP))
    for label, t in (("--temp", temp), ("--first-layer-temp", first)):
        if t > lwcurve.TEMP_OK_MAX or t < lwcurve.TEMP_OK_MIN:
            args._warnings = getattr(args, "_warnings", []) + [
                "%s %d C is outside the usable range %d-%d C found in the test print (%s)" % (
                    label, t, lwcurve.TEMP_OK_MIN, lwcurve.TEMP_OK_MAX,
                    "too cold: the filament will not foam" if t < lwcurve.TEMP_OK_MIN else "too hot: the surface degrades; never exceed %d C" % lwcurve.MAX_SAFE_TEMP)]
    if args.speed is not None and (args.speed < 0 or args.speed > 100):
        raise ValueError("--speed must be 0-100 mm/s (datasheet: up to 100; 0 = do not limit the speed)")
    for label, val in (("--fan", args.fan), ("--bridge-fan", args.bridge_fan)):
        if not (0 <= val <= 100):
            raise ValueError("%s must be 0-100 %%" % label)
    if not (30 <= args.bed <= 110):
        raise ValueError("--bed must be 30-110 C")

    name = safe_name(args.name or "Prusament PLA Lightweight %dC EM%s" % (temp, format_number(em)))
    if not name:
        raise ValueError("--name produced an empty preset name")

    values = {
        # what the test tower measures
        "extrusion_multiplier": em,
        "temperature": temp,
        "first_layer_temperature": first,
        # bed (datasheet: 60 +/- 10 C)
        "bed_temperature": args.bed,
        "first_layer_bed_temperature": args.bed,
        # cooling, as in Prusa's own Lightweight profiles: automatic cooling OFF, so the fan simply runs at
        # min_fan_speed (30 on CORE One / MK4S / XL+, 45-50 on some other printers), 100 % on bridges and (stock
        # dynamic overhang fans) on overhangs, none on the first layers; no layer-time slowdown
        "cooling": 0,
        "fan_always_on": 1,
        "min_fan_speed": args.fan,
        "bridge_fan_speed": args.bridge_fan,
        "disable_fan_first_layers": 1,
        "full_fan_speed_layer": 3,
        "slowdown_below_layer_time": args.slowdown,
        # no Z-hop and no travel Z-ramping, as in Prusa's profiles
        "retract_lift": 0,
        "travel_ramping_lift": 0,
        # retraction does not work well with foaming filament (Prusa blog and Knowledge Base)
        # NOTE: Prusa's shipped profile does not override the retraction length; see --keep-retraction
        **({} if args.keep_retraction else {"retract_length": args.retract, "retract_before_wipe": "0%", "wipe": 0}),
        # datasheet density of the unfoamed filament
        "filament_density": 1.18,
        "filament_notes": "Made with Prusament-PLA-Lightweight-Test-Tower: %d C, extrusion multiplier %s" % (temp, format_number(em)),
    }

    # Prusa's Lightweight profiles switch pressure advance off ("M572 S0") on every printer
    if not args.keep_pressure_advance:
        if not (0 <= args.pressure_advance <= 1):
            raise ValueError("--pressure-advance must be between 0 and 1")
        values["pressure_advance_value"] = args.pressure_advance

    if args.max_volumetric_speed is not None:
        values["filament_max_volumetric_speed"] = args.max_volumetric_speed
    elif args.speed is None:
        values["filament_max_volumetric_speed"] = PRUSA_MAX_VOLUMETRIC   # Prusa's own value
    elif args.speed:
        values["filament_max_volumetric_speed"] = volumetric_limit(args.speed)

    baked = []
    if getattr(args, "stock_json", None):
        stock = load_stock(args.stock_json)
        for key in BAKE_KEYS:
            if key in values or key not in stock:
                continue
            val = bake_value(stock[key])
            if val is None:
                continue
            values[key] = val
            baked.append(key)
    args._baked = baked

    condition = args.condition or build_condition(args.printers, args.nozzle, args.high_flow)
    preset_id = str(uuid.uuid5(NAMESPACE, name))
    variant_id = str(uuid.uuid5(NAMESPACE, name + "/variant"))

    lines = [
        "kind: filament",
        "id: %s" % preset_id,
        "variants:",
        "  - condition: %s" % yaml_scalar(condition),
        "    id: %s" % variant_id,
        "    name: %s" % yaml_scalar(name),
        "    unconditional_inherits:",
        "      - %s" % yaml_scalar(args.parent),
        "    values:",
    ]
    for key, val in values.items():
        lines.append("      %s: %s" % (key, yaml_scalar(val)))
    lines += [
        "    features:",
        "      $.brand.slug: %s" % BRAND_SLUG,
        "      $.brand.uuid: %s" % BRAND_UUID,
        "      $.type: PLA",
        "      based_id: %s" % yaml_scalar(args.parent),
        "      based_root_id: %s" % yaml_scalar(args.parent),
    ]
    return name, "\n".join(lines) + "\n", values


def candidate_datadirs():
    home = os.path.expanduser("~")
    paths = [
        os.path.join(home, ".var/app/com.prusa3d.PrusaSlicer/config/PrusaSlicer3-dev"),  # Flatpak
        os.path.join(home, ".config/PrusaSlicer3-dev"),                                  # Linux
        os.path.join(home, "Library/Application Support/PrusaSlicer3-dev"),             # macOS
    ]
    if os.environ.get("APPDATA"):
        paths.append(os.path.join(os.environ["APPDATA"], "PrusaSlicer3-dev"))            # Windows
    return paths


def find_datadir(explicit):
    if explicit:
        return explicit if os.path.isdir(explicit) else None
    for p in candidate_datadirs():
        if os.path.isdir(p):
            return p
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--temp", type=float, required=True, help="nozzle temperature in C (from the test tower label)")
    ap.add_argument("--em", type=float, required=True, help="extrusion multiplier (from the label, or your corrected value)")
    ap.add_argument("--name", help="preset name (default: Prusament PLA Lightweight <temp>C EM<em>)")
    ap.add_argument("--first-layer-temp", type=float, help="first layer temperature (default: same as --temp)")
    ap.add_argument("--bed", type=int, default=60, help="bed temperature (default 60)")
    ap.add_argument("--fan", type=int, default=30, help="fan speed %% (default 30: Prusa's value for CORE One, MK4S and XL+; their MK4/MK3.9 "
                    "profile uses 45 and XL 0.4 HF uses 50)")
    ap.add_argument("--bridge-fan", type=int, default=100, help="fan %% on bridges (datasheet 100)")
    ap.add_argument("--slowdown", type=int, default=0, help="slowdown_below_layer_time in s (default 0 = off)")
    ap.add_argument("--speed", type=float, default=None, help="target print speed in mm/s, applied as a maximum volumetric speed. "
                    "Default: Prusa's own limit of 4 mm3/s (about 49 mm/s at 0.2 mm layers); datasheet: up to 100; 0 = leave the stock limit")
    ap.add_argument("--max-volumetric-speed", type=float, help="set the limit in mm^3/s directly (overrides --speed)")
    ap.add_argument("--pressure-advance", type=float, default=0.0, help="pressure advance value (default 0: off, as in all of Prusa's "
                    "Lightweight profiles, which send M572 S0)")
    ap.add_argument("--keep-pressure-advance", action="store_true", help="keep the stock preset's pressure advance instead")
    ap.add_argument("--keep-retraction", action="store_true", help="do not override retraction (this is what Prusa's shipped profile does; "
                    "the default here is retraction off, as in Prusa's blog post and Knowledge Base)")
    ap.add_argument("--retract", type=float, default=0, help="retraction length in mm (default 0 = off)")
    ap.add_argument("--parent", default=PARENT_DEFAULT, help="preset to inherit from (default 'Prusament PLA')")
    ap.add_argument("--printers", default=PRINTERS_DEFAULT, help="printer base_model regex alternatives, '|' separated")
    ap.add_argument("--nozzle", type=float, help="restrict to a nozzle diameter, e.g. 0.4")
    hf = ap.add_mutually_exclusive_group()
    hf.add_argument("--high-flow", dest="high_flow", action="store_true", default=None, help="only high-flow nozzles")
    hf.add_argument("--standard-flow", dest="high_flow", action="store_false", help="only non-high-flow nozzles")
    ap.add_argument("--stock-json", help="resolved stock filament settings from tools/resolve_stock.py; copies the "
                    "printer/nozzle-specific keys (start G-code, volumetric speed, ...) into the preset")
    ap.add_argument("--condition", help="full custom visibility condition (overrides --printers/--nozzle/flow)")
    ap.add_argument("--out", default="profiles", help="output folder (default ./profiles)")
    ap.add_argument("--install", action="store_true", help="also copy into the PrusaSlicer 3 data folder")
    ap.add_argument("--datadir", help="PrusaSlicer 3 data folder for --install (default: auto-detect)")
    ap.add_argument("--print", dest="print_only", action="store_true", help="print the YAML, write nothing")
    args = ap.parse_args(argv)

    try:
        name, text, values = make_preset(args)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    for w in getattr(args, "_warnings", []):
        print("WARNING: %s" % w, file=sys.stderr)

    if args.print_only:
        sys.stdout.write(text)
        return 0

    filename = "filament-%s.yaml" % name
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, filename)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("Wrote %s" % out_path)
    if getattr(args, "_baked", None):
        print("Copied printer-specific values from the stock preset: %s" % ", ".join(args._baked))
    elif not args.stock_json:
        print("note: no --stock-json given, so printer/nozzle-specific values of the stock preset (CORE One heatbreak "
              "start G-code, high-flow volumetric limit, ...) fall back to the generic Prusament PLA ones. "
              "See tools/resolve_stock.py.")

    if args.install:
        datadir = find_datadir(args.datadir)
        if not datadir:
            print("error: PrusaSlicer 3 data folder not found; pass --datadir (the folder with PrusaSlicer.ini)", file=sys.stderr)
            return 3
        dest_dir = os.path.join(datadir, "presets", "user", "prusa-research-fff", "PrusaResearch")
        if not os.path.isdir(dest_dir):
            print("error: %s does not exist; open PrusaSlicer 3 once and save any preset first" % dest_dir, file=sys.stderr)
            return 3
        dest = os.path.join(dest_dir, filename)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("Installed %s" % dest)
        print("Restart PrusaSlicer 3, select your printer, then pick '%s' as the filament." % name)
    else:
        print("To use it: copy it into <PrusaSlicer 3 data folder>/presets/user/prusa-research-fff/PrusaResearch/ "
              "and restart PrusaSlicer 3 (or re-run with --install).")

    print("\nStill to set in the PRINT preset (a filament preset cannot hold these):")
    print("  - print speed about 50 mm/s (faster needs a higher temperature to foam as much)")
    print("  - 'Avoid crossing perimeters' (max detour 40 mm) to reduce stringing")
    print("  - dry the filament 5 h at 55 C")
    return 0


if __name__ == "__main__":
    sys.exit(main())
