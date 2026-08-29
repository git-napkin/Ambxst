#!/usr/bin/env bash
# ambxst+ CLI - It was needed, so here it is. lol

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Use environment variables if set by flake, otherwise fall back to PATH
QS_BIN="${AMBXST_PLUS_QS:-${AMBXST_QS:-qs}}"
NIXGL_BIN="${AMBXST_PLUS_NIXGL:-}"

if [ -n "${QML2_IMPORT_PATH:-}" ] && [ -z "${QML_IMPORT_PATH:-}" ]; then
	export QML_IMPORT_PATH="$QML2_IMPORT_PATH"
fi

# Ensure config files exist - copy from preset if missing
ensure_config_files() {
	local old_config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/ambxst"
	local config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+/config"
	local preset_dir="${SCRIPT_DIR}/assets/presets/ambxst+ Default"

	# First-boot migration: copy old ~/.config/ambxst to ~/.config/ambxst+
	if [ -d "$old_config_dir" ] && [ ! -f "${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+/.migrated" ]; then
		echo "Migrating config from $old_config_dir to ${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+..."
		mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+"
		cp -r "$old_config_dir/." "${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+/"
		# Migrate old flat config to new config/ subdirectory if needed
		mkdir -p "$config_dir"
		for f in theme bar workspaces overview notch compositor performance desktop lockscreen dock ai system; do
			if [ -f "${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+/${f}.json" ] && [ ! -f "${config_dir}/${f}.json" ]; then
				mv "${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+/${f}.json" "${config_dir}/${f}.json"
			fi
		done
		touch "${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+/.migrated"
		echo "Migration complete."
	fi

	# Create config directory if it doesn't exist
	mkdir -p "$config_dir"

	# Migrate wallpaper config from old cache path to config path
	local new_wallpaper_config="${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+/wallpapers.json"
	local old_wallpaper_config="${HOME}/.cache/ambxst/wallpapers.json"
	if [ -f "$old_wallpaper_config" ] && [ ! -f "$new_wallpaper_config" ]; then
		cp "$old_wallpaper_config" "$new_wallpaper_config"
		echo "Migrated wallpaper config from $old_wallpaper_config to $new_wallpaper_config"
	fi
	old_wallpaper_config="${HOME}/.cache/ambxst+/wallpapers.json"
	if [ -f "$old_wallpaper_config" ] && [ ! -f "$new_wallpaper_config" ]; then
		cp "$old_wallpaper_config" "$new_wallpaper_config"
		echo "Migrated wallpaper config from $old_wallpaper_config to $new_wallpaper_config"
	fi

	# Copy preset files if they don't exist (cp -n = no-clobber)
	for file in theme bar workspaces overview notch compositor performance desktop lockscreen dock ai; do
		cp -n "${preset_dir}/${file}.json" "${config_dir}/${file}.json" 2>/dev/null || true
	done
}

