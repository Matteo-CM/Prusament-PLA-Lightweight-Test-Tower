#!/usr/bin/env python3
"""Turn your caliper readings from the test tower into the extrusion multiplier for each temperature.

    python3 tools/analyze_results.py 210=0.62 220=0.55 230=0.50 240=0.47
    python3 tools/analyze_results.py 215=0.55 225=0.50 --perimeters 2 --pick 225

Each argument is  TEMP=WALL_MM  (average of your readings on the 30 mm side walls, upper half of the band).
The multiplier the tower printed each band with is read from the plugin's own curve, so you only type what
you measured. Standard library only.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lwcurve as lw  # noqa: E402

TARGET = {1: 0.48, 2: 0.90}   # mm: middle of Prusa's 0.45-0.50 for one perimeter; two lines overlap
TOLERANCE = 0.03              # mm: within this of the target counts as "on target"


def analyse(measurements, perimeters=1, target=None):
    """measurements: {temp: wall_mm}. Returns a list of row dicts sorted by temperature."""
    target = target if target is not None else TARGET[perimeters]
    rows = []
    for temp in sorted(measurements):
        wall = measurements[temp]
        em_used = lw.em_at(temp)
        needed = em_used * target / wall
        zone = lw.zone_of(temp)
        notes = []
        if temp > lw.MAX_SAFE_TEMP:
            notes.append("ABOVE %d C: toxic fumes, never print this" % lw.MAX_SAFE_TEMP)
        elif zone == "cold":
            notes.append("too cold (below %d C): not foaming, don't use" % lw.TEMP_OK_MIN)
        elif zone == "hot":
            notes.append("too hot (above %d C): surface degrades, don't use" % lw.TEMP_OK_MAX)
        if not (0.4 * target <= wall <= 2.0 * target):
            notes.append("wall %.2f mm looks like a measurement error (expected about %.2f)" % (wall, target))
        if not (0.2 <= needed <= 1.2):
            notes.append("multiplier %.2f is outside the sane range 0.2-1.2" % needed)
        rows.append({"temp": temp, "zone": zone, "em_used": em_used, "wall": wall, "em_needed": needed,
                     "on_target": abs(wall - target) <= TOLERANCE, "notes": notes})
    # the multiplier a foaming filament needs should fall as the temperature rises
    usable = [r for r in rows if r["zone"] == "ok"]
    for a, b in zip(usable, usable[1:]):
        if b["em_needed"] > a["em_needed"] * 1.08:
            b["notes"].append("needs MORE flow than %d C (%.2f vs %.2f); a hotter band should need less, so re-measure one of them"
                              % (a["temp"], b["em_needed"], a["em_needed"]))
    return rows


def parse_measure(text):
    try:
        t, w = text.split("=", 1)
        temp, wall = int(round(float(t))), float(w)
    except ValueError:
        raise argparse.ArgumentTypeError("%r is not TEMP=WALL_MM (e.g. 230=0.50)" % text)
    if wall <= 0:
        raise argparse.ArgumentTypeError("wall thickness must be positive: %r" % text)
    return temp, wall


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("measure", nargs="+", type=parse_measure, metavar="TEMP=WALL_MM", help="e.g. 230=0.50")
    ap.add_argument("--perimeters", type=int, choices=(1, 2), default=1, help="perimeters the tower was printed with (default 1)")
    ap.add_argument("--target", type=float, help="override the target wall in mm (default 0.48 for 1 perimeter, 0.90 for 2)")
    ap.add_argument("--pick", type=int, metavar="TEMP", help="temperature you chose; prints the profile command and a prompt for Claude")
    args = ap.parse_args(argv)

    meas = dict(args.measure)
    if any(t > lw.MAX_SAFE_TEMP for t in meas):
        print("error: %d C is above the %d C hard limit (toxic fumes); that band must not be printed or used."
              % (max(meas), lw.MAX_SAFE_TEMP), file=sys.stderr)
        return 2
    target = args.target if args.target is not None else TARGET[args.perimeters]
    rows = analyse(meas, args.perimeters, args.target)

    print("Target wall: %.2f mm (%d perimeter%s). Usable range: %d-%d C (first test print); hard limit %d C.\n"
          % (target, args.perimeters, "" if args.perimeters == 1 else "s", lw.TEMP_OK_MIN, lw.TEMP_OK_MAX, lw.MAX_SAFE_TEMP))
    print("%6s  %-6s %9s %9s %11s   %s" % ("temp", "zone", "EM used", "wall mm", "EM needed", "verdict"))
    for r in rows:
        verdict = "on target" if r["on_target"] else ("wall too thick: lower the multiplier" if r["wall"] > target else "wall too thin: raise the multiplier")
        print("%5d C  %-6s %9.2f %9.2f %11.2f   %s" % (r["temp"], r["zone"].upper(), r["em_used"], r["wall"], r["em_needed"], verdict))
        for n in r["notes"]:
            print("%36s! %s" % ("", n))

    usable = [r for r in rows if r["zone"] == "ok" and not any("measurement error" in n for n in r["notes"])]
    print()
    if not usable:
        print("No usable band measured. Measure the %d-%d C bands." % (lw.TEMP_OK_MIN, lw.TEMP_OK_MAX))
    else:
        print("Usable bands: %s." % ", ".join("%d C -> EM %.2f" % (r["temp"], r["em_needed"]) for r in usable))
        print("Choose the temperature by looking at the print too: the palest, lightest band is the most foamed, hotter bands")
        print("string more and are weaker. Then give Claude that temperature and its EM (or use --pick).")

    if args.pick is not None:
        chosen = next((r for r in rows if r["temp"] == args.pick), None)
        if chosen is None:
            print("\nerror: --pick %d is not one of the measured temperatures" % args.pick, file=sys.stderr)
            return 2
        if chosen["zone"] != "ok":
            print("\nerror: %d C is outside the usable range %d-%d C; pick a usable band." % (chosen["temp"], lw.TEMP_OK_MIN, lw.TEMP_OK_MAX), file=sys.stderr)
            return 2
        em = round(chosen["em_needed"], 2)
        print("\nYour choice: %d C with extrusion multiplier %.2f" % (chosen["temp"], em))
        print("\nAsk Claude (with this repo open):")
        print('  "Make me a Lightweight PLA filament profile for PrusaSlicer 3 with the %d degrees / %.2f combo."' % (chosen["temp"], em))
        print("\nOr run it yourself (see the README for the stock-preset step):")
        print("  python3 tools/make_profile.py --temp %d --em %.2f --stock-json stock.json --printers <BASE_MODEL> --nozzle <0.4>" % (chosen["temp"], em))
    return 0


if __name__ == "__main__":
    sys.exit(main())
