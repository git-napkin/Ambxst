#!/usr/bin/env python3
"""Unit tests for Ambxst[+] Python scripts."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


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
    """Source contracts for daemon lifetime, IPC, and clock tick rate."""

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
