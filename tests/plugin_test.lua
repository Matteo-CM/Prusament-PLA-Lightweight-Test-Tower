-- LuaJIT test: loads the plugin the way the slicer does and checks the maths.
-- It uses a mock of `api`; it CANNOT prove the plugin works inside PrusaSlicer.
local BUNDLE = arg[1] or "com.community.pla-lw-temp-test"
local fails = 0
local function check(name, cond, extra)
    if not cond then fails = fails + 1 end
    print((cond and "ok   " or "FAIL ") .. name .. (extra and ("  [" .. tostring(extra) .. "]") or ""))
end
local function csv(t, f) local o = {} for _, v in ipairs(t) do o[#o + 1] = f(v) end return table.concat(o, ",") end

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
check("scan: params use verified types (int/float/bool) with defaults", allok)
check("scan: id matches manifest", env.info.id == (function()
    local f = io.open(BUNDLE .. "/manifest.json"); local t = f:read("*a"); f:close()
    return t:match('"id"%s*:%s*"([^"]+)"') end)())
check("defaults: 205-250 C, 10 steps, box 50 x 30, 1 perimeter, EM 1.0, fan 30",
    defaults.min_temp == 205 and defaults.max_temp == 250 and defaults.steps == 10 and defaults.box_width == 50
    and defaults.box_depth == 30 and defaults.perimeters == 1 and defaults.ref_em == 1.0 and defaults.fan_percent == 30 and defaults.print_speed == 50)

-- 2. Planning
local plan = env.plan_bands(defaults, 0.2, 0.2)
check("plan: temps 205..250 in 5 C steps", csv(plan.bands, function(b) return b.temp end) == "205,210,215,220,225,230,235,240,245,250")
check("plan: flow% vs standard PLA EM 1.0 (Prusa points 1.0@215, .45@230, .38@235, floor .35)",
    csv(plan.bands, function(b) return b.flow end) == "100,100,100,82,63,45,38,37,36,35", csv(plan.bands, function(b) return b.flow end))
check("plan: EM hits published points", (function()
    local m = {} for _, b in ipairs(plan.bands) do m[b.temp] = string.format("%.2f", b.em) end
    return m[215] == "1.00" and m[230] == "0.45" and m[235] == "0.38" and m[250] == "0.35" end)())
check("plan: total height 80 mm", math.abs(plan.total_height - 80) < 1e-9)
local asc, grid = true, true
for i = 2, #plan.entries do if plan.entries[i].z <= plan.entries[i - 1].z then asc = false end end
for _, e in ipairs(plan.entries) do local k = (e.z - 0.2) / 0.2; if math.abs(k - math.floor(k + 0.5)) > 1e-6 then grid = false end end
check("plan: entries strictly ascending in Z", asc)
check("plan: every Z on the real layer grid", grid)
local p2 = env.plan_bands(defaults, 0.25, 0.3)
local grid2 = true
for _, e in ipairs(p2.entries) do local k = (e.z - 0.3) / 0.25; if math.abs(k - math.floor(k + 0.5)) > 1e-6 then grid2 = false end end
check("plan: grid holds for flh 0.3 / lh 0.25", grid2)
check("plan: band 1 M104 on layer 3 or later (never races the slicer's layer-2 change)", plan.bands[1].gcode_z >= 0.6 - 1e-9, plan.bands[1].gcode_z)
local pe0 = env.plan_bands({ref_em = 0.45, hot_on_top = true}, 0.2, 0.2)
local b1flow, b1temp
for _, e in ipairs(pe0.entries) do if e.flow == pe0.bands[1] then b1flow = e.z end; if e.temp == pe0.bands[1] then b1temp = e.z end end
check("plan: band 1 flow > 100% (222) is held back past bottom layers + 2 mm", pe0.bands[1].flow == 222 and b1flow >= 0.2 + 3 * 0.2 + 2 - 1e-6 and b1temp < b1flow, tostring(b1temp) .. " -> " .. tostring(b1flow))
local rev = {} for k, v in pairs(defaults) do rev[k] = v end; rev.hot_on_top = false
local pr = env.plan_bands(rev, 0.2, 0.2)
local same = false for _, e in ipairs(pr.entries) do if e.flow == pr.bands[1] and e.temp == pr.bands[1] then same = true end end
check("plan: band 1 flow < 100% (250 C, 35%) is applied immediately, not held", pr.bands[1].temp == 250 and pr.bands[1].flow == 35 and same)
local firstfan, fans, nofan_early = nil, 0, true -- fallback path (preset fan not confirmed)
for _, e in ipairs(plan.entries) do if e.fan then fans = fans + 1; firstfan = firstfan or e.z; if e.z < 0.6 - 1e-6 then nofan_early = false end end end
check("plan: fallback M106 on every layer from layer 3", fans == 398 and math.abs(firstfan - 0.6) < 1e-6 and nofan_early, fans .. " @ " .. tostring(firstfan))
local pok = {} for k, v in pairs(defaults) do pok[k] = v end; pok._fan_preset_ok = true
local pokp = env.plan_bands(pok, 0.2, 0.2); local fok = false
for _, e in ipairs(pokp.entries) do if e.fan then fok = true end end
check("plan: preset fan confirmed -> no M106 entries at all", not fok and pokp.fan_pwm == 0)
check("plan: fallback fan 30% -> PWM 77", plan.fan_pwm == 77, plan.fan_pwm)
local nf = {} for k, v in pairs(defaults) do nf[k] = v end; nf.fan_percent = 0
local pnf = env.plan_bands(nf, 0.2, 0.2)
local anyfan = false; for _, e in ipairs(pnf.entries) do if e.fan then anyfan = true end end
check("plan: fan_percent 0 leaves the profile fan alone", not anyfan and pnf.fan_pwm == 0)
local nc = {} for k, v in pairs(defaults) do nc[k] = v end; nc.comp_flow = false
local pn = env.plan_bands(nc, 0.2, 0.2); local all100 = true
for _, b in ipairs(pn.bands) do if b.flow ~= 100 then all100 = false end end
check("plan: comp_flow=false -> 100% everywhere", all100)
local pe = env.plan_bands({ref_em = 0.45}, 0.2, 0.2)
check("plan: ref_em 0.45 (e.g. Prusa LW profile) -> 230 C band at 100%", (function()
    for _, b in ipairs(pe.bands) do if b.temp == 230 then return b.flow == 100 end end end)())

-- clamps
local hot = {min_temp = 100, max_temp = 400, steps = 99, band_height = 1, perimeters = 7}
local p3 = env.plan_bands(hot, 0.2, 0.2)
local mn, mx, minf = 1e9, 0, 1e9
for _, b in ipairs(p3.bands) do mn = math.min(mn, b.temp); mx = math.max(mx, b.temp); minf = math.min(minf, b.flow) end
check("clamp: temps within 205..250", mn >= 205 and mx <= 250, mn .. ".." .. mx)
check("clamp: steps <= 10, band height >= 5, perimeters in 1..2", #p3.bands <= 10 and p3.band_height >= 5 and p3.perimeters == 2)
check("clamp: flow >= 30", minf >= 30, minf)
check("clamp: perimeters 0 -> 1", env.plan_bands({perimeters = 0}, 0.2, 0.2).perimeters == 1)
local p4 = env.plan_bands({min_temp = 250, max_temp = 205, steps = 3, hot_on_top = false}, 0.2, 0.2)
check("clamp: swapped min/max handled", p4.bands[1].temp >= 205 and p4.bands[1].temp <= 250)
check("clamp: NaN / wrong types do not crash", #env.plan_bands({min_temp = 0/0, steps = "x"}, nil, nil).bands >= 2)

-- 3. execute() against a mock API
local calls
-- mode "store": ConfigBox:set stores and value() returns it; mode "ignore": set is a silent no-op
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
        emboss_text = function(o) calls.text[#calls.text + 1] = o.text; return mesh("text") end,
        get_default_font = function() return "font" end,
        project = {current_bed = function() return bed end,
            clear_layer_custom_steps = function() calls.cleared = calls.cleared + 1 end,
            insert_layer_custom_gcode = function(_, b, z, g) calls.gcode[#calls.gcode + 1] = {z = z, g = g} end,
            add_object = function(_, o) calls.objects[#calls.objects + 1] = o end},
    }
end
newmock(nil); env.execute(defaults)
local fmtok, lines_ok = true, true
for _, c in ipairs(calls.gcode) do
    if c.g:match("M109") or c.g:match("S%d+%.%d") then fmtok = false end
    for line in (c.g .. "\n"):gmatch("([^\n]*)\n") do
        if not (line:match("^M104 S%d%d%d ; ") or line:match("^M221 S%d+ ; ") or line:match("^M106 S%d+ ; ")) then lines_ok = false end
    end
end
check("exec: only integer-formatted M104 / M221 / M106 lines, no M109", fmtok and lines_ok)
local zs_ok = true
for i = 2, #calls.gcode do if calls.gcode[i].z <= calls.gcode[i - 1].z then zs_ok = false end end
check("exec: inserts strictly ascending in Z", zs_ok)
check("exec: first entry is band 1 on layer 3 (M104 S205 + M221 S100)", calls.gcode[1].z >= 0.6 - 1e-9 and calls.gcode[1].g:match("^M104 S205") and calls.gcode[1].g:match("M221 S100"), calls.gcode[1].z .. " " .. (calls.gcode[1].g:gsub("\n", " | ")))
local anyM106 = false; for _, c in ipairs(calls.gcode) do if c.g:match("M106") then anyM106 = true end end
check("exec: fan read back OK -> no M106 G-code (auto-cooling holds 30% from the preset)", not anyM106)
check("exec: 10 bands, 10 inserts when fan comes from the preset", #calls.gcode == 10, #calls.gcode)
local blk; for _, c in ipairs(calls.gcode) do if c.g:match("M104 S220") then blk = c end end
check("exec: later band changes M104 + M221 together (220 C -> S82)", blk and blk.g:match("M221 S82"), blk and (blk.g:gsub("\n", " | ")))
check("exec: cleared old custom G-code", calls.cleared == 1)
check("exec: box 50 x 30 x 80 main mesh", calls.cubes[#calls.cubes][1] == 50 and calls.cubes[#calls.cubes][2] == 30 and calls.cubes[#calls.cubes][3] == 80, table.concat(calls.cubes[#calls.cubes], "x"))
local o = calls.objects[1]
check("exec: 1 perimeter, 0% infill, open top", o.object_params.perimeters == 1 and o.object_params.fill_density == "0%" and o.object_params.top_solid_layers == 0)
local mods, negs, sol = 0, 0, 0
for _, v in ipairs(o.other_volumes) do
    if v.type == "Modifier" then mods = mods + 1; check("exec: modifier thickens tab", v.params.perimeters >= 4) end
    if v.type == "Negative" then negs = negs + 1 end
    if v.type == "Solid" then sol = sol + 1 end
end
check("exec: tab + modifier + 10 labels", sol == 1 and mods == 1 and negs == 10, sol .. "/" .. mods .. "/" .. negs)
check("exec: labels 'temp / EM'", calls.text[1] == "205 / 1.00" and calls.text[10] == "250 / 0.35", calls.text[1] .. " .. " .. calls.text[10])
local st = calls.stored
check("exec: fan preset: min/max 30, bridge 100, overhang 30, no first-layer fan", st.min_fan_speed == 30 and st.max_fan_speed == 30 and st.bridge_fan_speed == 100 and st.overhang_fan_speed_0 == 30 and st.overhang_fan_speed_3 == 30 and st.disable_fan_first_layers == 1)
check("exec: temperatures: first layer 215, body = band 1 temp (205)", st.first_layer_temperature == 215 and st.temperature == 205)
check("exec: slowdown off, bed 60, retraction 0", st.slowdown_below_layer_time == 0 and st.bed_temperature == 60 and st.filament_retract_length == 0 and calls.pstored.retract_length == 0)
local op = o.object_params
check("exec: speeds applied to the test object (50 mm/s everywhere)", op.perimeter_speed == 50 and op.external_perimeter_speed == 50 and op.small_perimeter_speed == 50 and op.infill_speed == 50 and op.solid_infill_speed == 50 and op.gap_fill_speed == 50)
check("exec: label tab centred on a 50 mm front", (function() local t; for _, v in ipairs(o.other_volumes) do if v.type == "Solid" then t = v end end return math.abs(t.translate.x - 10) < 1e-9 end)())

-- 2 perimeters
newmock(nil); local two = {} for k, v in pairs(defaults) do two[k] = v end; two.perimeters = 2
env.execute(two)
check("exec: perimeters=2 reaches the object", calls.objects[1].object_params.perimeters == 2)

-- print speed param + clamp
newmock(nil); local fast = {} for k, v in pairs(defaults) do fast[k] = v end; fast.print_speed = 999
env.execute(fast)
check("exec: print speed clamped to 100", calls.objects[1].object_params.perimeter_speed == 100)

-- readback FAILS (setter ignores everything) -> per-layer M106 fallback
newmock(nil, "ignore"); env.execute(defaults)
local m106 = 0; for _, c in ipairs(calls.gcode) do if c.g:match("M106 S77") then m106 = m106 + 1 end end
check("exec: setter ignored -> fallback emits M106 S77 on 398 layers", m106 == 398, m106)
local z_ok = true; for i = 2, #calls.gcode do if calls.gcode[i].z <= calls.gcode[i - 1].z then z_ok = false end end
check("exec: fallback inserts still strictly ascending", z_ok)

-- options off
newmock(nil); local off = {} for k, v in pairs(defaults) do off[k] = v end
off.labels, off.clear_gcode, off.no_slowdown, off.fan_percent, off.retraction_off = false, false, false, 0, false
env.execute(off)
local anyfan2 = false; for _, c in ipairs(calls.gcode) do if c.g:match("M106") then anyfan2 = true end end
check("exec: options off -> no clear, no fan edits/M106, no slowdown/retraction edits, no labels",
    calls.cleared == 0 and not anyfan2 and calls.stored.min_fan_speed == nil and calls.stored.slowdown_below_layer_time == nil
    and calls.stored.filament_retract_length == nil and #calls.objects[1].other_volumes == 2)

-- loaded EM readable
newmock(0.45); env.execute(defaults)
local g = calls.gcode; local found
for _, c in ipairs(g) do if c.g:match("M104 S230") then found = c end end
check("exec: readable loaded EM 0.45 overrides the parameter -> 230 C band at 100%", found and found.g:match("M221 S100"), found and (found.g:gsub("\n", " | ")))

print(fails == 0 and "\nALL PASSED" or ("\n" .. fails .. " FAILED"))
os.exit(fails == 0 and 0 or 1)
