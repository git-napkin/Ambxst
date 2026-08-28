#!/usr/bin/env bash
set -euo pipefail
# Usage: clipboard_watch.sh <check_script> <db_path> <insert_script> <data_dir>
# wl-paste --watch feeds clipboard bytes on stdin; drain them so the watch
# doesn't block. The check script talks to wl-paste itself.

CHECK_SCRIPT="$1"
DB_PATH="$2"
INSERT_SCRIPT="$3"
DATA_DIR="$4"

exec wl-paste --watch bash -c 'cat >/dev/null; if "$0" "$1" "$2" "$3"; then echo REFRESH_LIST; fi' \
	"$CHECK_SCRIPT" "$DB_PATH" "$INSERT_SCRIPT" "$DATA_DIR"
