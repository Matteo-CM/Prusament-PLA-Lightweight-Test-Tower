#!/usr/bin/env python3
"""Regenerate docs/images/*.svg. The flow curve is read from the plugin source, so the chart
cannot disagree with the code.   python3 tools/make_diagrams.py
"""
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "docs", "images")
SRC = open(os.path.join(ROOT, "com.community.pla-lw-temp-test", "pla_lw_temp_test.lua"), encoding="utf-8").read()

pts = [(int(a), float(b)) for a, b in re.findall(r"\{(\d+),\s*([\d.]+)\}", re.search(r"local EM_CURVE = (\{.*?\})\n", SRC).group(1))]
FLOOR = float(re.search(r"local EM_FLOOR = ([\d.]+)", SRC).group(1))
MIN_T = int(re.search(r"local MIN_TEMP = (\d+)", SRC).group(1))
MAX_T = int(re.search(r"local MAX_SAFE_TEMP = (\d+)", SRC).group(1))


def em(t):
    if t <= pts[0][0]:
        return pts[0][1]
    for i in range(1, len(pts)):
        if t <= pts[i][0]:
            f = (t - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0])
            return pts[i - 1][1] + f * (pts[i][1] - pts[i - 1][1])
    return max(FLOOR, pts[-1][1] - 0.002 * (t - pts[-1][0]))


FONT = 'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"'
INK, MUTED, ORANGE, GRID, BLUE, RED = "#1f2328", "#59636e", "#e8641c", "#e1e4e8", "#0969da", "#cf222e"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def T(x, y, s, size=14, fill=INK, anchor="start", weight="400"):
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>'


def card(W, H, label):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(label)}">',
            f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="#ffffff" stroke="#d0d7de"/>']


def write(name, lines):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines + ["</svg>"]))


