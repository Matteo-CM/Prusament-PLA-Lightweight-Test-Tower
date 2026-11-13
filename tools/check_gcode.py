#!/usr/bin/env python3
"""Prove what a generated filament preset really does: slice a test model with stock PrusaSlicer 3 presets
and with your new preset, then compare the G-code (retractions, fan, temperatures, flow, speeds, pressure advance).

The slicer runs on a THROWAWAY COPY of your presets, never on your real data folder.

    python3 tools/check_gcode.py --printer "Prusa CORE One & One+ 0.4 HF" --print "0.20mm BALANCED @COREONE 0.4HF" \\
        --stock "Prusament PLA @COREONE HF0.4@COREONE 0.4" --material "Prusament PLA Lightweight 230C EM0.43" \\
        --with-preset "profiles/filament-Prusament PLA Lightweight 230C EM0.43.yaml"
"""
import argparse
import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_stock as rs  # noqa: E402


def two_cubes_stl(size=20.0, gap=20.0):
    """ASCII STL of two cubes: the travel between them is where retraction and stringing happen."""
    def cube(x0):
        v = [(x0, 0, 0), (x0 + size, 0, 0), (x0 + size, size, 0), (x0, size, 0),
             (x0, 0, size), (x0 + size, 0, size), (x0 + size, size, size), (x0, size, size)]
        faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
        return "".join("facet normal 0 0 0\n outer loop\n" + "".join(" vertex %f %f %f\n" % v[i] for i in f) + " endloop\nendfacet\n" for f in faces)
    return "solid cubes\n" + cube(0.0) + cube(size + gap) + "endsolid cubes\n"


def analyse(text):
    """Summarise sliced G-code. Pure function (tested without a slicer)."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith(";LAYER_CHANGE")), 0)
    body = lines[start:]
    joined, body_joined = "\n".join(lines), "\n".join(body)
    # PrusaSlicer writes "G1 E-.7 F2700": the digit may follow a bare decimal point
    ret = [float(m.group(1)) for l in body for m in [re.match(r"G1 E-(\.?\d[\d.]*)", l)] if m]
    speeds, typ, feed = collections.defaultdict(list), None, None
    for l in body:
        m = re.match(r";TYPE:(.*)", l)
        if m:
            typ = m.group(1)
            continue
        m = re.search(r"\bF([\d.]+)", l)
        if m and l.startswith("G1"):
            feed = float(m.group(1))
        if re.match(r"G[123] .*E[\d.]", l) and not re.match(r"G1 E", l) and typ and feed:
            speeds[typ].append(feed / 60.0)
    stats = {k: (round(min(v)), round(sorted(v)[len(v) // 2]), round(max(v))) for k, v in speeds.items()}
    def num(pattern):
        m = re.search(pattern, joined)
        return m.group(1) if m else None
    return {
        "retractions": len(ret),
        "z_moves_in_travel": sum(1 for l in body if re.match(r"G1 X[-\d.]+ Y[-\d.]+ Z[-\d.]+", l)),
        "retraction_mm": sorted(set(ret)),
        "temperatures": sorted({int(t) for t in re.findall(r"M10[49] S(\d+)", joined) if int(t) > 0}),
        "fan_values": collections.Counter(int(v) for v in re.findall(r"M106 S(\d+)", body_joined)).most_common(5),
        "flow": sorted({int(v) for v in re.findall(r"M221 S(\d+)", joined)}),
        "heatbreak": [l for l in lines if l.startswith("M142")][:1],
        "pressure_advance": sorted({float(v) for v in re.findall(r"M572 S([\d.]+)", joined) if float(v) > 0}),
        "speeds": stats,
        "time": num(r"; estimated printing time \(normal mode\) = (.*)"),
        "filament_g": num(r"; total filament used \[g\] = ([\d.]+)"),
    }


def slice_once(slicer, work, printer, print_profile, material, stl, out):
    cmd = slicer + ["--datadir", work, "--printer-profile", printer, "--print-profile", print_profile,
                    "--material-profile", material, "--export-gcode", "--output", out, stl]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=tempfile.gettempdir())
    if not os.path.exists(out):
        raise RuntimeError("the slicer could not slice with '%s':\n%s" % (material, res.stderr[-600:]))
    return analyse(open(out, errors="ignore").read())


def report(stock, new):
    rows = [("retractions in the print (count)", "retractions"), ("retraction length (mm)", "retraction_mm"),
            ("travel moves that also change Z (Z-hop / ramping)", "z_moves_in_travel"),
            ("temperatures (M104/M109)", "temperatures"), ("fan M106 (value, uses)", "fan_values"),
            ("flow (M221 %)", "flow"), ("pressure advance (M572)", "pressure_advance"),
            ("heatbreak (M142)", "heatbreak"), ("estimated time", "time"), ("filament used (g)", "filament_g")]
    out = []
    for label, key in rows:
        out.append("%s\n    stock: %s\n    new  : %s" % (label, stock[key], new[key]))
    out.append("print speed mm/s (min, median, max) per feature\n    stock: %s\n    new  : %s" % (stock["speeds"], new["speeds"]))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--printer", required=True)
    ap.add_argument("--print", dest="print_profile", required=True)
    ap.add_argument("--stock", required=True, help="stock Prusament PLA profile name to compare against")
    ap.add_argument("--material", required=True, help="name of the new preset")
    ap.add_argument("--with-preset", required=True, metavar="YAML")
    ap.add_argument("--slicer")
    ap.add_argument("--datadir")
    args = ap.parse_args(argv)

    slicer, datadir = rs.find_slicer(args.slicer), rs.find_datadir(args.datadir)
    if not slicer or not datadir:
        print("error: PrusaSlicer 3 or its data folder not found; pass --slicer / --datadir", file=sys.stderr)
        return 3
    work = tempfile.mkdtemp(prefix="lw-gcode-", dir=rs.workdir_parent(datadir, slicer))
    try:
        shutil.copytree(os.path.join(datadir, "presets"), os.path.join(work, "presets"))
        dest = os.path.join(work, "presets", "user", "prusa-research-fff", "PrusaResearch")
        os.makedirs(dest, exist_ok=True)
        shutil.copy(args.with_preset, dest)
        stl = os.path.join(work, "two_cubes.stl")
        open(stl, "w").write(two_cubes_stl())
        try:
            stock = slice_once(slicer, work, args.printer, args.print_profile, args.stock, stl, os.path.join(work, "stock.gcode"))
            new = slice_once(slicer, work, args.printer, args.print_profile, args.material, stl, os.path.join(work, "new.gcode"))
        except RuntimeError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 4
        print(report(stock, new))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
