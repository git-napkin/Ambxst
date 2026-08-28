#!/usr/bin/env python3
"""Unit tests for Ambxst[+] Python scripts."""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


try:
    import cryptography  # noqa: F401
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


@unittest.skipUnless(HAS_CRYPTOGRAPHY, "cryptography not installed")
class TestKeystore(unittest.TestCase):
    """Tests for keystore.py encryption/decryption."""

    @classmethod
    def setUpClass(cls):
        """Import keystore module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "keystore", SCRIPTS_DIR / "keystore.py"
        )
        cls.keystore = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.keystore)

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypted text should decrypt back to original."""
        machine_key = b"test-machine-id-1234"
        original = "sk-test-1234567890abcdef"

        encrypted = self.keystore.encrypt(original, machine_key)
        decrypted = self.keystore.decrypt(encrypted, machine_key)

        self.assertEqual(decrypted, original)

    def test_encrypt_produces_different_output(self):
        """Each encryption should produce different output (random salt)."""
        machine_key = b"test-machine-id-1234"
        original = "sk-test-1234567890abcdef"

        enc1 = self.keystore.encrypt(original, machine_key)
        enc2 = self.keystore.encrypt(original, machine_key)

        self.assertNotEqual(enc1, enc2)

    def test_decrypt_invalid_returns_empty(self):
        """Decryption of invalid data should return empty string."""
        machine_key = b"test-machine-id-1234"
        result = self.keystore.decrypt("invalid-base64-data", machine_key)
        self.assertEqual(result, "")

    def test_get_machine_id_fallback(self):
        """get_machine_id should return bytes."""
        result = self.keystore.get_machine_id()
        self.assertIsInstance(result, bytes)
        self.assertTrue(len(result) > 0)


class TestSystemMonitor(unittest.TestCase):
    """Tests for system_monitor.py."""

    @classmethod
    def setUpClass(cls):
        """Import system_monitor module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "system_monitor", SCRIPTS_DIR / "system_monitor.py"
        )
        cls.monitor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.monitor)

    def test_system_monitor_initialization(self):
        """SystemMonitor should initialize with default values."""
        monitor = self.monitor.SystemMonitor(disks=["/"])
        self.assertEqual(monitor.prev_cpu_total, 0)
        self.assertEqual(monitor.prev_cpu_idle, 0)
        self.assertEqual(monitor.monitored_disks, ["/"])

    def test_cpu_usage_in_range(self):
        """CPU usage should be between 0 and 100."""
        monitor = self.monitor.SystemMonitor(disks=["/"])
        # First call returns 0 (no previous data)
        usage = monitor.get_cpu()
        self.assertGreaterEqual(usage, 0.0)
        self.assertLessEqual(usage, 100.0)

    def test_memory_in_range(self):
        """Memory usage should be between 0 and 100."""
        monitor = self.monitor.SystemMonitor(disks=["/"])
        usage, total, used, available = monitor.get_mem()
        self.assertGreaterEqual(usage, 0.0)
        self.assertLessEqual(usage, 100.0)

    def test_disk_usage_returns_dict(self):
        """Disk usage should return a dictionary."""
        monitor = self.monitor.SystemMonitor(disks=["/"])
        usage = monitor.get_disk_usage(["/"])
        self.assertIsInstance(usage, dict)
        self.assertIn("/", usage)


class TestColorpicker(unittest.TestCase):
    """Tests for colorpicker.py."""

    @classmethod
    def setUpClass(cls):
        """Import colorpicker module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "colorpicker", SCRIPTS_DIR / "colorpicker.py"
        )
        cls.colorpicker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.colorpicker)

    def test_cmd_function_exists(self):
        """cmd function should be callable."""
        self.assertTrue(callable(self.colorpicker.cmd))

    def test_main_function_exists(self):
        """main function should be callable."""
        self.assertTrue(callable(self.colorpicker.main))

    def test_notify_shell_returns_false_without_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkfifo(os.path.join(tmp, "ambxst+_ipc.pipe"))
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": tmp}):
                ok = self.colorpicker.notify_shell({"summary": "x", "body": "y"})
            self.assertFalse(ok)

    def test_notify_shell_writes_json_when_reader_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipe = os.path.join(tmp, "ambxst+_ipc.pipe")
            os.mkfifo(pipe)
            got = {}

            def read():
                with open(pipe, "r", encoding="utf-8") as fh:
                    got["line"] = fh.readline()

            reader = threading.Thread(target=read)
            reader.start()
            time.sleep(0.1)
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": tmp}):
                ok = self.colorpicker.notify_shell({
                    "summary": "Color Picked",
                    "body": "#fff",
                    "actions": [{"identifier": "hex", "clipboard": "#fff"}],
                })
            reader.join(timeout=2)
            self.assertTrue(ok)
            payload = json.loads(got["line"])
            self.assertEqual(payload["v"], "notify")
            self.assertEqual(payload["summary"], "Color Picked")
            self.assertEqual(payload["actions"][0]["clipboard"], "#fff")


