"""Shared constants for the LW-PLA tools, read from the plugin source so they cannot drift.

If the plugin file is not next to this repo layout, the built-in fallbacks (identical values,
checked by tests/analyze_test.py) are used.
"""
import os
import re

_PLUGIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "com.community.pla-lw-temp-test", "pla_lw_temp_test.lua")

# fallbacks (kept equal to the plugin by a test)
CURVE = [(215, 1.00), (230, 0.45), (235, 0.38)]
EM_FLOOR = 0.35
MAX_SAFE_TEMP = 250   # hard limit: toxic fumes above it
MIN_TEMP = 190        # hard lower limit
TEMP_OK_MIN = 210     # usable range from the first test print (below: no foaming)
TEMP_OK_MAX = 240     # above: surface degrades
WIDE_MIN, WIDE_MAX = 205, 250

try:
    _src = open(_PLUGIN, encoding="utf-8").read()
    CURVE = [(int(a), float(b)) for a, b in re.findall(r"\{(\d+),\s*([\d.]+)\}", re.search(r"local EM_CURVE = (\{.*?\})\n", _src).group(1))]
    EM_FLOOR = float(re.search(r"local EM_FLOOR = ([\d.]+)", _src).group(1))
    MAX_SAFE_TEMP = int(re.search(r"local MAX_SAFE_TEMP = (\d+)", _src).group(1))
    MIN_TEMP = int(re.search(r"local MIN_TEMP = (\d+)", _src).group(1))
    TEMP_OK_MIN = int(re.search(r"local TEMP_OK_MIN = (\d+)", _src).group(1))
    TEMP_OK_MAX = int(re.search(r"local TEMP_OK_MAX = (\d+)", _src).group(1))
    WIDE_MIN = int(re.search(r"local WIDE_MIN = (\d+)", _src).group(1))
    WIDE_MAX = int(re.search(r"local WIDE_MAX = (\d+)", _src).group(1))
except (OSError, AttributeError):  # plugin source missing or reshaped: keep the fallbacks
    pass


def em_at(t):
    """Extrusion multiplier the tower prints at temperature t (same maths as the plugin)."""
    if t <= CURVE[0][0]:
        return CURVE[0][1]
    for i in range(1, len(CURVE)):
        if t <= CURVE[i][0]:
            f = (t - CURVE[i - 1][0]) / (CURVE[i][0] - CURVE[i - 1][0])
            return CURVE[i - 1][1] + f * (CURVE[i][1] - CURVE[i - 1][1])
    return max(EM_FLOOR, CURVE[-1][1] - 0.002 * (t - CURVE[-1][0]))


def zone_of(t):
    """'cold', 'ok' or 'hot'."""
    if t < TEMP_OK_MIN:
        return "cold"
    if t > TEMP_OK_MAX:
        return "hot"
    return "ok"
