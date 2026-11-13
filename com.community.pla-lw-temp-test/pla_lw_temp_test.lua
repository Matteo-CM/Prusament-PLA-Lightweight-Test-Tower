-- PLA Lightweight (foaming PLA) temperature + flow test.
--
-- Source of the defaults (official Prusa material):
--  * Prusament PLA Lightweight Technical Datasheet v1.0 (Prusa Polymers, 09-2026):
--    nozzle 215-250 C, bed 60 +/-10 C, speed up to 100 mm/s, fan 30% (100% on
--    bridges). Its test specimens were printed with extrusion multiplier
--    1.0 @ 215 C and 0.38 @ 235 C, cooling disabled.
--  * Prusa blog, Prusament PLA Lightweight: default profile 230 C / EM 0.45,
--    bed 60 C, retraction off; foaming starts at 215 C and peaks at 235 C;
--    do not exceed 250 C.
--  * Prusa Knowledge Base "LW PLA": foaming depends on temperature AND speed;
--    EM range 1 - 0.35.
-- EM_CURVE below is piecewise-linear through those published points. Anything
-- between/after them is interpolation -- the measured wall decides.
--  * First test print (CORE One 0.4 HF, standard Prusament PLA converted by this
--    plugin, 205-250 C): 205 C was dense and unfoamed (too cold) and 245-250 C had
--    a degraded, blurred surface (too hot). Usable range found: 210-240 C. The
--    plugin therefore defaults to 210-240 C and flags anything outside it.
--    250 C is a HARD limit (Prusa: toxic fumes above it); the plugin refuses it.
--
-- Why this exists: Prusament PLA Lightweight foams in the hot end. Nozzle
-- temperature sets how much it expands (foaming starts ~215 C, peaks ~235 C), and
-- expansion changes the extruded line width, so the extrusion multiplier is only
-- right for ONE temperature. A normal temperature tower judged by eye is
-- misleading. This test prints a single-perimeter, open-top box, one band per
-- temperature, so the wall can be measured with calipers (Prusa's own method:
-- 1 perimeter, 0% infill, 0 top layers, target wall about 0.45-0.5 mm).
-- Every band also steps the flow with M221, and the label on the front tab shows
-- the temperature and the extrusion multiplier used for that band.
--
-- Constraints honoured (see README):
--  * top level holds declarations only -- the slicer scans this file in a bare
--    Lua engine without `api`;
--  * primitive Mesh:bounds() is stale in 3.0 alpha, so primitives use the
--    dimensions passed to their constructors;
--  * ConfigBox:set only supports int/number/percent/enum, so only those are set;
--  * every number written into G-code or a label goes through fmt_int(), because
--    Lua 5.4 prints floats as "235.0".

info = {
    id = "com.community.pla-lw-temp-test",
    type = "project.plugin",
    title = "PLA Lightweight Temp Test",
    menu = "Calibration/PLA Lightweight Temp Test",
    params = {
        {name = "wide_range",     label = "Wide test 205-250 C (shows too cold AND too hot)", type = "bool", default = false},
        {name = "custom_range",   label = "Custom range: use Min / Max / Steps below",   type = "bool",  default = false},
        {name = "min_temp",       label = "Custom Min [C]  (below 210 = too cold, minimum 190)", type = "int", default = 210},
        {name = "max_temp",       label = "Custom Max [C]  (above 240 = too hot, HARD LIMIT 250: toxic fumes)", type = "int", default = 240},
        {name = "steps",          label = "Custom Num Steps, 2-10  (Min = Max tests one temperature)", type = "int", default = 7},
        {name = "band_height",    label = "Band Height  [mm]",                     type = "float", default = 8},
        {name = "box_width",      label = "Box Front/Back Width  [mm]",            type = "float", default = 50},
        {name = "box_depth",      label = "Box Side Length  [mm]",                 type = "float", default = 30},
        {name = "perimeters",     label = "Perimeters (1 or 2)",                   type = "int",   default = 1},
        {name = "ref_em",         label = "Loaded Profile Extrusion Multiplier",   type = "float", default = 1.0},
        {name = "comp_flow",      label = "Convert Flow For Foaming (M221)",       type = "bool",  default = true},
        {name = "print_speed",    label = "Print Speed  [mm/s]  (datasheet: up to 100)", type = "int", default = 50},
        {name = "fan_percent",    label = "Fan Speed  [%]  (0 = keep profile)",    type = "int",   default = 30},
        {name = "retraction_off", label = "Try To Turn Retraction Off",            type = "bool",  default = true},
        {name = "hot_on_top",     label = "Hottest Band On Top",                   type = "bool",  default = true},
        {name = "labels",         label = "Engrave Labels And Band Grooves",       type = "bool",  default = true},
        {name = "lcd_messages",   label = "Show Band / Warning Messages On The Printer Display (M117)", type = "bool", default = true},
        {name = "clear_gcode",    label = "Clear Existing Custom G-code",          type = "bool",  default = true},
        {name = "no_slowdown",    label = "Disable Layer-time Slowdown (edits filament preset)", type = "bool", default = true}
    }
}