def curve():
    W, H, L, R, Tp, B = 920, 490, 80, 40, 70, 100
    pw, ph = W - L - R, H - Tp - B
    x = lambda t: L + (t - 203) / (252 - 203) * pw
    y = lambda v: Tp + (1.05 - v) / (1.05 - 0.25) * ph
    o = card(W, H, "Extrusion multiplier versus nozzle temperature for Lightweight PLA")
    o += [T(W / 2, 34, "Flow has to drop as the filament gets hotter", 20, INK, "middle", "700"),
          T(W / 2, 56, "Extrusion multiplier per band (1.0 = the standard Prusament PLA profile)", 13, MUTED, "middle")]
    o.append(f'<rect x="{x(215):.1f}" y="{Tp}" width="{x(235) - x(215):.1f}" height="{ph:.1f}" fill="#fff4ec"/>')
    o.append(T((x(215) + x(235)) / 2, Tp + ph - 10, "foaming range (Prusa)", 12, ORANGE, "middle", "600"))
    for v in (0.4, 0.6, 0.8, 1.0):
        o.append(f'<line x1="{L}" y1="{y(v):.1f}" x2="{W - R}" y2="{y(v):.1f}" stroke="{GRID}"/>' + T(L - 10, y(v) + 4, f"{v:.1f}", 12, MUTED, "end"))
    for t in range(MIN_T, MAX_T + 1, 5):
        o.append(f'<line x1="{x(t):.1f}" y1="{Tp + ph:.1f}" x2="{x(t):.1f}" y2="{Tp + ph + 6:.1f}" stroke="{MUTED}"/>' + T(x(t), Tp + ph + 22, str(t), 12, MUTED, "middle"))
    o.append(T(L + pw / 2, Tp + ph + 46, "Nozzle temperature (°C): the 10 bands of the tower", 13, MUTED, "middle"))
    o.append(f'<text transform="translate(22,{Tp + ph / 2:.1f}) rotate(-90)" {FONT} font-size="13" fill="{MUTED}" text-anchor="middle">extrusion multiplier</text>')

    def path(t0, t1):
        return "M" + " L".join(f"{x(t):.1f},{y(em(t)):.1f}" for t in [t0 + i * (t1 - t0) / 40 for i in range(41)])
    o.append(f'<path d="{path(MIN_T, 215)}" fill="none" stroke="{ORANGE}" stroke-width="3" stroke-dasharray="6 5"/>')
    o.append(f'<path d="{path(215, 235)}" fill="none" stroke="{ORANGE}" stroke-width="3.5"/>')
    o.append(f'<path d="{path(235, MAX_T)}" fill="none" stroke="{ORANGE}" stroke-width="3" stroke-dasharray="6 5"/>')
    for t in range(MIN_T, MAX_T + 1, 5):
        o.append(f'<circle cx="{x(t):.1f}" cy="{y(em(t)):.1f}" r="4" fill="#ffffff" stroke="{ORANGE}" stroke-width="2"/>')
    for t, v, lab, dx, dy, anc in [(215, 1.0, "1.00 · datasheet", 10, 26, "start"), (230, 0.45, "0.45 · Prusa default profile", -12, -14, "end"), (235, 0.38, "0.38 · datasheet", 12, -14, "start")]:
        o.append(f'<circle cx="{x(t):.1f}" cy="{y(v):.1f}" r="7" fill="{ORANGE}" stroke="#fff" stroke-width="2"/>' + T(x(t) + dx, y(v) + dy, lab, 13, INK, anc, "600"))
    o.append(T(x(MAX_T) - 4, y(FLOOR) - 14, "0.35 · floor (assumed)", 12, MUTED, "end"))
    o.append(T(x(MIN_T) + 2, y(1.0) - 14, "held at 1.0 (assumed)", 12, MUTED, "start"))
    o.append(f'<line x1="{x(MAX_T):.1f}" y1="{Tp}" x2="{x(MAX_T):.1f}" y2="{Tp + ph:.1f}" stroke="{RED}" stroke-dasharray="4 4"/>' + T(x(MAX_T) - 6, Tp + 14, "never above 250 °C", 12, RED, "end", "600"))
    ly = H - 22
    o.append(f'<circle cx="{L + 8}" cy="{ly - 4}" r="6" fill="{ORANGE}"/>' + T(L + 22, ly, "published by Prusa", 12, MUTED)
             + f'<circle cx="{L + 176}" cy="{ly - 4}" r="4" fill="#fff" stroke="{ORANGE}" stroke-width="2"/>' + T(L + 188, ly, "one band of the tower (interpolated, or assumed outside Prusa’s points)", 12, MUTED))
    write("em-curve.svg", o)


def workflow():
    W, H = 1000, 280
    steps = [("1", "Print the tower", "Plugins → Calibration →\nPLA Lightweight\nTemp Test"),
             ("2", "Measure", "calipers on the 30 mm\nside walls, upper half\nof each band"),
             ("3", "Calculate", "EM = EM_band × 0.48\n÷ measured wall (mm)"),
             ("4", "Ask Claude", "“Make a Lightweight PLA\nprofile for PrusaSlicer 3:\n240 °C / 0.37”"),
             ("5", "Print with it", "restart PrusaSlicer 3,\npick the new filament")]
    o = card(W, H, "Workflow: print, measure, calculate, ask Claude, print")
    o.append(T(W / 2, 38, "From one test print to your own filament profile", 20, INK, "middle", "700"))
    bw, gap = 172, 20
    x0 = (W - (5 * bw + 4 * gap)) / 2
    for i, (n, title, body) in enumerate(steps):
        bx = x0 + i * (bw + gap)
        hi = n == "4"
        o.append(f'<rect x="{bx:.1f}" y="64" width="{bw}" height="176" rx="10" fill="{"#fff4ec" if hi else "#f6f8fa"}" stroke="{ORANGE if hi else "#d0d7de"}" stroke-width="{2 if hi else 1}"/>')
        o.append(f'<circle cx="{bx + 24:.1f}" cy="92" r="14" fill="{ORANGE}"/>' + T(bx + 24, 97, n, 15, "#fff", "middle", "700"))
        o.append(T(bx + 46, 97, title, 15, INK, "start", "700"))
        for j, line in enumerate(body.split("\n")):
            o.append(T(bx + 14, 132 + j * 22, line, 13, MUTED))
        if i < 4:
            o.append(f'<path d="M{bx + bw + 3:.1f},152 l{gap - 6},0 m-5,-5 l5,5 l-5,5" fill="none" stroke="{MUTED}" stroke-width="2"/>')
    write("workflow.svg", o)


