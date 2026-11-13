-- LuaJIT test: loads the plugin the way the slicer does and checks the maths.
-- It uses a mock of `api`; it CANNOT prove the plugin works inside PrusaSlicer.
local BUNDLE = arg[1] or "com.community.pla-lw-temp-test"
local fails = 0
local function check(name, cond, extra)
    if not cond then fails = fails + 1 end
    print((cond and "ok   " or "FAIL ") .. name .. (extra and ("  [" .. tostring(extra) .. "]") or ""))
end
local function csv(t, f) local o = {} for _, v in ipairs(t) do o[#o + 1] = f(v) end return table.concat(o, ",") end
local function copy(t, over) local o = {} for k, v in pairs(t) do o[k] = v end for k, v in pairs(over or {}) do o[k] = v end return o end

-- 1. Scan phase: bare environment (no api / VolumeType)
local env = setmetatable({}, {__index = _G})
local chunk = assert(loadfile(BUNDLE .. "/pla_lw_temp_test.lua"))
setfenv(chunk, env); chunk()
check("scan: info + execute defined", type(env.info) == "table" and type(env.execute) == "function")
check("scan: type project.plugin", env.info.type == "project.plugin")
local okTypes, allok, defaults = {float = true, int = true, bool = true}, true, {}
for _, p in ipairs(env.info.params) do
    if not okTypes[p.type] or not p.name or not p.label or p.default == nil then allok = false end
    defaults[p.name] = p.default
end
check("scan: only verified param types (int/float/bool), all with defaults", allok)
check("scan: id matches manifest", env.info.id == (function()
    local f = io.open(BUNDLE .. "/manifest.json"); local t = f:read("*a"); f:close()
    return t:match('"id"%s*:%s*"([^"]+)"') end)())
check("defaults: recommended range (not wide, not custom), 7 custom steps, box 50 x 30, 1 perimeter, EM 1.0, fan 30, speed 50",
    defaults.wide_range == false and defaults.custom_range == false and defaults.min_temp == 210 and defaults.max_temp == 240
    and defaults.steps == 7 and defaults.box_width == 50 and defaults.box_depth == 30 and defaults.perimeters == 1
    and defaults.ref_em == 1.0 and defaults.fan_percent == 30 and defaults.print_speed == 50 and defaults.lcd_messages == true)
local labels_ok = false
for _, p in ipairs(env.info.params) do
    if p.name == "max_temp" and p.label:match("250") and p.label:lower():match("fumes") then labels_ok = true end
end
check("dialog label for Max warns about the 250 C fumes limit", labels_ok)

-- 2. Range modes and zones
local plan = env.plan_bands(defaults, 0.2, 0.2)
check("recommended: 210..240 in 5 C steps (7 bands)", csv(plan.bands, function(b) return b.temp end) == "210,215,220,225,230,235,240")
check("recommended: no band is flagged and there are no warnings", #plan.warnings == 0 and (function()
    for _, b in ipairs(plan.bands) do if b.zone ~= "ok" then return false end end return true end)())
