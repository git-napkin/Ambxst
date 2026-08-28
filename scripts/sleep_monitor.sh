#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"
LOCKFILE="$RUNTIME_DIR/ambxst+_sleep_monitor.pid"
mkdir -p "$RUNTIME_DIR"

take_lock() {
	set -C
	if (echo $$ >"$LOCKFILE") 2>/dev/null; then
		set +C
		return 0
	fi
	set +C
	local pid
	pid=$(cat "$LOCKFILE" 2>/dev/null || echo "")
	if [ -n "$pid" ] && [ "$pid" != "$$" ] && [ -O "$LOCKFILE" ] && kill -0 "$pid" 2>/dev/null; then
		kill "$pid" 2>/dev/null || true
		sleep 0.1
	fi
	rm -f "$LOCKFILE"
	set -C
	echo $$ >"$LOCKFILE"
	set +C
}

take_lock

# grep --line-buffered: GNU grep otherwise buffers the logind boolean in the pipe.
dbus-monitor --system "type='signal',interface='org.freedesktop.login1.Manager',member='PrepareForSleep'" |
	grep --line-buffered "boolean" |
	while read -r line; do
		if echo "$line" | grep -q "true"; then
			echo "SUSPEND"
		elif echo "$line" | grep -q "false"; then
			echo "WAKE"
		fi
	done