class TestDesktopScan(unittest.TestCase):
    def test_scan_lists_folders_files_and_desktop_entries(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "desktop_scan", SCRIPTS_DIR / "desktop_scan.py"
        )
        scan_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scan_mod)

        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, "Docs"))
            with open(os.path.join(tmp, "notes.txt"), "w") as f:
                f.write("hi")
            with open(os.path.join(tmp, "App.desktop"), "w") as f:
                f.write("[Desktop Entry]\nName=Cool App\nIcon=cool-app\n")
            with open(os.path.join(tmp, ".hidden"), "w") as f:
                f.write("nope")

            items = {item["name"]: item for item in scan_mod.scan(tmp)}
            self.assertIn("Docs", items)
            self.assertEqual(items["Docs"]["type"], "folder")
            self.assertIn("notes.txt", items)
            self.assertIsNone(items["notes.txt"]["type"])
            self.assertEqual(items["Cool App"]["icon"], "cool-app")
            self.assertTrue(items["Cool App"]["isDesktopFile"])
            self.assertNotIn(".hidden", items)


REPO_ROOT = Path(__file__).parent.parent


class TestJustWorksContracts(unittest.TestCase):
    def _read(self, *parts):
        return REPO_ROOT.joinpath(*parts).read_text()

    def test_ipc_pipe_uses_runtime_dir(self):
        cli = self._read("cli.sh")
        shortcuts = self._read("modules/services/GlobalShortcuts.qml")
        self.assertIn('PIPE="${XDG_RUNTIME_DIR:-/tmp}/ambxst+_ipc.pipe"', cli)
        self.assertNotIn('PIPE="/tmp/ambxst+_ipc.pipe"', cli)
        self.assertIn("XDG_RUNTIME_DIR", shortcuts)
        self.assertNotIn('"/tmp/ambxst+_ipc.pipe"', shortcuts)

    def test_loginlock_steals_held_lock(self):
        src = self._read("scripts/loginlock.sh")
        self.assertIn('kill "$pid"', src)
        self.assertNotIn("exit 0", src)

    def test_sleep_monitor_steals_held_lock(self):
        src = self._read("scripts/sleep_monitor.sh")
        self.assertIn('kill "$pid"', src)
        self.assertNotIn("exit 0", src)

    def test_idle_service_restarts_monitors_on_clean_exit(self):
        src = self._read("modules/services/IdleService.qml")
        self.assertNotIn("if (exitCode !== 0)", src)
        self.assertIn("loginLockRestartTimer", src)
        self.assertIn("sleepMonitorRestartTimer", src)

    def test_clock_uses_system_clock_minutes(self):
        src = self._read("modules/bar/clock/Clock.qml")
        self.assertIn("SystemClock", src)
        self.assertIn("SystemClock.Minutes", src)

    def test_idle_inhibitor_uses_argv(self):
        src = self._read("modules/services/IdleInhibitor.qml")
        self.assertIn("idle-inhibitor-create", src)
        self.assertNotIn('["sh", "-c", cmd]', src)
        self.assertNotIn('command: ["sh", "-c", ""]', src)

    def test_camera_watcher_has_restart_cap(self):
        src = self._read("modules/services/CameraService.qml")
        self.assertIn("_restartCap", src)

    def test_camera_service_init_uses_sync_running(self):
        src = self._read("shell.qml")
        self.assertIn("CameraService._syncRunning.toString()", src)
        self.assertNotIn("CameraService.update.toString()", src)

    def test_axctl_restore_focus_reuses_process(self):
        src = self._read("modules/services/AxctlService.qml")
        self.assertNotIn("Qt.createQmlObject", src)

    def test_weather_missing_tools_returns_error_json(self):
        import shutil
        import subprocess

        bash = shutil.which("bash") or "/bin/bash"
        env = os.environ.copy()
        env["PATH"] = "/nonexistent"
        result = subprocess.run(
            [bash, str(SCRIPTS_DIR / "weather.sh")],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout.strip().split("\n")[-1])
        self.assertIn("error", payload)
        self.assertIn("missing", payload["error"])

    def test_bar_popups_are_mutually_exclusive(self):
        popup = self._read("modules/components/BarPopup.qml")
        vis = self._read("modules/services/Visibilities.qml")
        self.assertIn('property string groupId: "bar"', popup)
        self.assertIn("registerBarPopup", vis)
        self.assertIn("barPopupGroups", vis)

    def test_workspace_slide_follows_bar_position(self):
        src = self._read("modules/services/CompositorTomlWriter.qml")
        self.assertIn("slidefadevert 20%", src)
        self.assertIn("workspace_style", src)

    def test_gtk_darkmode_is_optional(self):
        src = self._read("modules/theme/GtkGenerator.qml")
        self.assertIn("axctl darkmode", src)
        self.assertIn("command -v axctl", src)

    def test_zen_theme_writes_plus_cache(self):
        src = self._read("modules/theme/PywalZenGenerator.qml")
        self.assertIn("/ambxst+/pywalzen.css", src)
        colors = self._read("modules/theme/Colors.qml")
        self.assertIn("pywalZenGenerator.generate(colors)", colors)

    def test_qml_toasts_use_in_shell_notifications(self):
        for rel in (
            "modules/services/PresetsService.qml",
            "modules/services/ScreenRecorder.qml",
            "modules/services/UpdateService.qml",
            "modules/bar/clock/Pomodoro.qml",
            "modules/services/Screenshot.qml",
        ):
            src = self._read(rel)
            self.assertIn("Notifications.notifyInternal", src)
            self.assertNotIn("notify-send", src)

    def test_terminal_is_configurable(self):
        defaults = self._read("config/defaults/system.js")
        config = self._read("config/Config.qml")
        tmux = self._read("modules/widgets/dashboard/tmux/TmuxTab.qml")
        self.assertIn('"terminal": "kitty"', defaults)
        self.assertIn('property string terminal: "kitty"', config)
        self.assertIn("TerminalService.execDetached", tmux)
        self.assertNotIn("kitty -e", tmux)

    def test_cli_json_ipc_and_hyprland_guard(self):
        cli = self._read("cli.sh")
        shortcuts = self._read("modules/services/GlobalShortcuts.qml")
        self.assertIn("wallpaper-set", cli)
        self.assertIn("preset-load", cli)
        self.assertIn("is_nix_store_symlink", cli)
        self.assertIn('case "notify":', shortcuts)
        self.assertIn('case "wallpaper-set":', shortcuts)
        self.assertIn("handleNotifyRequest", shortcuts)

    def test_settings_screen_bound_before_map(self):
        src = self._read("modules/widgets/config/SettingsWindow.qml")
        self.assertIn("screen: screenByName(GlobalStates.settingsTargetScreenName)", src)
        self.assertNotIn("settingsWindow.screen =", src)

    def test_ocr_qr_reuse_screenshot_overlay(self):
        tools = self._read("modules/widgets/tools/ToolsMenu.qml")
        shot = self._read("modules/services/Screenshot.qml")
        self.assertIn('Screenshot.captureMode = "ocr"', tools)
        self.assertIn('Screenshot.captureMode = "qr"', tools)
        self.assertNotIn("ocr.sh", tools)
        self.assertIn("function _runRecognition", shot)