check("recommended: flow% vs standard PLA EM 1.0", csv(plan.bands, function(b) return b.flow end) == "100,100,82,63,45,38,37", csv(plan.bands, function(b) return b.flow end))
check("recommended: total height 56 mm", math.abs(plan.total_height - 56) < 1e-9)
local pw = env.plan_bands(copy(defaults, {wide_range = true}), 0.2, 0.2)
check("wide: 205..250 (10 bands)", csv(pw.bands, function(b) return b.temp end) == "205,210,215,220,225,230,235,240,245,250")
check("wide: flow follows Prusa points, floor 35% at 250", csv(pw.bands, function(b) return b.flow end) == "100,100,100,82,63,45,38,37,36,35")
local zs = csv(pw.bands, function(b) return b.zone end)
check("wide: 205 cold, 210-240 ok, 245/250 hot", zs == "cold,ok,ok,ok,ok,ok,ok,ok,hot,hot", zs)
check("wide: three warnings (205, 245, 250), the hot ones mention 250 C", #pw.warnings == 3 and pw.warnings[1]:match("too cold") and pw.warnings[2]:match("too hot") and pw.warnings[3]:match("250"))
local pc = env.plan_bands(copy(defaults, {custom_range = true, min_temp = 220, max_temp = 235, steps = 4}), 0.2, 0.2)
check("custom: uses Min/Max/Steps (220..235 in 5 C steps)", csv(pc.bands, function(b) return b.temp end) == "220,225,230,235")
local po = env.plan_bands(copy(defaults, {custom_range = true, min_temp = 230, max_temp = 230, steps = 2}), 0.2, 0.2)
check("custom: Min = Max tests one temperature (2 identical bands, no division by zero)", #po.bands == 2 and po.bands[1].temp == 230 and po.bands[2].temp == 230)
check("custom ignored unless enabled", #env.plan_bands(copy(defaults, {min_temp = 190, max_temp = 250}), 0.2, 0.2).bands == 7)
check("zone boundaries: 240 ok, 241 hot, 210 ok, 209 cold", (function()
    local function z(t) return env.plan_bands(copy(defaults, {custom_range = true, min_temp = t, max_temp = t, steps = 2}), 0.2, 0.2).bands[1].zone end
    return z(240) == "ok" and z(241) == "hot" and z(210) == "ok" and z(209) == "cold" end)())

-- hard limits / refusal
local function refused(over) return env.validate_range(copy(defaults, over)) end
check("hard limit: custom max 251 is refused", refused({custom_range = true, max_temp = 251}) ~= nil)
check("hard limit: custom max 250 is allowed", refused({custom_range = true, max_temp = 250}) == nil)
check("hard limit: custom min 300 / max 300 is refused", refused({custom_range = true, min_temp = 300, max_temp = 300}) ~= nil)
check("hard limit: custom min 189 is refused, 190 allowed", refused({custom_range = true, min_temp = 189, max_temp = 220}) ~= nil and refused({custom_range = true, min_temp = 190, max_temp = 220}) == nil)
check("refusal text names the 250 C fumes limit", (refused({custom_range = true, max_temp = 400}).text:match("250") and refused({custom_range = true, max_temp = 400}).text:match("FUMES")) ~= nil)
check("defaults and wide mode are never refused", env.validate_range(defaults) == nil and refused({wide_range = true}) == nil)
local pclamp = env.plan_bands(copy(defaults, {custom_range = true, min_temp = 100, max_temp = 900, steps = 99}), 0.2, 0.2)
local mn, mx = 1e9, 0
for _, b in ipairs(pclamp.bands) do mn = math.min(mn, b.temp); mx = math.max(mx, b.temp) end
check("defence in depth: even if validation is skipped the plan never leaves 190..250 C", mn >= 190 and mx <= 250 and #pclamp.bands <= 10, mn .. ".." .. mx)

-- 3. G-code planning
local asc, grid = true, true
for i = 2, #plan.entries do if plan.entries[i].z <= plan.entries[i - 1].z then asc = false end end
for _, e in ipairs(plan.entries) do local k = (e.z - 0.2) / 0.2; if math.abs(k - math.floor(k + 0.5)) > 1e-6 then grid = false end end
check("plan: entries strictly ascending in Z, all on the layer grid", asc and grid)
local p2 = env.plan_bands(defaults, 0.25, 0.3); local grid2 = true
for _, e in ipairs(p2.entries) do local k = (e.z - 0.3) / 0.25; if math.abs(k - math.floor(k + 0.5)) > 1e-6 then grid2 = false end end
check("plan: grid holds for first layer 0.3 / layer 0.25", grid2)
check("plan: band 1 temperature on layer 3 or later (never races the slicer's layer-2 change)", plan.bands[1].gcode_z >= 0.6 - 1e-9, plan.bands[1].gcode_z)
local pe0 = env.plan_bands({ref_em = 0.45, hot_on_top = true, wide_range = true}, 0.2, 0.2)
local b1flow, b1temp
for _, e in ipairs(pe0.entries) do if e.flow == pe0.bands[1] then b1flow = e.z end; if e.temp == pe0.bands[1] then b1temp = e.z end end
check("plan: band 1 flow > 100% (222) is held back past the bottom layers + 2 mm", pe0.bands[1].flow == 222 and b1flow >= 0.2 + 3 * 0.2 + 2 - 1e-6 and b1temp < b1flow)
local pr = env.plan_bands(copy(defaults, {hot_on_top = false, wide_range = true}), 0.2, 0.2)
local same = false for _, e in ipairs(pr.entries) do if e.flow == pr.bands[1] and e.temp == pr.bands[1] then same = true end end
check("plan: band 1 flow < 100% (250 C, 35%) is applied immediately", pr.bands[1].temp == 250 and pr.bands[1].flow == 35 and same)
local fans, firstfan = 0, nil
for _, e in ipairs(plan.entries) do if e.fan then fans = fans + 1; firstfan = firstfan or e.z end end
check("plan: fallback M106 on every layer from layer 3 (56 mm / 0.2 mm)", fans == 278 and math.abs(firstfan - 0.6) < 1e-6, fans)
local ok = copy(defaults, {_fan_preset_ok = true}); local anyf = false
for _, e in ipairs(env.plan_bands(ok, 0.2, 0.2).entries) do if e.fan then anyf = true end end
check("plan: preset fan confirmed -> no M106 entries", not anyf)
check("plan: comp_flow=false -> 100% everywhere", (function() for _, b in ipairs(env.plan_bands(copy(defaults, {comp_flow = false}), 0.2, 0.2).bands) do if b.flow ~= 100 then return false end end return true end)())
check("plan: perimeters clamp 1..2", env.plan_bands(copy(defaults, {perimeters = 7}), 0.2, 0.2).perimeters == 2 and env.plan_bands(copy(defaults, {perimeters = 0}), 0.2, 0.2).perimeters == 1)
check("plan: NaN / wrong types do not crash", #env.plan_bands({min_temp = 0/0, steps = "x", custom_range = true}, nil, nil).bands >= 2)

-- 4. execute() against a mock API
local calls
local function newmock(material_em, mode)
    mode = mode or "store"
    calls = {gcode = {}, objects = {}, cleared = 0, stored = {}, pstored = {}, text = {}, cubes = {}}
    local function mesh(tag) return {tag = tag, bounds = function() return {min_x = 0, max_x = 0, min_y = 0, max_y = 0, min_z = 0, max_z = 0} end} end
    local fl = {is_percentage = false, get_abs_value = function() return 0.2 end}
    local print_p = {value = function(_, k) if k == "layer_height" then return 0.2 end return fl end, set = function() end}
    local mat = {value = function(_, k)
                    if calls.stored[k] ~= nil then return calls.stored[k] end
                    if k == "extrusion_multiplier" and material_em then return material_em end
                    error("opaque") end,
                 set = function(_, k, v) if mode == "store" then calls.stored[k] = v end end}
    local printer = {set = function(_, k, v) if mode == "store" then calls.pstored[k] = v end end,
                     value = function(_, k) if calls.pstored[k] ~= nil then return calls.pstored[k] end error("opaque") end}
    local bed = {print_presets = function() return print_p end, printer_presets = function() return printer end,
                 material_presets = function(_, slot) if slot > 0 then error("no slot") end return mat end}
    env.VolumeType = {Solid = "Solid", Negative = "Negative", Modifier = "Modifier"}
    env.api = {
        make_cube = function(w, d, h) local m = mesh("cube"); calls.cubes[#calls.cubes + 1] = {w, d, h}; return m end,
        emboss_text = function(o) calls.text[#calls.text + 1] = o.text; calls.textopts = o; return mesh("text") end,
        get_default_font = function() return "font" end,
        project = {current_bed = function() return bed end,
            clear_layer_custom_steps = function() calls.cleared = calls.cleared + 1 end,
            insert_layer_custom_gcode = function(_, b, z, g) calls.gcode[#calls.gcode + 1] = {z = z, g = g} end,
            add_object = function(_, o) calls.objects[#calls.objects + 1] = o end},
    }
end

newmock(nil); env.execute(defaults)
local fmtok = true
for _, c in ipairs(calls.gcode) do
    if c.g:match("M109") or c.g:match("S%d+%.%d") then fmtok = false end
    for line in (c.g .. "\n"):gmatch("([^\n]*)\n") do
        if not (line:match("^M104 S%d%d%d ; ") or line:match("^M221 S%d+ ; ") or line:match("^M106 S%d+ ; ") or line:match("^M117 [%w/ .]+$") or line:match("^; WARNING")) then fmtok = false end
    end
end
check("exec: only integer-formatted M104 / M221 / M117 / M106 lines, no M109", fmtok)
local z_ok = true; for i = 2, #calls.gcode do if calls.gcode[i].z <= calls.gcode[i - 1].z then z_ok = false end end
check("exec: inserts strictly ascending in Z", z_ok)
local anyM106 = false; for _, c in ipairs(calls.gcode) do if c.g:match("M106") then anyM106 = true end end
check("exec: fan read back OK -> no M106 G-code", not anyM106)
check("exec: 7 inserts (one per band) when the fan comes from the preset", #calls.gcode == 7, #calls.gcode)
check("exec: band 1 = M104 S210 + M117 'LW 1/7 210C EM1.00' + M221 S100 on layer 3", calls.gcode[1].z >= 0.6 - 1e-9 and calls.gcode[1].g:match("M104 S210") and calls.gcode[1].g:match("M117 LW 1/7 210C EM1.00") and calls.gcode[1].g:match("M221 S100"), (calls.gcode[1].g:gsub("\n", " | ")))
local noWarn = true for _, c in ipairs(calls.gcode) do if c.g:match("WARNING") or c.g:match("COLD") or c.g:match("HOT") then noWarn = false end end
check("exec: recommended range -> no WARNING / COLD / HOT anywhere in the G-code", noWarn)
check("exec: cleared old custom G-code; box 50 x 30 x 56", calls.cleared == 1 and calls.cubes[#calls.cubes][1] == 50 and calls.cubes[#calls.cubes][2] == 30 and calls.cubes[#calls.cubes][3] == 56)
local o = calls.objects[1]
check("exec: exactly one object, 1 perimeter, 0% infill, open top", #calls.objects == 1 and o.object_params.perimeters == 1 and o.object_params.fill_density == "0%" and o.object_params.top_solid_layers == 0)
local mods, negs, sol, tabw = 0, 0, 0, nil
for _, v in ipairs(o.other_volumes) do
    if v.type == "Modifier" then mods = mods + 1; check("exec: modifier thickens tab", v.params.perimeters >= 4) end
    if v.type == "Negative" then negs = negs + 1 end
    if v.type == "Solid" then sol = sol + 1 end
end
check("exec: tab + modifier + 7 labels + 6 band grooves", sol == 1 and mods == 1 and negs == 13, sol .. "/" .. mods .. "/" .. negs)
check("exec: labels 'temp/EM' without spaces, deeper and larger than before", calls.text[1] == "210/1.00" and calls.text[7] == "240/0.37" and calls.textopts.depth >= 0.8 and calls.textopts.line_height >= 4, table.concat(calls.text, " | "))
local st = calls.stored
check("exec: fan preset 30/30, bridge 100, overhang 30, first layers off", st.min_fan_speed == 30 and st.max_fan_speed == 30 and st.bridge_fan_speed == 100 and st.overhang_fan_speed_0 == 30 and st.disable_fan_first_layers == 1)
check("exec: temperatures: first layer 215, body = band 1 temp (210)", st.first_layer_temperature == 215 and st.temperature == 210)
check("exec: Prusa's other LW values: pressure advance 0, Z-hop 0, travel ramping 0", st.pressure_advance_value == 0 and st.retract_lift == 0 and st.travel_ramping_lift == 0)
check("exec: slowdown off, bed 60, retraction 0", st.slowdown_below_layer_time == 0 and st.bed_temperature == 60 and st.filament_retract_length == 0 and calls.pstored.retract_length == 0)
local op = o.object_params
check("exec: 50 mm/s everywhere on the test object", op.perimeter_speed == 50 and op.external_perimeter_speed == 50 and op.small_perimeter_speed == 50 and op.infill_speed == 50 and op.solid_infill_speed == 50)

-- wide mode: warnings reach labels, G-code and the printer display
newmock(nil); env.execute(copy(defaults, {wide_range = true}))
local lab = table.concat(calls.text, " | ")
check("wide exec: cold/hot bands are tagged on the labels", lab:match("205/1.00 COLD") and lab:match("245/0.36 HOT") and lab:match("250/0.35 HOT") and not lab:match("230/0.45 %a"), lab)
local g = {} for _, c in ipairs(calls.gcode) do g[#g + 1] = c.g end; local gall = table.concat(g, "\n")
check("wide exec: G-code carries ; WARNING comments and M117 COLD/HOT alerts", gall:match("; WARNING: 205 C is too cold") and gall:match("; WARNING: 250 C is too hot") and gall:match("M117 COLD 205C no foam") and gall:match("M117 HOT 245C degrades"))
check("wide exec: no G-code line ever sets a temperature above 250", (function() for t in gall:gmatch("M104 S(%d+)") do if tonumber(t) > 250 then return false end end return true end)())
check("wide exec: 9 groove cuts for 10 bands", (function() local n = 0 for _, v in ipairs(calls.objects[1].other_volumes) do if v.type == "Negative" then n = n + 1 end end return n == 10 + 9 end)())

-- hard refusal: nothing changes except a visible warning plate
newmock(nil); env.execute(copy(defaults, {custom_range = true, max_temp = 260}))
check("refusal: no tower, no G-code, no preset edits, nothing cleared", #calls.gcode == 0 and calls.cleared == 0 and next(calls.stored) == nil and next(calls.pstored) == nil)
check("refusal: a single warning plate object is added with a 250 C / FUMES message", #calls.objects == 1 and calls.text[1]:match("250") and calls.text[1]:match("FUMES") and calls.objects[1].other_volumes == nil, calls.text[1])
newmock(nil); env.execute(copy(defaults, {custom_range = true, min_temp = 150}))
check("refusal: too cold (150 C) also shows a plate and changes nothing", #calls.objects == 1 and calls.text[1]:match("190") and #calls.gcode == 0 and next(calls.stored) == nil)

-- display messages can be switched off
newmock(nil); env.execute(copy(defaults, {lcd_messages = false, wide_range = true}))
local anyM117 = false; for _, c in ipairs(calls.gcode) do if c.g:match("M117") then anyM117 = true end end
check("lcd_messages=false -> no M117 (the ; WARNING comments stay)", not anyM117 and calls.gcode[1].g:match("; WARNING"))

-- print speed clamp, 2 perimeters
newmock(nil); env.execute(copy(defaults, {print_speed = 999, perimeters = 2}))
check("exec: print speed clamped to 100; perimeters=2 reaches the object", calls.objects[1].object_params.perimeter_speed == 100 and calls.objects[1].object_params.perimeters == 2)

-- readback FAILS (setter ignores everything) -> per-layer M106 fallback
newmock(nil, "ignore"); env.execute(defaults)
local m106 = 0; for _, c in ipairs(calls.gcode) do if c.g:match("M106 S77") then m106 = m106 + 1 end end
check("exec: setter ignored -> fallback emits M106 S77 on 278 layers", m106 == 278, m106)
local z2 = true; for i = 2, #calls.gcode do if calls.gcode[i].z <= calls.gcode[i - 1].z then z2 = false end end
check("exec: fallback inserts still strictly ascending", z2)

-- options off
newmock(nil); local off = copy(defaults, {labels = false, clear_gcode = false, no_slowdown = false, fan_percent = 0, retraction_off = false, lcd_messages = false})
env.execute(off)
local anyfan2 = false; for _, c in ipairs(calls.gcode) do if c.g:match("M106") then anyfan2 = true end end
check("exec: options off -> no clear, no fan/slowdown/retraction edits, no labels or grooves",
    calls.cleared == 0 and not anyfan2 and calls.stored.min_fan_speed == nil and calls.stored.slowdown_below_layer_time == nil
    and calls.stored.filament_retract_length == nil and #calls.objects[1].other_volumes == 2)

-- loaded EM readable
newmock(0.45); env.execute(defaults)
local found; for _, c in ipairs(calls.gcode) do if c.g:match("M104 S230") then found = c end end
check("exec: readable loaded EM 0.45 overrides the parameter -> 230 C band at 100%", found and found.g:match("M221 S100"))

print(fails == 0 and "\nALL PASSED" or ("\n" .. fails .. " FAILED"))
os.exit(fails == 0 and 0 or 1)