local MAX_SAFE_TEMP = 250 -- HARD limit. Prusa: never exceed 250 C with this filament (toxic fumes)
local MIN_TEMP = 190         -- hard lower limit; below this PLA does not extrude reliably
local TEMP_OK_MIN = 210      -- usable range found in the first test print: below = too cold, no foaming
local TEMP_OK_MAX = 240      -- above = too hot: degraded surface (and fumes risk grows towards 250)
local WIDE_MIN = 205         -- "wide" test shows both failure ends
local WIDE_MAX = 250

-- Published extrusion-multiplier points {temp C, EM}: datasheet 215 C -> 1.0 and
-- 235 C -> 0.38; blog 230 C -> 0.45.
local EM_CURVE = {{215, 1.00}, {230, 0.45}, {235, 0.38}}
local BOTTOM_LAYERS = 3 -- bottom_solid_layers set on the object below
local EM_FLOOR = 0.35 -- lowest EM Prusa's Knowledge Base mentions (reached at 250 C here)

local function em_at(t)
    local c = EM_CURVE
    if t <= c[1][1] then return c[1][2] end
    for i = 2, #c do
        if t <= c[i][1] then
            local f = (t - c[i - 1][1]) / (c[i][1] - c[i - 1][1])
            return c[i - 1][2] + f * (c[i][2] - c[i - 1][2])
        end
    end
    -- above the last published point: continue gently towards the floor
    local last = c[#c]
    return math.max(EM_FLOOR, last[2] - 0.002 * (t - last[1]))
end

local function clamp(v, lo, hi)
    return math.max(lo, math.min(hi, v))
end

-- Integer formatting that is identical on LuaJIT and Lua 5.4.
local function fmt_int(v)
    return string.format("%d", math.floor(v + 0.5))
end

local function num(v, default)
    if type(v) ~= "number" or v ~= v then return default end
    return v
end

--- "ok", "cold" or "hot" for a nozzle temperature.
local function zone_of(t)
    if t < TEMP_OK_MIN then return "cold" end
    if t > TEMP_OK_MAX then return "hot" end
    return "ok"
end

--- Which temperature range was asked for? Returns min, max, steps, mode.
local function resolve_range(opts)
    if opts.custom_range then
        return math.floor(num(opts.min_temp, TEMP_OK_MIN) + 0.5), math.floor(num(opts.max_temp, TEMP_OK_MAX) + 0.5),
               clamp(math.floor(num(opts.steps, 7) + 0.5), 2, 10), "custom"
    elseif opts.wide_range then
        return WIDE_MIN, WIDE_MAX, 10, "wide"
    end
    return TEMP_OK_MIN, TEMP_OK_MAX, 7, "recommended"
end

--- nil when the request is allowed, otherwise {text = "...", why = "..."}. Plugin errors are only
-- written to the log (never shown), so a refusal is made visible as a warning plate in the plater.
function validate_range(opts)
    local lo, hi = resolve_range(opts)
    if hi > MAX_SAFE_TEMP or lo > MAX_SAFE_TEMP then
        return {text = "NO - ABOVE 250 C = TOXIC FUMES", why = "requested " .. fmt_int(math.max(lo, hi)) .. " C; the hard limit is 250 C"}
    end
    if lo < MIN_TEMP or hi < MIN_TEMP then
        return {text = "NO - BELOW 190 C = TOO COLD", why = "requested " .. fmt_int(math.min(lo, hi)) .. " C; the minimum is 190 C"}
    end
    return nil
end

--- Pure planning step (also exercised by tests/). Returns a table:
--   bands = { {index, temp, flow, z_start, gcode_z}, ... } sorted by ascending z
--   total_height, layer_height, first_layer_height, error?
function plan_bands(opts, layer_height, first_layer_height)
    local lo, hi, steps = resolve_range(opts)
    -- Defence in depth: never plan outside the hard limits even if validate_range was skipped.
    local min_t = clamp(lo, MIN_TEMP, MAX_SAFE_TEMP)
    local max_t = clamp(hi, MIN_TEMP, MAX_SAFE_TEMP)
    if max_t < min_t then min_t, max_t = max_t, min_t end
    local band_h = clamp(num(opts.band_height, 8), 5, 25)
    local ref_em = clamp(num(opts.ref_em, 1.0), 0.2, 1.5)
    local fan_pct = clamp(math.floor(num(opts.fan_percent, 30) + 0.5), 0, 100)
    local comp = opts.comp_flow ~= false
    layer_height = num(layer_height, 0.2)
    first_layer_height = num(first_layer_height, layer_height)

    -- First layer (print_z) that starts at or above z. Layer k>=1 has
    -- print_z = first_layer_height + k * layer_height.
    local function snap(z)
        local k = math.max(1, math.ceil((z - first_layer_height) / layer_height - 1e-6) + 1)
        return math.floor((first_layer_height + k * layer_height) * 1000 + 0.5) / 1000
    end

    local bands = {}
    for i = 1, steps do
        local frac = (i - 1) / math.max(1, steps - 1)
        local t = min_t + (max_t - min_t) * frac
        if not opts.hot_on_top then t = max_t - (max_t - min_t) * frac end
        t = math.floor(t + 0.5)
        local em = comp and em_at(t) or ref_em
        local flow = clamp(em / ref_em * 100, 30, 250)
        flow = math.floor(flow + 0.5)

        local z_start = (i - 1) * band_h
        -- Band 1's M104 goes on layer 3, not 2: PrusaSlicer itself emits a temperature
        -- change on layer 2 when first-layer and normal temperature differ (e.g.
        -- CORE One PLA 230 -> 225 C), and the two must not race.
        local gz = snap(z_start)
        if i == 1 then gz = snap(first_layer_height + layer_height) end
        bands[i] = {index = i, temp = t, flow = flow, em = em, z_start = z_start, gcode_z = gz, zone = zone_of(t)}
    end
    local warnings = {}
    for _, b in ipairs(bands) do
        if b.zone == "cold" then
            warnings[#warnings + 1] = fmt_int(b.temp) .. " C is below " .. fmt_int(TEMP_OK_MIN) .. " C: too cold, the filament will not foam"
        elseif b.zone == "hot" then
            warnings[#warnings + 1] = fmt_int(b.temp) .. " C is above " .. fmt_int(TEMP_OK_MAX) .. " C: too hot, the surface degrades (never exceed 250 C)"
        end
    end
    table.sort(bands, function(a, b) return a.gcode_z < b.gcode_z end)

    -- G-code entries in ascending Z. Band 1's M104 goes on layer 3. If its flow is
    -- above 100 % that M221 is held back until the solid bottom layers plus ~2 mm
    -- are done (a still-hot nozzle must not print them at e.g. 222 %); a flow
    -- reduction is applied immediately.
    local byz, zs = {}, {}
    local function at(z)
        local key = string.format("%.3f", z)
        if not byz[key] then byz[key] = {z = z}; zs[#zs + 1] = key end
        return byz[key]
    end
    for i, band in ipairs(bands) do
        if i == 1 then
            if band.flow > 100 then
                -- Hold the flow increase until the solid bottom layers and ~2 mm
                -- are done, so a still-hot nozzle never prints them at e.g. 222 %.
                local flow_z = snap(first_layer_height + BOTTOM_LAYERS * layer_height + 2.0)
                if flow_z <= band.gcode_z then flow_z = snap(band.gcode_z + layer_height) end
                at(band.gcode_z).temp = band
                at(flow_z).flow = band
                band.flow_z = flow_z
            else -- a flow REDUCTION is safe immediately
                at(band.gcode_z).temp = band
                at(band.gcode_z).flow = band
                band.flow_z = band.gcode_z
            end
        else
            at(band.gcode_z).temp = band
            at(band.gcode_z).flow = band
            band.flow_z = band.gcode_z
        end
    end
    -- Fan: the standard PLA profile uses auto-cooling at 100 % (85 % on CORE One);
    -- LW-PLA wants 30 %. Preferred route: write the integer fan-speed settings
    -- and read them back (see execute); then no M106 is needed. Fallback only when
    -- that did not take: re-assert M106 on every layer from layer 3.
    local pwm = math.floor(fan_pct * 255 / 100 + 0.5)
    if opts._fan_preset_ok then pwm = 0 end -- the preset holds the fan; emit no M106
    if fan_pct > 0 and not opts._fan_preset_ok then
        local k = 2
        while true do
            local z = math.floor((first_layer_height + k * layer_height) * 1000 + 0.5) / 1000
            if z > band_h * steps + 1e-6 then break end
            at(z).fan = pwm
            k = k + 1
        end
    end
    table.sort(zs, function(a, b) return byz[a].z < byz[b].z end)
    local entries = {}
    for _, key in ipairs(zs) do entries[#entries + 1] = byz[key] end

    return {
        bands = bands,
        entries = entries,
        warnings = warnings,
        fan_pwm = pwm,
        perimeters = clamp(math.floor(num(opts.perimeters, 1) + 0.5), 1, 2),
        band_height = band_h,
        total_height = band_h * steps,
        layer_height = layer_height,
        first_layer_height = first_layer_height
    }
end

--- Engraved label (negative volume) on the front face (min Y) of the tab.
local function front_label(text, center_x, center_z, face_y, size)
    local depth = 0.9 -- deep and large: foamed bands blur shallow, small engraving
    local mesh = api.emboss_text {
        font = api.get_default_font(),
        text = text,
        depth = depth,
        line_height = size
    }
    local b = mesh:bounds()
    local w, h = b.max_x - b.min_x, b.max_y - b.min_y
    if w <= 0 or h <= 0 then -- stale/empty bounds: fall back to an estimate
        b = {min_x = 0, max_x = #text * size * 0.6, min_y = 0, max_y = size}
    end
    return {
        mesh = mesh,
        type = VolumeType.Negative,
        rotate = {x = 90},
        translate = {
            x = center_x - (b.min_x + b.max_x) * 0.5,
            y = face_y + depth,
            z = center_z - (b.min_y + b.max_y) * 0.5
        }
    }
end

--- A visible refusal: plugin errors are only logged, so show the reason as 3D text in the plater.
local function refusal_plate(reason)
    api.project:add_object {
        mesh = api.emboss_text {
            font = api.get_default_font(),
            text = reason.text,
            depth = 2,
            line_height = 8
        },
        object_params = {fill_density = "100%"}
    }
end

function execute(opts)
    -- Safety first: refuse before touching any preset or G-code.
    local refusal = validate_range(opts)
    if refusal then
        print("PLA-LW temp test REFUSED: " .. refusal.why)
        refusal_plate(refusal)
        return
    end

    local bed = api.project:current_bed()
    local print_settings = bed:print_presets()

    local layer_height = print_settings:value("layer_height")
    local first_layer = layer_height
    local okf, flv = pcall(function() return print_settings:value("first_layer_height") end)
    if okf and flv ~= nil then
        if type(flv) == "number" then
            first_layer = flv
        else -- FloatOrPercentage
            local oka, abs = pcall(function() return flv:get_abs_value(layer_height) end)
            if oka and type(abs) == "number" and abs > 0 then first_layer = abs end
        end
    end

    -- If the API can read the loaded filament's extrusion multiplier as a plain
    -- number, trust it over the parameter (labels and flow depend on it).
    local okE, emv = pcall(function() return bed:material_presets(0):value("extrusion_multiplier") end)
    if okE and type(emv) == "number" and emv > 0.1 and emv <= 1.5 then
        local o = {}
        for k, v in pairs(opts) do o[k] = v end
        o.ref_em = emv
        opts = o
    end

    local plan = plan_bands(opts, layer_height, first_layer) -- first pass: band 1 temperature
    local print_speed = clamp(math.floor(num(opts.print_speed, 50) + 0.5), 20, 100)
    local box_w = clamp(num(opts.box_width, 50), 20, 150)
    local box_d = clamp(num(opts.box_depth, 30), 20, 150)
    local total_height = plan.total_height

    -- Convert the loaded standard PLA profile (edits the ACTIVE filament/printer
    -- preset as unsaved changes -- do not save it over Prusament PLA). ConfigBox:set
    -- silently ignores keys it can't write, so every write is read back where
    -- possible; the results are collected in `report` and printed.
    local report = {}
    local function put(box, key, value)
        local ok_s = pcall(function() box:set(key, value) end)
        local ok_r, got = pcall(function() return box:value(key) end)
        local took = ok_s and ok_r and type(got) == "number" and math.abs(got - value) < 1e-6
        report[#report + 1] = key .. "=" .. tostring(value) .. (took and " ok" or " UNVERIFIED")
        return took
    end
    local function each_material(fn)
        for slot = 0, 15 do
            local ok_m, material = pcall(function() return bed:material_presets(slot) end)
            if not ok_m then break end
            pcall(fn, material)
        end
    end

    local fan_pct = clamp(math.floor(num(opts.fan_percent, 30) + 0.5), 0, 100)
    local fan_ok = false
    local band1_temp = plan.bands[1].temp
    each_material(function(m)
        -- Temperatures: first layer at 215 C (datasheet: EM 1.0 matches ~215 C, not the
        -- 225-230 C of the CORE One PLA profile); body at the first band's temperature.
        put(m, "first_layer_temperature", 215)
        put(m, "temperature", band1_temp)
        -- Cooling: datasheet fan 30 % (100 % on bridges); no layer-time slowdown.
        if opts.no_slowdown then
            put(m, "slowdown_below_layer_time", 0)
            put(m, "min_print_speed", 5)
        end
        if fan_pct > 0 then
            local a1 = put(m, "min_fan_speed", fan_pct)
            local a2 = put(m, "max_fan_speed", fan_pct)
            put(m, "bridge_fan_speed", 100)
            put(m, "full_fan_speed_layer", 0)
            put(m, "disable_fan_first_layers", 1)
            for i = 0, 3 do put(m, "overhang_fan_speed_" .. i, fan_pct) end -- CORE One dynamic fan
            fan_ok = a1 and a2
        end
        put(m, "bed_temperature", 60)
        put(m, "first_layer_bed_temperature", 60)
        -- As in Prusa's own Lightweight profiles: pressure advance off (M572 S0), no Z-hop, no travel Z-ramping.
        put(m, "pressure_advance_value", 0)
        put(m, "retract_lift", 0)
        put(m, "travel_ramping_lift", 0)
    end)
    if opts.retraction_off then
        each_material(function(m) put(m, "filament_retract_length", 0) end)
        pcall(function() put(bed:printer_presets(), "retract_length", 0) end)
    end
    if #report > 0 then print("PLA-LW conversion: " .. table.concat(report, ", ")) end
    if fan_ok then
        local o = {}
        for k, v in pairs(opts) do o[k] = v end
        o._fan_preset_ok = true
        plan = plan_bands(o, layer_height, first_layer)
    end


    if opts.clear_gcode then
        api.project:clear_layer_custom_steps(bed)
    end

    -- Geometry. Primitives start at (0,0,0); bounds() is not used on them.
    local TAB_W, TAB_T = math.min(40.0, box_w - 4), 3.5
    local other_volumes = {}

    -- Label tab on the front (-Y side). With perimeters=1 it would otherwise be
    -- hollow, so a modifier gives that region 4 perimeters and solid infill.
    local tab_x = (box_w - TAB_W) * 0.5
    table.insert(other_volumes, {
        mesh = api.make_cube(TAB_W, TAB_T, total_height),
        type = VolumeType.Solid,
        translate = {x = tab_x, y = -TAB_T, z = 0}
    })
    table.insert(other_volumes, {
        mesh = api.make_cube(TAB_W, TAB_T, total_height),
        type = VolumeType.Modifier,
        translate = {x = tab_x, y = -TAB_T, z = 0},
        params = {perimeters = 4, fill_density = "100%"}
    })

    for _, band in ipairs(plan.bands) do
        if opts.labels then
            local text = fmt_int(band.temp) .. "/" .. string.format("%.2f", band.em)
            if band.zone == "cold" then text = text .. " COLD" elseif band.zone == "hot" then text = text .. " HOT" end
            table.insert(other_volumes, front_label(
                text,
                box_w * 0.5,
                band.z_start + plan.band_height * 0.5,
                -TAB_T,
                math.min(4.6, plan.band_height * 0.55)
            ))
        end
    end
    -- Horizontal grooves on the tab at every band boundary, so the band is identifiable even when
    -- foaming blurs the text.
    if opts.labels then
        for i = 1, #plan.bands - 1 do
            table.insert(other_volumes, {
                mesh = api.make_cube(TAB_W, 0.8, 0.6),
                type = VolumeType.Negative,
                translate = {x = tab_x, y = -TAB_T, z = i * plan.band_height - 0.3}
            })
        end
    end

    -- G-code entries, appended in ascending Z. M104 does not wait: M109 would
    -- park the nozzle on the wall at the layer change and ooze a blob right on
    -- the surface being measured. Measure the upper half of each band.
    for _, e in ipairs(plan.entries) do
        local lines = {}
        if e.temp then
            local band = e.temp
            lines[#lines + 1] = "M104 S" .. fmt_int(band.temp) .. " ; PLA-LW test band " .. fmt_int(band.index)
            if band.zone ~= "ok" then
                lines[#lines + 1] = "; WARNING: " .. fmt_int(band.temp) .. " C is " ..
                    (band.zone == "cold" and "too cold (no foaming)" or "too hot (degrades the surface)")
            end
            if opts.lcd_messages ~= false then
                local msg
                if band.zone == "cold" then msg = "COLD " .. fmt_int(band.temp) .. "C no foam"
                elseif band.zone == "hot" then msg = "HOT " .. fmt_int(band.temp) .. "C degrades"
                else msg = "LW " .. fmt_int(band.index) .. "/" .. fmt_int(#plan.bands) .. " " .. fmt_int(band.temp) .. "C EM" .. string.format("%.2f", band.em) end
                lines[#lines + 1] = "M117 " .. msg
            end
        end
        if e.flow then
            lines[#lines + 1] = "M221 S" .. fmt_int(e.flow.flow) .. " ; flow " .. fmt_int(e.flow.flow) ..
                "% = EM " .. string.format("%.2f", e.flow.em)
        end
        if e.fan then
            lines[#lines + 1] = "M106 S" .. fmt_int(e.fan) .. " ; PLA-LW fan"
        end
        api.project:insert_layer_custom_gcode(bed, e.z, table.concat(lines, "\n"))
    end

    api.project:add_object {
        mesh = api.make_cube(box_w, box_d, total_height),
        translate = {x = 0, y = 0, z = 0},
        other_volumes = other_volumes,
        object_params = {
            perimeters = plan.perimeters,
            perimeter_speed = print_speed,
            external_perimeter_speed = print_speed,
            small_perimeter_speed = print_speed,
            gap_fill_speed = print_speed,
            infill_speed = print_speed,
            solid_infill_speed = print_speed,
            top_solid_infill_speed = print_speed,
            fill_density = "0%",
            top_solid_layers = 0,
            bottom_solid_layers = 3,
            seam_position = "rear"
        }
    }

    print(string.format("PLA-LW temp test: %d bands, %d-%d C, height %s mm",
        #plan.bands, plan.bands[1].temp, plan.bands[#plan.bands].temp, fmt_int(total_height)))
    for _, w in ipairs(plan.warnings) do print("PLA-LW WARNING: " .. w) end
end
