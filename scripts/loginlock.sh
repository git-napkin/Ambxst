#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"
LOCKFILE="$RUNTIME_DIR/ambxst+_loginlock.pid"
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

dbus-monitor --system "type='signal',interface='org.freedesktop.login1.Session',member='Lock'" |
	while read -r line; do
		if echo "$line" | grep -q "member=Lock"; then
			echo "LOCK"
		fi
	done
