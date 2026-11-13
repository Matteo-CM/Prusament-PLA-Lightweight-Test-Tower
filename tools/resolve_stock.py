#!/usr/bin/env python3
"""Ask PrusaSlicer 3 itself for the fully resolved filament settings of a stock preset.

Why: a user filament preset that inherits "Prusament PLA" does NOT pick up that preset's
printer/nozzle-specific values (e.g. the CORE One heatbreak start G-code, the high-flow
volumetric speed limit). make_profile.py can copy those values in from the JSON this tool
writes (--stock-json).

The slicer is run on a THROWAWAY COPY of your presets, never on your real data folder.

Examples:
    python3 tools/resolve_stock.py --list-printers
    python3 tools/resolve_stock.py --list-materials "Prusa CORE One & One+ 0.4 HF"
    python3 tools/resolve_stock.py --printer "Prusa CORE One & One+ 0.4 HF" \\
        --print "0.20mm BALANCED @COREONE 0.4HF" \\
        --material "Prusament PLA @COREONE HF0.4@COREONE 0.4" --out stock.json
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

FLATPAK_ID = "com.prusa3d.PrusaSlicer"


def candidate_datadirs():
    home = os.path.expanduser("~")
    paths = [
        os.path.join(home, ".var/app/%s/config/PrusaSlicer3-dev" % FLATPAK_ID),
        os.path.join(home, ".config/PrusaSlicer3-dev"),
        os.path.join(home, "Library/Application Support/PrusaSlicer3-dev"),
    ]
    if os.environ.get("APPDATA"):
        paths.append(os.path.join(os.environ["APPDATA"], "PrusaSlicer3-dev"))
    return paths


def find_datadir(explicit):
    if explicit:
        return explicit if os.path.isdir(explicit) else None
    return next((p for p in candidate_datadirs() if os.path.isdir(p)), None)


def find_slicer(explicit):
    if explicit:
        return shlex.split(explicit)
    if shutil.which("flatpak"):
        out = subprocess.run(["flatpak", "list", "--app", "--columns=application"], capture_output=True, text=True)
        if FLATPAK_ID in out.stdout.split():
            return ["flatpak", "run", FLATPAK_ID]
    for exe in ("prusa-slicer", "PrusaSlicer", "prusa-slicer-3"):
        if shutil.which(exe):
            return [exe]
    return None


def workdir_parent(datadir, slicer):
    """The slicer must be able to see the work folder; a Flatpak only sees its own cache folder."""
    if slicer[:2] == ["flatpak", "run"]:
        base = os.path.join(os.path.expanduser("~"), ".var/app", FLATPAK_ID, "cache")
        if os.path.isdir(base):
            return base
    return None  # default temp dir


def diff_settings(a, b):
    """Return [(key, a_value, b_value)] for filament settings that differ (values are the slicer's lists)."""
    return [(k, a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


def run_cli(slicer, datadir, args, timeout=180):
    cmd = slicer + ["--datadir", datadir] + args
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir())
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slicer", help="slicer command (default: auto-detect Flatpak or prusa-slicer on PATH)")
    ap.add_argument("--datadir", help="PrusaSlicer 3 data folder (default: auto-detect)")
    ap.add_argument("--list-printers", action="store_true", help="list printer profile names")
    ap.add_argument("--list-materials", metavar="PRINTER", help="list print and filament profile names for a printer profile")
    ap.add_argument("--printer", help="printer profile name")
    ap.add_argument("--print", dest="print_profile", help="print profile name")
    ap.add_argument("--material", help="stock filament profile name, e.g. 'Prusament PLA @COREONE HF0.4@COREONE 0.4'")
    ap.add_argument("--with-preset", metavar="YAML", help="copy this user preset into the throwaway copy first, so --material "
                    "can name it (use this to verify a generated preset)")
    ap.add_argument("--diff-against", metavar="STOCK_JSON", help="print the settings that differ from this earlier resolved JSON")
    ap.add_argument("--out", default="stock.json", help="output JSON (the filament_settings of the resolved config)")
    args = ap.parse_args(argv)

    slicer = find_slicer(args.slicer)
    datadir = find_datadir(args.datadir)
    if not slicer:
        print("error: PrusaSlicer 3 not found; pass --slicer '<command>'", file=sys.stderr)
        return 3
    if not datadir:
        print("error: PrusaSlicer 3 data folder not found; pass --datadir", file=sys.stderr)
        return 3
    presets = os.path.join(datadir, "presets")
    if not os.path.isdir(presets):
        print("error: %s has no presets folder" % datadir, file=sys.stderr)
        return 3

    work = tempfile.mkdtemp(prefix="lw-resolve-", dir=workdir_parent(datadir, slicer))
    try:
        shutil.copytree(presets, os.path.join(work, "presets"))
        if args.with_preset:
            dest = os.path.join(work, "presets", "user", "prusa-research-fff", "PrusaResearch")
            os.makedirs(dest, exist_ok=True)
            shutil.copy(args.with_preset, dest)
        if args.list_printers:
            out = os.path.join(work, "models.json")
            res = run_cli(slicer, work, ["--query-printer-models", "--output", out])
            if not os.path.exists(out):
                print(res.stderr[-800:], file=sys.stderr)
                return 4
            for model in json.load(open(out))["printer_models"]:
                for var in model.get("variants", []):
                    for prof in var.get("printer_profiles", []):
                        print(prof["name"])
            return 0
        if args.list_materials:
            out = os.path.join(work, "fil.json")
            res = run_cli(slicer, work, ["--printer-profile", args.list_materials, "--query-print-tool-filament-profiles", "--output", out])
            if not os.path.exists(out):
                print(res.stderr[-800:], file=sys.stderr)
                return 4
            data = json.load(open(out))
            for p in data["print_profiles"]:
                print("print: %s" % p["name"])
            names = sorted({(f if isinstance(f, str) else f.get("name")) for p in data["print_profiles"] for f in p.get("filament_profiles", [])})
            for n in names:
                print("filament: %s" % n)
            return 0
        if not (args.printer and args.print_profile and args.material):
            print("error: --printer, --print and --material are required (or use --list-printers / --list-materials)", file=sys.stderr)
            return 2
        saved = os.path.join(work, "resolved.json")
        res = run_cli(slicer, work, ["--printer-profile", args.printer, "--print-profile", args.print_profile,
                                     "--material-profile", args.material, "--save", saved])
        if not os.path.exists(saved):
            print("error: the slicer could not resolve those profile names.\n%s" % res.stderr[-800:], file=sys.stderr)
            return 4
        settings = json.load(open(saved))["configuration"]["filament_settings"]
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=1, sort_keys=True)
        print("Wrote %s (%d filament settings)" % (args.out, len(settings)))
        if args.diff_against:
            with open(args.diff_against, encoding="utf-8") as fh:
                base = json.load(fh)
            rows = diff_settings(base, settings)
            print("\n%d settings differ from %s:" % (len(rows), args.diff_against))
            for k, a, b in rows:
                print("  %-36s %s -> %s" % (k, str(a)[:34], str(b)[:44]))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
