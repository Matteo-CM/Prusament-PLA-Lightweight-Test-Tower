#!/usr/bin/env python3
"""Read Prusa's OFFICIAL Prusament PLA Lightweight profiles from their GitHub repository and compare your
generated profile with them.

Source: https://github.com/prusa3d/PrusaSlicer-settings-prusa-fff (PrusaResearch/<version>.ini). Prusa ships the
Lightweight profiles there as part of their vendor bundle (added in 2.5.10). The inheritance chain
("inherits = a; b; c") is resolved the way PrusaSlicer does: parents left to right, later ones override earlier
ones, the preset's own keys win.

    python3 tools/official_lw.py --list
    python3 tools/official_lw.py --variant "COREONE HF0.4"
    python3 tools/official_lw.py --variant "COREONE HF0.4" --compare profiles/filament-X.yaml

Needs network access (or --file with a local copy of the .ini). Standard library only.
"""
import argparse
import re
import sys
import urllib.request

BASE = "https://raw.githubusercontent.com/prusa3d/PrusaSlicer-settings-prusa-fff/main/PrusaResearch/"
PREFIX = "Prusament PLA Lightweight @"

# (key in our 3.0 YAML preset, official key in the 2.x .ini, how to read it)
COMPARE = [
    ("extrusion_multiplier", "extrusion_multiplier"),
    ("temperature", "temperature"),
    ("first_layer_temperature", "first_layer_temperature"),
    ("bed_temperature", "bed_temperature"),
    ("cooling", "cooling"),
    ("min_fan_speed", "min_fan_speed"),
    ("bridge_fan_speed", "bridge_fan_speed"),
    ("filament_max_volumetric_speed", "filament_max_volumetric_speed"),
    ("retract_lift", "filament_retract_lift"),
    ("travel_ramping_lift", "filament_travel_ramping_lift"),
    ("filament_density", "filament_density"),
    ("slowdown_below_layer_time", "slowdown_below_layer_time"),
]


def parse_ini(text):
    secs, cur = {}, None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith((";", "#")):
            continue
        m = re.match(r"^\[(.+)\]$", s)
        if m:
            cur = m.group(1)
            secs[cur] = {}
        elif cur is not None and "=" in line:
            k, v = line.split("=", 1)
            secs[cur][k.strip()] = v.strip()
    return secs


def resolve(secs, name, kind="filament", _seen=()):
    key = "%s:%s" % (kind, name)
    if key not in secs:
        raise KeyError(key)
    if key in _seen:
        raise RuntimeError("inheritance cycle at " + key)
    out = {}
    for parent in [p.strip() for p in secs[key].get("inherits", "").split(";") if p.strip()]:
        out.update(resolve(secs, parent, kind, _seen + (key,)))
    out.update({k: v for k, v in secs[key].items() if k != "inherits"})
    return out


def variants(secs):
    return sorted(n[len("filament:" + PREFIX):] for n in secs if n.startswith("filament:" + PREFIX))


def latest_version(idx_text):
    versions = [m.group(1) for line in idx_text.splitlines() for m in [re.match(r"^(\d+\.\d+\.\d+)\b", line)] if m]
    if not versions:
        raise ValueError("no versions found in index.idx")
    return max(versions, key=lambda v: tuple(int(x) for x in v.split(".")))


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lw-pla-test-tower"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def pressure_advance_of(values):
    g = values.get("start_filament_gcode", "")
    m = re.search(r"M572 S([\d.]+)", g)
    return m.group(1) if m else None


def read_yaml_values(path):
    """The flat `values:` block of one of our generated presets (no YAML library needed)."""
    out, inside = {}, False
    for line in open(path, encoding="utf-8"):
        if line.strip() == "values:":
            inside = True
            continue
        if inside:
            m = re.match(r"^      ([A-Za-z0-9_]+): (.*)$", line.rstrip("\n"))
            if not m:
                break
            out[m.group(1)] = m.group(2).strip().strip("'")
    return out


def same(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a) == str(b)


def compare(official, ours):
    """Rows (key, official, ours, status) with status 'same', 'differs' or 'not set by us'."""
    rows = []
    for ykey, ikey in COMPARE:
        o, u = official.get(ikey), ours.get(ykey)
        rows.append((ykey, o, u, "not set by us" if u is None else ("same" if same(o, u) else "differs")))
    po, pu = pressure_advance_of(official), ours.get("pressure_advance_value")
    rows.append(("pressure advance (M572 S)", po, pu, "not set by us" if pu is None else ("same" if same(po, pu) else "differs")))
    ro, ru = official.get("filament_retract_length"), ours.get("retract_length")
    rows.append(("retract_length", ro if ro is not None else "(not overridden: printer value)", ru,
                 "not set by us" if ru is None else ("same" if same(ro, ru) else "differs")))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="local .ini instead of downloading the newest bundle")
    ap.add_argument("--list", action="store_true", help="list the official Lightweight variants")
    ap.add_argument("--variant", help="e.g. 'COREONE HF0.4', 'MK4S', 'XL+ HF0.4' (see --list)")
    ap.add_argument("--compare", metavar="YAML", help="compare one of our generated presets with the official variant")
    args = ap.parse_args(argv)

    if args.file:
        text, source = open(args.file, encoding="utf-8", errors="ignore").read(), args.file
    else:
        version = latest_version(fetch(BASE + "index.idx"))
        text, source = fetch(BASE + version + ".ini"), "prusa3d/PrusaSlicer-settings-prusa-fff PrusaResearch/%s.ini" % version
    secs = parse_ini(text)
    names = variants(secs)
    print("Source: %s  (%d official Lightweight variants)\n" % (source, len(names)))
    if args.list or not args.variant:
        for n in names:
            v = resolve(secs, PREFIX + n)
            print("  %-16s EM %-5s %s C  fan %-3s  max vol %s mm3/s  cooling %s" % (
                n, v.get("extrusion_multiplier"), v.get("temperature"), v.get("min_fan_speed"),
                v.get("filament_max_volumetric_speed"), v.get("cooling")))
        return 0
    name = args.variant if args.variant in names else next((n for n in names if n.lower() == args.variant.lower()), None)
    if name is None:
        print("error: unknown variant %r; use --list" % args.variant, file=sys.stderr)
        return 2
    off = resolve(secs, PREFIX + name)
    if args.compare:
        rows = compare(off, read_yaml_values(args.compare))
        print("%-32s %-30s %-12s %s" % ("setting", "official " + name, "ours", ""))
        for k, o, u, st in rows:
            print("%-32s %-30s %-12s %s" % (k, str(o)[:30], str(u), "" if st == "same" else "<-- " + st))
        diff = [r for r in rows if r[3] == "differs"]
        print("\n%d of %d compared settings differ from Prusa's official profile." % (len(diff), len(rows)))
        return 0
    for k in sorted(off):
        if k in ("start_filament_gcode", "filament_notes"):
            continue
        print("%-34s %s" % (k, off[k][:80]))
    print("%-34s %s" % ("(pressure advance from G-code)", "M572 S" + str(pressure_advance_of(off))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