def layout():
    W, H, s = 760, 470, 7.2
    bx0, by0 = 230, 96
    bw, bd = 50 * s, 30 * s
    o = card(W, H, "Top view of the test box showing where to measure")
    o.append(T(W / 2, 36, "Top view of the test box (50 × 30 mm)", 20, INK, "middle", "700"))
    o.append(f'<rect x="{bx0}" y="{by0}" width="{bw}" height="{bd}" fill="#f6f8fa" stroke="{MUTED}" stroke-width="3"/>')
    for sx in (bx0, bx0 + bw):
        o.append(f'<line x1="{sx}" y1="{by0}" x2="{sx}" y2="{by0 + bd}" stroke="{ORANGE}" stroke-width="8"/>')
    tw, th = 30 * s, 3 * s * 2.2
    o.append(f'<rect x="{bx0 + (bw - tw) / 2}" y="{by0 + bd}" width="{tw}" height="{th}" fill="#d0d7de" stroke="{MUTED}" stroke-width="2"/>' + T(bx0 + bw / 2, by0 + bd + th / 2 + 5, "205 / 1.00", 13, INK, "middle", "600"))
    o.append(T(bx0 + bw / 2, by0 + bd + th + 26, "FRONT — label tab (30 × 3 mm)", 14, INK, "middle", "700"))
    o.append(T(bx0 + bw / 2, by0 - 14, "REAR — the seam is here, don’t measure", 14, MUTED, "middle", "600"))
    o.append(T(bx0 - 20, by0 + bd / 2 - 4, "LEFT", 14, ORANGE, "end", "700") + T(bx0 - 20, by0 + bd / 2 + 14, "side wall", 13, INK, "end"))
    o.append(T(bx0 + bw + 20, by0 + bd / 2 - 4, "RIGHT", 14, ORANGE, "start", "700") + T(bx0 + bw + 20, by0 + bd / 2 + 14, "side wall", 13, INK, "start"))
    dx = bx0 - 120
    o.append(f'<line x1="{dx}" y1="{by0}" x2="{dx}" y2="{by0 + bd}" stroke="{BLUE}"/><path d="M{dx - 5},{by0 + 8} l5,-8 l5,8 M{dx - 5},{by0 + bd - 8} l5,8 l5,-8" fill="none" stroke="{BLUE}"/>' + T(dx - 10, by0 + bd / 2 + 5, "30 mm", 13, BLUE, "end", "600"))
    yy = by0 + bd + th + 52
    o.append(f'<line x1="{bx0}" y1="{yy}" x2="{bx0 + bw}" y2="{yy}" stroke="{BLUE}"/><path d="M{bx0 + 8},{yy - 5} l-8,5 l8,5 M{bx0 + bw - 8},{yy - 5} l8,5 l-8,5" fill="none" stroke="{BLUE}"/>' + T(bx0 + bw / 2, yy + 20, "50 mm", 13, BLUE, "middle", "600"))
    o.append(T(W / 2, H - 16, "Orange = the walls to measure with calipers, in the upper half of each band.", 13, MUTED, "middle"))
    write("box-layout.svg", o)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    curve()
    workflow()
    layout()
    print("wrote 3 diagrams to", OUT)