class TestCliPort(unittest.TestCase):
    CLI = REPO_ROOT / "cli.sh"

    def test_cli_syntax(self):
        subprocess.run(["bash", "-n", str(self.CLI)], check=True)

    def test_help_lists_wallpaper_and_preset(self):
        result = subprocess.run(
            ["bash", str(self.CLI), "help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("wallpaper <file>", result.stdout)
        self.assertIn('preset -l', result.stdout)

    def test_wallpaper_missing_file_fails_before_ipc(self):
        result = subprocess.run(
            ["bash", str(self.CLI), "wallpaper", "/no/such/ambxst-wallpaper.png"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr)

    def test_preset_list_runs_without_shell(self):
        result = subprocess.run(
            ["bash", str(self.CLI), "preset", "-l"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("ambxst+ Default", result.stdout)

    def test_nix_store_symlink_detection(self):
        text = self.CLI.read_text()
        match = re.search(r"^is_nix_store_symlink\(\) \{.*?\n\}", text, re.M | re.S)
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "hyprland.lua")
            other = os.path.join(tmp, "plain.lua")
            os.symlink("/nix/store/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee-hypr/hyprland.lua", store)
            os.symlink("/tmp/elsewhere.lua", other)
            probe = match.group(0) + '\nis_nix_store_symlink "$1"\n'
            store_rc = subprocess.run(["bash", "-c", probe, "_", store]).returncode
            other_rc = subprocess.run(["bash", "-c", probe, "_", other]).returncode
            self.assertEqual(store_rc, 0)
            self.assertNotEqual(other_rc, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
