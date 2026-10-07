-- Runs the exporter outside the game with stubbed engine globals.
-- usage: luajit harness.lua <scripts_dir> <configs_dir> <out_dir> <scenario>
-- Writes every distinct snapshot to <out_dir>/fast.jsonl and slow.jsonl and
-- the game log to <out_dir>/xray.log.

local scripts_dir, configs_dir, out_dir, scenario = arg[1], arg[2], arg[3], arg[4] or "normal"
assert(scripts_dir and configs_dir and out_dir, "usage: harness.lua <scripts_dir> <configs_dir> <out_dir> <scenario>")

local function path(...)
	return table.concat({ ... }, "/")
end

local log_file = assert(io.open(path(out_dir, "xray.log"), "w"))

-- X-Ray loads gamedata/scripts/<name>.script on first access to the global <name>.
setmetatable(_G, {
	__index = function(t, name)
		local file = io.open(path(scripts_dir, name .. ".script"), "rb")
		if not file then
			return nil
		end
		local src = file:read("*a")
		file:close()
		local env = setmetatable({}, { __index = _G })
		rawset(t, name, env)
		local chunk = assert(loadstring(src, "@" .. name .. ".script"))
		setfenv(chunk, env)
		chunk()
		return env
	end,
})

-- Engine stubs ---------------------------------------------------------------

local clock_ms = 0
local callbacks = {}

function printf(fmt, ...)
	log_file:write(string.format(fmt, ...), "\n")
end

function time_global()
	return clock_ms
end

function RegisterScriptCallback(name, fn)
	callbacks[name] = callbacks[name] or {}
	table.insert(callbacks[name], fn)
end

local function fire(name)
	for _, fn in ipairs(callbacks[name] or {}) do
		fn()
	end
end

local CP1251_CORDON = "\202\238\240\228\238\237" -- "Кордон"
local CP1251_NAME = "\204\229\247\229\237\251\233" -- "Меченый"

local world = {
	level = "l01_escape",
	translations = { l01_escape = CP1251_CORDON },
	pos = { x = -118.4, y = 11.9, z = -257.1 },
	dir = { x = 0.6, y = 0, z = 0.8 },
	health = 0.9,
	radiation = 0.05,
	alive = true,
	money = 12500,
	name = CP1251_NAME,
	day = 3,
	hour = 21,
	minute = 47,
}

local aliases = {
	["$app_data_root$"] = path(out_dir, "appdata") .. "/",
	["$game_saves$"] = path(out_dir, "saves") .. "/",
}

local fs = {}
function fs:update_path(alias, rest)
	local base = aliases[alias]
	if not base then
		error("unknown alias " .. alias)
	end
	return base .. rest
end

function getFS()
	return fs
end

local actor = {}
function actor:position()
	return { x = world.pos.x, y = world.pos.y, z = world.pos.z }
end
function actor:alive()
	return world.alive
end
function actor:money()
	return world.money
end
function actor:character_name()
	return world.name
end
function actor:id()
	return 0
end
setmetatable(actor, {
	__index = function(_, key)
		if key == "health" then
			return world.health
		elseif key == "radiation" then
			return world.radiation
		end
	end,
})

db = { actor = nil }

level = {
	name = function()
		return world.level
	end,
	get_time_days = function()
		return world.day
	end,
	get_time_hours = function()
		return world.hour
	end,
	get_time_minutes = function()
		return world.minute
	end,
}

game = {
	translate_string = function(id)
		return world.translations[id] or id
	end,
}

function device()
	return { cam_dir = world.dir }
end

local ini_mt = {}
ini_mt.__index = ini_mt
function ini_mt:section_exist(sec)
	return self.data[sec] ~= nil
end
function ini_mt:line_exist(sec, key)
	return self.data[sec] ~= nil and self.data[sec][key] ~= nil
end
function ini_mt:r_string(sec, key)
	return self.data[sec][key]
end

function ini_file(name)
	local data, section = {}, nil
	local file = io.open(path(configs_dir, name), "rb")
	if file then
		for line in file:lines() do
			line = line:gsub(";.*$", ""):gsub("\r", "")
			local sec = line:match("^%s*%[([^%]]+)%]")
			if sec then
				section = sec
				data[sec] = data[sec] or {}
			elseif section then
				local k, v = line:match("^%s*([%w_]+)%s*=%s*(.-)%s*$")
				if k then
					data[section][k] = v
				end
			end
		end
		file:close()
	end
	return setmetatable({ data = data }, ini_mt)
end

-- Scenarios ------------------------------------------------------------------

local snapshot_dir = aliases["$app_data_root$"]

if scenario == "broken_api" then
	actor.money = function()
		error("money is not exported in this build")
	end
	actor.character_name = nil
	device = function()
		error("device() unavailable")
	end
	world.radiation = nil
elseif scenario == "appdata_readonly" then
	aliases["$app_data_root$"] = path(out_dir, "missing", "appdata") .. "/"
	snapshot_dir = aliases["$game_saves$"]
elseif scenario == "config_dir" then
	snapshot_dir = path(out_dir, "custom") .. "/"
elseif scenario == "utf8_names" then
	world.translations.l01_escape = "Кордон"
	world.name = "Стрелок"
elseif scenario == "bad_time" then
	world.day = 0
elseif scenario ~= "normal" then
	error("unknown scenario " .. scenario)
end

-- Run ------------------------------------------------------------------------

local seen = { fast = nil, slow = nil }
local sinks = {
	fast = assert(io.open(path(out_dir, "fast.jsonl"), "w")),
	slow = assert(io.open(path(out_dir, "slow.jsonl"), "w")),
}

local function capture()
	for kind, sink in pairs(sinks) do
		local f = io.open(snapshot_dir .. "pda_" .. kind .. ".json", "rb")
		if f then
			local data = f:read("*a")
			f:close()
			if data ~= seen[kind] then
				seen[kind] = data
				sink:write(data, "\n")
			end
		end
	end
end

local FRAME_MS = 16

local function run_frames(ms, step)
	local stop = clock_ms + ms
	while clock_ms < stop do
		clock_ms = clock_ms + FRAME_MS
		if step then
			step()
		end
		fire("actor_on_update")
		capture()
	end
end

clock_ms = 5000
xpda_export.on_game_start()
db.actor = actor
fire("actor_on_first_update")
capture()

run_frames(3000, function()
	world.pos.x = world.pos.x + 0.07
	world.pos.z = world.pos.z + 0.05
	world.health = math.max(0, world.health - 0.001)
end)

world.level = "l02_garbage"
run_frames(500)

world.health = 0
world.alive = false
run_frames(1000)

fire("actor_on_net_destroy")
capture()

for _, sink in pairs(sinks) do
	sink:close()
end
log_file:close()