show_help() {
	cat <<EOF
Ambxst[+] CLI - Desktop Environment Control

Usage: ambxst+ [COMMAND]

Commands:
    (none)                            Launch Ambxst[+]
    refresh                           Refresh local/dev profile (for developers)
    lock                              Activate lockscreen
    run <command>                     Send command to running shell (launcher, volume-up, etc.)
    mic-mute                          Toggle microphone mute (with OSD feedback)
    brightness <percent> [monitor]    Set brightness (0-100)
    brightness +/-<delta> [monitor]   Adjust brightness relatively
    brightness -s [monitor]           Save current brightness
    brightness -r [monitor]           Restore saved brightness
    brightness -l                     List monitors and their brightness
    wallpaper <file>                  Set wallpaper on the running shell
        -scheme <name>                Matugen scheme for this wallpaper
        -oled                         OLED mode for this wallpaper only
        -tint                         Tint for this wallpaper only
        -monitor <id|name>            Apply to one monitor
    preset -l                         List presets
    preset "Name"                     Load a preset
    help                              Show this help message
    version, -v, --version            Show Ambxst[+] version
    goodbye                           Uninstall Ambxst[+] :(
    install <target>                    Install compositor config (hyprland)
    remove <target>                    Remove compositor config (hyprland)

Examples:
    ambxst+ brightness 75              Set all monitors to 75%
    ambxst+ brightness 50 HDMI-A-1     Set HDMI-A-1 to 50%
    ambxst+ brightness +10             Increase brightness by 10%
    ambxst+ brightness -5 HDMI-A-1     Decrease HDMI-A-1 brightness by 5%
    ambxst+ brightness 10 -s           Save current, then set all to 10%
    ambxst+ brightness -s HDMI-A-1     Save current brightness of HDMI-A-1
    ambxst+ brightness -r              Restore saved brightness
    ambxst+ wallpaper ~/Pictures/wall.png -scheme scheme-tonal-spot
    ambxst+ preset -l
    ambxst+ preset "ambxst+ Default"

EOF
}

AMBXST_PLUS_HYPR_CONF_SOURCE="source = ~/.local/share/ambxst+/hyprland.conf"
AMBXST_PLUS_HYPR_LUA_SOURCE='loadfile(os.getenv("HOME") .. "/.local/share/ambxst+/hyprland.lua")()'
AMBXST_PLUS_HYPR_CONF_BLOCK=$(
	cat <<'EOF'
# Ambxst[+]
source = ~/.local/share/ambxst+/hyprland.conf

# OVERRIDES
# Down here you can write or source anything that you want to override from Ambxst[+]'s settings.
EOF
)
AMBXST_PLUS_HYPR_LUA_BLOCK=$(
	cat <<'EOF'
-- Ambxst[+]
loadfile(os.getenv("HOME") .. "/.local/share/ambxst+/hyprland.lua")()

-- OVERRIDES
-- Down here you can write or source anything that you want to override from Ambxst[+]'s settings.
EOF
)

append_ambxst_plus_hyprland_block() {
	local conf="$1"
	local source="$2"
	local block="$3"

	if [ -f "$conf" ] && grep -qF "$source" "$conf"; then
		echo "Ambxst[+] Hyprland block already present in $conf"
		return 0
	fi

	if [ -f "$conf" ] && [ -s "$conf" ]; then
		printf "\n%s\n" "$block" >>"$conf"
	else
		printf "%s\n" "$block" >"$conf"
	fi

	echo "Added Ambxst[+] Hyprland block to $conf"
}

ensure_ambxst_plus_hyprland_source() {
	# The block we append sources ~/.local/share/ambxst+/hyprland.conf (or
	# .lua). Hyprland errors on a missing source file, so create it (with a
	# user-overrides header) if it does not exist yet.
	local file="$1"
	local header="$2"

	if [ ! -f "$file" ]; then
		mkdir -p "$(dirname "$file")"
		printf "%s\n" "$header" >"$file"
		echo "Created $file"
	else
		echo "$file already exists"
	fi
}

remove_ambxst_plus_hyprland_block() {
	local conf="$1"
	local source="$2"

	if [ ! -f "$conf" ]; then
		echo "$conf does not exist"
		return 0
	fi

	# Refuse symlinked configs: `mv` would replace the symlink with a regular
	# file, silently breaking dotfile-managed setups (chezmoi, git, ...).
	if [ -L "$conf" ]; then
		echo "Refusing to modify symlinked config: $conf -> $(readlink "$conf")"
		echo "Remove the Ambxst[+] block manually from the target file instead."
		return 1
	fi

	awk -v source="$source" '
		function is_remove(line) {
			return line == source \
				|| line == "# Ambxst[+]" \
				|| line == "-- Ambxst[+]" \
				|| line == "# OVERRIDES" \
				|| line == "-- OVERRIDES" \
				|| line == "# Down here you can write or source anything that you want to override from Ambxst[+]'\''s settings." \
				|| line == "-- Down here you can write or source anything that you want to override from Ambxst[+]'\''s settings."
		}
		{
			lines[NR] = $0
		}
		END {
			for (i = 1; i <= NR; i++) {
				line = lines[i]
				nextline = (i < NR) ? lines[i + 1] : ""
				if (is_remove(line)) {
					continue
				}
				if (line == "" && (is_remove(lines[i - 1]) || is_remove(nextline))) {
					continue
				}
				print line
			}
		}
	' "$conf" >"${conf}.tmp" && chmod --reference="$conf" "${conf}.tmp" && mv "${conf}.tmp" "$conf"

	echo "Removed Ambxst[+] Hyprland block from $conf"
}

find_ambxst_plus_pid() {
	pgrep -n -f '(^|/)(qs|quickshell) .*shell\.qml' 2>/dev/null || true
}

find_ambxst_plus_pid_cached() {
	# Optimized PID lookup: check cache file first, then fall back to pgrep
	local pid_file="${XDG_RUNTIME_DIR:-/tmp}/ambxst+.pid"
	local pid=""

	# Check if cache file exists and process is alive
	if [ -f "$pid_file" ] && [ -O "$pid_file" ]; then
		pid=$(<"$pid_file" 2>/dev/null)
		# Verify the PID is numeric, still alive, and really is our shell
		# (cmdline contains shell.qml) before trusting it
		if [ -n "$pid" ] && [[ "$pid" =~ ^[0-9]+$ ]] \
			&& [ -r "/proc/$pid/cmdline" ] \
			&& tr '\0' ' ' <"/proc/$pid/cmdline" | grep -q "shell.qml"; then
			echo "$pid"
			return 0
		fi
		# PID is stale or untrusted, remove cache file
		rm -f "$pid_file"
	fi

	# Fallback: use expensive pgrep search
	pid=$(find_ambxst_plus_pid)
	echo "$pid"
}

is_nix_store_symlink() {
	local path="$1"
	[ -L "$path" ] || return 1
	local target
	target=$(readlink "$path")
	case "$target" in
	/nix/store/*) return 0 ;;
	esac
	return 1
}

print_home_manager_hyprland_guide() {
	cat <<'EOF'
Ambxst[+]: this Hyprland config is managed by home-manager (symlink into /nix/store).
Refusing to write through it. Import Ambxst[+] from home.nix instead:

  xdg.configFile."hypr/hyprland.lua".text = ''
    loadfile(os.getenv("HOME") .. "/.local/share/ambxst+/hyprland.lua")()
  '';
EOF
}

send_json_ipc() {
	local json="$1"
	local pipe="${XDG_RUNTIME_DIR:-/tmp}/ambxst+_ipc.pipe"

	if [ -p "$pipe" ]; then
		printf '%s\n' "$json" >"$pipe" &
		return 0
	fi

	local pid
	pid=$(find_ambxst_plus_pid_cached)
	if [ -z "$pid" ]; then
		echo "Error: Ambxst[+] is not running" >&2
		return 1
	fi

	qs ipc --pid "$pid" call 'ambxst+' run "$json" 2>/dev/null || {
		echo "Error: Could not send command to Ambxst[+]" >&2
		return 1
	}
}

save_current_brightness() {
	local save_file="$1"
	local monitor="${2:-}"
	local list_script="${SCRIPT_DIR}/scripts/brightness_list.sh"

	if [ -z "$monitor" ]; then
		bash "$list_script" >"${save_file}.tmp" 2>/dev/null || {
			echo "Warning: Could not query current brightness"
			return 0
		}
		if [ -f "${save_file}.tmp" ]; then
			while IFS=: read -r name bright _; do
				if [ -n "$name" ] && [ -n "$bright" ]; then
					echo "${name}:${bright}"
				fi
			done <"${save_file}.tmp" >"$save_file"
			rm -f "${save_file}.tmp"
			echo "Saved current brightness for all monitors"
		fi
	else
		local current_line current
		current_line=$(bash "$list_script" 2>/dev/null | grep "^${monitor}:")
		if [ -z "$current_line" ]; then
			echo "Error: Monitor $monitor not found"
			return 1
		fi
		current=$(echo "$current_line" | cut -d: -f2)
		if [ -f "$save_file" ]; then
			grep -v "^${monitor}:" "$save_file" >"${save_file}.tmp" 2>/dev/null || true
			echo "${monitor}:${current}" >>"${save_file}.tmp"
			mv "${save_file}.tmp" "$save_file"
		else
			echo "${monitor}:${current}" >"$save_file"
		fi
		echo "Saved current brightness for $monitor (${current}%)"
	fi
}

restart_ambxst_plus() {
	# Kill axctl processes first (they survive parent death when forked/detached)
	pkill -f "axctl.*daemon" 2>/dev/null || true
	pkill -f "axctl subscribe" 2>/dev/null || true

	PID=$(find_ambxst_plus_pid_cached)
	if [ -n "$PID" ]; then
		echo "Stopping Ambxst[+] (PID $PID)..."
		kill "$PID"
		# Wait for process to exit
		while kill -0 "$PID" 2>/dev/null; do
			sleep 0.1
		done
	fi
	echo "Starting Ambxst[+]..."
	# Relaunch the script in background
	nohup "$0" >/dev/null 2>&1 &
}

case "${1:-}" in
refresh)
	echo "Refreshing Ambxst[+] profile..."
	# The profile element is named after the derivation (ambxst+-<version>),
	# so match any ambxst* variant rather than a stale exact name
	exec nix profile upgrade 'ambxst.*' --refresh --impure
	;;
run)
	shift
	CMD="$*"
	PIPE="${XDG_RUNTIME_DIR:-/tmp}/ambxst+_ipc.pipe"

	if [ -z "$CMD" ]; then
		echo "Error: No command specified for run"
		exit 1
	fi

	# Fast path: Write directly to pipe if it exists (Zero latency)
	if [ -p "$PIPE" ]; then
		echo "$CMD" >"$PIPE" &
		exit 0
	fi

	# Fallback path: Use QS IPC with cached PID lookup
	PID=$(find_ambxst_plus_pid_cached)
	if [ -z "$PID" ]; then
		echo "Error: Ambxst[+] is not running"
		exit 1
	fi

	qs ipc --pid "$PID" call 'ambxst+' run "$CMD" 2>/dev/null || {
		echo "Error: Could not run command '$CMD'"
		exit 1
	}
	;;
lock)
	exec "${BASH_SOURCE[0]}" run lockscreen
	;;
mic-mute)
	# Convenience alias for `ambxst+ run mic-mute`
	shift
	exec "${BASH_SOURCE[0]}" run mic-mute "$@"
	;;
reload)
	restart_ambxst_plus
	;;
quit)
	# Kill axctl processes first
	pkill -f "axctl.*daemon" 2>/dev/null || true
	pkill -f "axctl subscribe" 2>/dev/null || true

	PID=$(find_ambxst_plus_pid_cached)
	if [ -n "$PID" ]; then
		echo "Stopping Ambxst[+] (PID $PID)..."
		kill "$PID"
	else
		echo "Ambxst[+] is not running"
	fi
	;;
screen)
	SUB="${2:-}"
	AXCTL_STATE=""
	case "$SUB" in
	off) AXCTL_STATE="0" ;;
	on) AXCTL_STATE="1" ;;
	*)
		echo "Usage: ambxst+ screen [on|off]"
		exit 1
		;;
	esac

	if ! command -v axctl &>/dev/null; then
		notify-send "Screen ${SUB}" "axctl is required to control the screen"
		exit 1
	fi

	MONITORS_JSON=$(axctl monitor list 2>/dev/null) || {
		notify-send "Screen ${SUB}" "Failed to list monitors via axctl"
		exit 1
	}

	MONITOR_IDS=$(echo "$MONITORS_JSON" | jq -r '.[].id' 2>/dev/null) || {
		notify-send "Screen ${SUB}" "Failed to parse monitor list"
		exit 1
	}

	if [ -z "$MONITOR_IDS" ]; then
		notify-send "Screen ${SUB}" "No monitors detected"
		exit 1
	fi

	for MON_ID in $MONITOR_IDS; do
		if ! axctl monitor set-dpms "$MON_ID" "$AXCTL_STATE" >/dev/null 2>&1; then
			notify-send "Screen ${SUB}" "Failed to set DPMS on monitor $MON_ID"
			exit 1
		fi
	done
	;;
suspend)
	if command -v systemctl &>/dev/null; then
		systemctl suspend
	elif command -v loginctl &>/dev/null; then
		loginctl suspend
	else
		# Fallback to D-Bus
		dbus-send --system --print-reply --dest=org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager.Suspend boolean:true
	fi
	;;
brightness)
	BRIGHTNESS_SAVE_FILE="${XDG_RUNTIME_DIR:-/tmp}/ambxst+_brightness_saved.txt"

	# Parse arguments
	ARG2="${2:-}"
	ARG3="${3:-}"
	ARG4="${4:-}"

	# Handle list flag (no IPC needed)
	if [ "$ARG2" = "-l" ] || [ "$ARG2" = "--list" ]; then
		echo "Monitors:"
		if command -v hyprctl &>/dev/null; then
			hyprctl monitors -j 2>/dev/null | jq -r '.[] | "  \(.name)"' || {
				echo "Error: Could not list monitors"
				exit 1
			}
		else
			echo "Error: hyprctl not found"
			exit 1
		fi
		exit 0
	fi

	# Handle save-only flag (no IPC needed)
	if [ "$ARG2" = "-s" ] || [ "$ARG2" = "--save" ]; then
		save_current_brightness "$BRIGHTNESS_SAVE_FILE" "${ARG3:-}" || exit 1
		exit 0
	fi

	# Everything below talks to the running shell over IPC
	PID=$(find_ambxst_plus_pid_cached)
	if [ -z "$PID" ]; then
		echo "Error: Ambxst[+] is not running"
		exit 1
	fi

	# Handle restore flag
	if [ "$ARG2" = "-r" ] || [ "$ARG2" = "--restore" ]; then
		if [ ! -f "$BRIGHTNESS_SAVE_FILE" ] || [ ! -O "$BRIGHTNESS_SAVE_FILE" ]; then
			echo "Error: No saved brightness found. Use -s to save first."
			exit 1
		fi

		MONITOR="${ARG3:-}"

		if [ -z "$MONITOR" ]; then
			# Restore all monitors
			while IFS=: read -r name value; do
				if [ -n "$name" ] && [ -n "$value" ]; then
					NORMALIZED=$(awk "BEGIN {printf \"%.2f\", $value / 100}")
					qs ipc --pid "$PID" call brightness set "$NORMALIZED" "$name" 2>/dev/null || {
						echo "Warning: Could not restore brightness for $name"
					}
				fi
			done <"$BRIGHTNESS_SAVE_FILE"
			echo "Restored brightness for all monitors"
		else
			# Restore specific monitor
			VALUE=$(grep "^${MONITOR}:" "$BRIGHTNESS_SAVE_FILE" | cut -d: -f2)
			if [ -z "$VALUE" ]; then
				echo "Error: No saved brightness for monitor $MONITOR"
				exit 1
			fi
			NORMALIZED=$(awk "BEGIN {printf \"%.2f\", $VALUE / 100}")
			qs ipc --pid "$PID" call brightness set "$NORMALIZED" "$MONITOR" 2>/dev/null || {
				echo "Error: Could not restore brightness for $MONITOR"
				exit 1
			}
			echo "Restored brightness for $MONITOR to ${VALUE}%"
		fi
		exit 0
	fi

	# Parse value and monitor/flags
	VALUE=""
	MONITOR=""
	SAVE_FLAG=false
	RELATIVE_MODE=false
	RELATIVE_DELTA=0

	if [[ "$ARG2" =~ ^[0-9]+$ ]]; then
		VALUE="$ARG2"
		if [ "$ARG3" = "-s" ] || [ "$ARG3" = "--save" ]; then
			SAVE_FLAG=true
		elif [ -n "$ARG3" ] && [ "$ARG3" != "-s" ] && [ "$ARG3" != "--save" ]; then
			MONITOR="$ARG3"
			if [ "$ARG4" = "-s" ] || [ "$ARG4" = "--save" ]; then
				SAVE_FLAG=true
			fi
		fi
	elif [[ "$ARG2" =~ ^[+-][0-9]+$ ]]; then
		# Relative mode: +10 or -5
		RELATIVE_MODE=true
		RELATIVE_DELTA="$ARG2"
		if [ -n "$ARG3" ] && [ "$ARG3" != "-s" ] && [ "$ARG3" != "--save" ]; then
			MONITOR="$ARG3"
			if [ "$ARG4" = "-s" ] || [ "$ARG4" = "--save" ]; then
				SAVE_FLAG=true
			fi
		elif [ "$ARG3" = "-s" ] || [ "$ARG3" = "--save" ]; then
			SAVE_FLAG=true
		fi
	else
		echo "Error: Invalid brightness value. Must be 0-100 or +/-delta."
		echo "Run 'ambxst+ help' for usage information"
		exit 1
	fi

	# Handle relative mode - use IPC adjust function directly
	if [ "$RELATIVE_MODE" = true ]; then
		# Convert delta to 0-1 range
		NORMALIZED_DELTA=$(awk "BEGIN {printf \"%.2f\", $RELATIVE_DELTA / 100}")

		if [ -z "$MONITOR" ]; then
			qs ipc --pid "$PID" call brightness adjust "$NORMALIZED_DELTA" "" 2>/dev/null || {
				echo "Error: Could not adjust brightness"
				exit 1
			}
			echo "Adjusted brightness by ${RELATIVE_DELTA}% for all monitors"
		else
			qs ipc --pid "$PID" call brightness adjust "$NORMALIZED_DELTA" "$MONITOR" 2>/dev/null || {
				echo "Error: Could not adjust brightness for $MONITOR"
				exit 1
			}
			echo "Adjusted brightness by ${RELATIVE_DELTA}% for $MONITOR"
		fi
		exit 0
	fi

	# Validate brightness range
	if [ "$VALUE" -lt 0 ] || [ "$VALUE" -gt 100 ]; then
		echo "Error: Brightness must be between 0 and 100"
		exit 1
	fi

	# Save current brightness if requested
	if [ "$SAVE_FLAG" = true ]; then
		save_current_brightness "$BRIGHTNESS_SAVE_FILE" "$MONITOR" || exit 1
	fi

	# Set brightness
	NORMALIZED=$(awk "BEGIN {printf \"%.2f\", $VALUE / 100}")

	if [ -z "$MONITOR" ]; then
		# Set all monitors
		qs ipc --pid "$PID" call brightness set "$NORMALIZED" "" 2>/dev/null || {
			echo "Error: Could not set brightness"
			exit 1
		}
		echo "Set brightness to ${VALUE}% for all monitors"
	else
		# Set specific monitor
		qs ipc --pid "$PID" call brightness set "$NORMALIZED" "$MONITOR" 2>/dev/null || {
			echo "Error: Could not set brightness for $MONITOR"
			exit 1
		}
		echo "Set brightness to ${VALUE}% for $MONITOR"
	fi
	;;
wallpaper)
	shift
	WP_FILE=""
	WP_SCHEME=""
	WP_OLED=""
	WP_TINT=""
	WP_MONITOR=""
	while [ $# -gt 0 ]; do
		case "$1" in
		-scheme)
			WP_SCHEME="${2:-}"
			if [ -z "$WP_SCHEME" ]; then
				echo "Error: -scheme needs a name" >&2
				exit 2
			fi
			shift 2
			;;
		-oled)
			WP_OLED="true"
			shift
			;;
		-tint)
			WP_TINT="true"
			shift
			;;
		-monitor)
			WP_MONITOR="${2:-}"
			if [ -z "$WP_MONITOR" ]; then
				echo "Error: -monitor needs a name" >&2
				exit 2
			fi
			shift 2
			;;
		-*)
			echo "Error: unknown wallpaper flag '$1'" >&2
			exit 2
			;;
		*)
			if [ -n "$WP_FILE" ]; then
				echo "Error: extra wallpaper argument '$1'" >&2
				exit 2
			fi
			WP_FILE="$1"
			shift
			;;
		esac
	done
	if [ -z "$WP_FILE" ]; then
		echo "Error: wallpaper needs a file path" >&2
		exit 2
	fi
	if [ ! -e "$WP_FILE" ]; then
		echo "Error: wallpaper not found: $WP_FILE" >&2
		exit 1
	fi
	WP_ABS=$(readlink -f -- "$WP_FILE")
	WP_JSON=$(
		python3 -c '
import json, os, sys
payload = {"v": "wallpaper-set", "path": sys.argv[1]}
scheme, oled, tint, monitor = sys.argv[2:6]
if scheme:
    payload["scheme"] = scheme
if oled:
    payload["oled"] = True
if tint:
    payload["tint"] = True
if monitor:
    payload["monitor"] = monitor
print(json.dumps(payload))
' "$WP_ABS" "$WP_SCHEME" "$WP_OLED" "$WP_TINT" "$WP_MONITOR"
	)
	send_json_ipc "$WP_JSON" || exit 1
	echo "Wallpaper set: $WP_ABS"
	;;
preset)
	shift
	PRESET_ARG="${1:-}"
	PRESET_USER="${XDG_CONFIG_HOME:-$HOME/.config}/ambxst+/presets"
	PRESET_ASSETS="${SCRIPT_DIR}/assets/presets"
	if [ -z "$PRESET_ARG" ] || [ "$PRESET_ARG" = "-l" ]; then
		{
			[ -d "$PRESET_USER" ] && find "$PRESET_USER" -mindepth 1 -maxdepth 1 -type d -printf '%f\n'
			[ -d "$PRESET_ASSETS" ] && find "$PRESET_ASSETS" -mindepth 1 -maxdepth 1 -type d -printf '%f\n'
		} | sort -u
		exit 0
	fi
	PRESET_JSON=$(python3 -c 'import json,sys; print(json.dumps({"v":"preset-load","name":sys.argv[1]}))' "$PRESET_ARG")
	send_json_ipc "$PRESET_JSON" || exit 1
	echo "Preset load requested: $PRESET_ARG"
	;;
version | -v | --version)
	echo "Ambxst[+] $(cat "${SCRIPT_DIR}/version")"
	;;
install)
	TARGET="${2:-}"
	if [ "$TARGET" = "hyprland" ]; then
		HYPR_DIR="$HOME/.config/hypr"
		HYPR_LUA="$HYPR_DIR/hyprland.lua"
		HYPR_CONF="$HYPR_DIR/hyprland.conf"

		mkdir -p "$HYPR_DIR"

		if is_nix_store_symlink "$HYPR_LUA" || is_nix_store_symlink "$HYPR_CONF"; then
			print_home_manager_hyprland_guide
			exit 0
		fi

		if [ -f "$HYPR_LUA" ] || [ ! -f "$HYPR_CONF" ]; then
			append_ambxst_plus_hyprland_block "$HYPR_LUA" "$AMBXST_PLUS_HYPR_LUA_SOURCE" "$AMBXST_PLUS_HYPR_LUA_BLOCK"
			ensure_ambxst_plus_hyprland_source "$HOME/.local/share/ambxst+/hyprland.lua" "-- Ambxst[+] user overrides"
		else
			append_ambxst_plus_hyprland_block "$HYPR_CONF" "$AMBXST_PLUS_HYPR_CONF_SOURCE" "$AMBXST_PLUS_HYPR_CONF_BLOCK"
			ensure_ambxst_plus_hyprland_source "$HOME/.local/share/ambxst+/hyprland.conf" "# Ambxst[+] user overrides"
		fi
	else
		echo "Error: Unknown target '$TARGET'. Supported: hyprland"
		exit 1
	fi
	;;
remove)
	TARGET="${2:-}"
	if [ "$TARGET" = "hyprland" ]; then
		HYPR_DIR="$HOME/.config/hypr"
		HYPR_LUA="$HYPR_DIR/hyprland.lua"
		HYPR_CONF="$HYPR_DIR/hyprland.conf"

		if is_nix_store_symlink "$HYPR_LUA" || is_nix_store_symlink "$HYPR_CONF"; then
			echo "Ambxst[+]: Hyprland config is home-manager managed. Remove the import from home.nix instead."
			exit 0
		fi

		remove_ambxst_plus_hyprland_block "$HYPR_LUA" "$AMBXST_PLUS_HYPR_LUA_SOURCE"
		remove_ambxst_plus_hyprland_block "$HYPR_CONF" "$AMBXST_PLUS_HYPR_CONF_SOURCE"
	else
		echo "Error: Unknown target '$TARGET'. Supported: hyprland"
		exit 1
	fi
	;;
goodbye)
	echo "Uninstalling Ambxst[+]..."

	read -p "Are you sure? (y/N): " -n 1 -r
	echo
	if [[ ! $REPLY =~ ^[Yy]$ ]]; then
		echo "Uninstall aborted."
		exit 0
	fi

	if [ -f /etc/NIXOS ]; then
		if nix profile list 2>/dev/null | grep -q "ambxst"; then
			echo "Removing from nix profile..."
			nix profile remove 'ambxst.*'
		elif command -v ambxst+ >/dev/null 2>&1; then
			echo "Ambxst[+] was declared in this system. Please remove it from your configuration in order to uninstall."
		else
			echo "Ambxst[+] is not installed."
		fi
		# Remove the Hyprland import block if one was installed
		remove_ambxst_plus_hyprland_block "$HOME/.config/hypr/hyprland.lua" "$AMBXST_PLUS_HYPR_LUA_SOURCE" 2>/dev/null || true
		remove_ambxst_plus_hyprland_block "$HOME/.config/hypr/hyprland.conf" "$AMBXST_PLUS_HYPR_CONF_SOURCE" 2>/dev/null || true
		exit 0
	fi

	read -p "Remove configuration files? (y/N): " -n 1 -r
	echo
	REMOVE_CONFIG=false
	if [[ $REPLY =~ ^[Yy]$ ]]; then
		REMOVE_CONFIG=true
	fi

	# Remove the Hyprland import block if one was installed
	remove_ambxst_plus_hyprland_block "$HOME/.config/hypr/hyprland.lua" "$AMBXST_PLUS_HYPR_LUA_SOURCE" 2>/dev/null || true
	remove_ambxst_plus_hyprland_block "$HOME/.config/hypr/hyprland.conf" "$AMBXST_PLUS_HYPR_CONF_SOURCE" 2>/dev/null || true

	# Remove launcher installed by the curl installer (may need root)
	rm -f /usr/local/bin/ambxst+ 2>/dev/null || echo "Note: could not remove /usr/local/bin/ambxst+ (run as root if needed)"

	rm -rf "$HOME/.local/src/ambxst+"
	rm -rf "$HOME/.local/share/ambxst+"
	rm -rf "$HOME/.local/state/ambxst+"

	if [ "$REMOVE_CONFIG" = true ]; then
		rm -rf "$HOME/.config/ambxst+"
		echo "Configuration files removed."
	fi

	echo "Ambxst[+] uninstalled. :("
	;;
help | --help | -h)
	show_help
	;;
"")
	ensure_config_files

	# Run daemon priority script (backgrounded to not block startup)
	bash "${SCRIPT_DIR}/scripts/daemon_priority.sh" &

	# Set QS_ICON_THEME environment variable
	if command -v gsettings >/dev/null 2>&1; then
		if QS_ICON_THEME=$(gsettings get org.gnome.desktop.interface icon-theme 2>/dev/null | tr -d "'"); then
			export QS_ICON_THEME
		fi
	fi

	# Force Qt6CT
	export QT_QPA_PLATFORMTHEME=qt6ct
	unset HL_INITIAL_WORKSPACE_TOKEN

	# Cache this script's PID before exec (for fast PID lookups in future CLI calls)
	# In the runtime dir: user-owned (0700) and not world-writable, unlike /tmp
	echo $$ >"${XDG_RUNTIME_DIR:-/tmp}/ambxst+.pid"

	# Launch QuickShell with the main shell.qml
	# If NIXGL_BIN is set (NixOS/Nix setup), use it. Otherwise, just run qs directly.
	if [ -n "$NIXGL_BIN" ]; then
		exec "$NIXGL_BIN" "$QS_BIN" -p "${SCRIPT_DIR}/shell.qml"
	else
		exec "$QS_BIN" -p "${SCRIPT_DIR}/shell.qml"
	fi
	;;
*)
	echo "Error: Unknown command '$1'"
	echo "Run 'ambxst+ help' for usage information"
	exit 1
	;;
esac
