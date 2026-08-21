#!/usr/bin/env python3
"""
Fingerprint authentication helper using fprintd D-Bus API.
Outputs JSON to stdout for QML consumption.

Usage:
  python3 fprintd_auth.py check       - Check if fprintd is available and fingers enrolled
  python3 fprintd_auth.py verify      - Start fingerprint verification (blocks until done)
  python3 fprintd_auth.py enroll <finger> - Enroll a finger
  python3 fprintd_auth.py delete <finger> - Delete enrolled finger
  python3 fprintd_auth.py list        - List enrolled fingers
"""

import sys
import json
import os
import re
import time
import pwd

sys.stdout.reconfigure(line_buffering=True)

try:
    import dbus
    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False

FPRINTD_SERVICE = "net.reactivated.Fprint"
FPRINTD_MANAGER_PATH = "/net/reactivated/Fprint/Manager"
FPRINTD_MANAGER_IFACE = "net.reactivated.Fprint.Manager"
FPRINTD_PATH = "/net/reactivated/Fprint/Device/0"
FPRINTD_INTERFACE = "net.reactivated.Fprint.Device"

ENROLL_HINTS = {
    2: "Scan failed — try again",
    3: "Retry the scan",
    4: "Finger moved too quickly — try again",
    5: "Center your finger on the sensor",
    6: "Lift your finger and try again",
    7: "Swipe was too short — try again",
    8: "Sensor disconnected",
}

# fprintd >= 1.90 emits string statuses on VerifyStatus/EnrollStatus;
# map them to hint text (int codes above are legacy fallbacks).
VERIFY_STATUS_HINTS = {
    "verify-swipe-too-short": "Swipe was too short — try again",
    "verify-finger-not-centered": "Center your finger on the sensor",
    "verify-remove-and-retry": "Lift your finger and try again",
    "verify-disconnected": "Sensor disconnected",
}

ENROLL_STATUS_HINTS = {
    "enroll-stage-passed": "__stage__",
    "enroll-retry-scan": "Retry the scan",
    "enroll-scan-failed": "Scan failed — try again",
    "enroll-finger-not-centered": "Center your finger on the sensor",
    "enroll-remove-and-retry": "Lift your finger and try again",
    "enroll-swipe-too-short": "Swipe was too short — try again",
    "enroll-disconnected": "Sensor disconnected",
}


def _status_str(value):
    """Normalize a dbus status arg to a plain string, or None for ints/other."""
    if isinstance(value, int):
        return None
    try:
        s = str(value)
    except Exception:
        return None
    return s if not s.isdigit() else None


def get_bus():
    """Get D-Bus bus — fprintd is a system service, try SystemBus first."""
    if not HAS_DBUS:
        return None
    # Prefer SystemBus (fprintd is system service)
    try:
        bus = dbus.SystemBus()
        # Quick check that we can connect
        return bus
    except Exception:
        pass
    try:
        return dbus.SessionBus()
    except Exception:
        return None


def _get_device_path(bus):
    """Resolve device path via Manager.GetDefaultDevice, fallback to Device/0."""
    try:
        manager = dbus.Interface(
            bus.get_object(FPRINTD_SERVICE, FPRINTD_MANAGER_PATH),
            FPRINTD_MANAGER_IFACE,
        )
        # GetDevices returns array; GetDefaultDevice returns single path
        try:
            path = manager.GetDefaultDevice()
            if path:
                return str(path)
        except dbus.DBusException:
            pass
        try:
            devices = manager.GetDevices()
            if devices and len(devices) > 0:
                return str(devices[0])
        except dbus.DBusException:
            pass
    except Exception:
        pass
    return FPRINTD_PATH


def _get_username():
    """Get current username securely (don't trust $USER which can be spoofed)."""
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        return os.environ.get("USER", "")


def _parse_finger_list(fingers):
    """Normalize fprintd finger list (array of strings) to Python list[str]."""
    if not fingers:
        return []
    result = []
    # dbus may return array of dbus.String or plain str
    for f in fingers:
        if isinstance(f, (list, tuple)):
            for item in f:
                result.append(str(item))
        else:
            result.append(str(f))
    # Filter to valid finger names
    valid = re.compile(r"^[a-z-]+$")
    # Don't strictly filter; keep whatever fprintd returns
    return result


def check_available():
    """Check if fprintd is available and fingers are enrolled."""
    result = {
        "available": False,
        "enrolled": False,
        "fingers": [],
        "error": None
    }

    if not HAS_DBUS:
        result["error"] = "python-dbus not installed"
        print(json.dumps(result))
        return

    try:
        bus = get_bus()
        if bus is None:
            result["error"] = "Failed to get D-Bus bus"
            print(json.dumps(result))
            return

        if not bus.name_has_owner(FPRINTD_SERVICE):
            result["error"] = "fprintd service not running"
            print(json.dumps(result))
            return

        result["available"] = True

        device_path = _get_device_path(bus)
        device = dbus.Interface(
            bus.get_object(FPRINTD_SERVICE, device_path),
            FPRINTD_INTERFACE
        )

        fingers = device.ListEnrolledFingers()
        finger_list = _parse_finger_list(fingers)

        result["fingers"] = finger_list
        result["enrolled"] = len(finger_list) > 0

    except Exception as e:
        result["error"] = str(e)

    print(json.dumps(result))


def verify_finger():
    """Start fingerprint verification and wait for result."""
    result = {
        "success": False,
        "error": None,
        "finger": None
    }

    if not HAS_DBUS:
        result["error"] = "python-dbus not installed"
        print(json.dumps(result))
        return

    try:
        bus = get_bus()
        if bus is None:
            result["error"] = "Failed to get D-Bus bus"
            print(json.dumps(result))
            return

        if not bus.name_has_owner(FPRINTD_SERVICE):
            result["error"] = "fprintd service not running"
            print(json.dumps(result))
            return

        device_path = _get_device_path(bus)
        device = dbus.Interface(
            bus.get_object(FPRINTD_SERVICE, device_path),
            FPRINTD_INTERFACE
        )

        username = _get_username()
        if username:
            try:
                device.SetUsername(username)
            except dbus.DBusException:
                pass

        fingers = device.ListEnrolledFingers()
        finger_list = _parse_finger_list(fingers)
        if not finger_list:
            result["error"] = "No fingers enrolled"
            print(json.dumps(result))
            return

        first_finger = finger_list[0]
        result["finger"] = first_finger

        try:
            device.VerifyStart(first_finger)
        except dbus.DBusException as e:
            result["error"] = f"VerifyStart failed: {e}"
            print(json.dumps(result))
            return

        print(json.dumps({"status": "scanning", "finger": first_finger}))
        sys.stdout.flush()

        done = False
        success = False
        timeout_count = 0
        max_timeout = 30
        last_hint = None

        while not done and timeout_count < max_timeout:
            try:
                msg = bus.pop_message()
                while msg is not None:
                    if msg.get_member() == "VerifyStatus":
                        args = msg.get_args_list()
                        if len(args) >= 2:
                            done = bool(args[0])
                            status = _status_str(args[1])
                            if done:
                                # fprintd >= 1.90: "verify-match" / "verify-no-match";
                                # legacy int codes: 1 = match. Unknown → assume match.
                                success = (status == "verify-match" if status is not None
                                           else (args[1] == 1 if isinstance(args[1], int) else True))
                            else:
                                hint = VERIFY_STATUS_HINTS.get(status)
                                if hint and hint != last_hint:
                                    print(json.dumps({"status": "hint", "message": hint}))
                                    sys.stdout.flush()
                                last_hint = hint
                    msg = bus.pop_message()

                if not done:
                    time.sleep(0.1)
                    timeout_count += 0.1
            except dbus.DBusException:
                time.sleep(0.1)
                timeout_count += 0.1
            except Exception:
                time.sleep(0.1)
                timeout_count += 0.1

        try:
            device.VerifyStop()
        except Exception:
            pass

        if done:
            result["success"] = success
            if not success:
                result["error"] = "Fingerprint did not match"
        else:
            result["error"] = "Fingerprint verification timed out"

    except Exception as e:
        result["error"] = str(e)

    print(json.dumps(result))


def enroll_finger(finger):
    """Enroll a new finger."""
    # Validate finger name
    if not re.match(r"^[a-z-]+$", finger):
        print(json.dumps({"success": False, "error": "Invalid finger name", "finger": finger}))
        return

    result = {
        "success": False,
        "error": None,
        "finger": finger
    }

    if not HAS_DBUS:
        result["error"] = "python-dbus not installed"
        print(json.dumps(result))
        return

    try:
        bus = get_bus()
        if bus is None:
            result["error"] = "Failed to get D-Bus bus"
            print(json.dumps(result))
            return

        if not bus.name_has_owner(FPRINTD_SERVICE):
            result["error"] = "fprintd service not running"
            print(json.dumps(result))
            return

        device_path = _get_device_path(bus)
        device = dbus.Interface(
            bus.get_object(FPRINTD_SERVICE, device_path),
            FPRINTD_INTERFACE
        )

        username = _get_username()
        if username:
            try:
                device.SetUsername(username)
            except dbus.DBusException:
                pass

        try:
            device.EnrollStart(finger)
        except dbus.DBusException as e:
            result["error"] = f"EnrollStart failed: {e}"
            print(json.dumps(result))
            return

        print(json.dumps({"status": "enrolling", "finger": finger, "stage": 0}))
        sys.stdout.flush()

        done = False
        success = False
        stage = 0
        timeout_count = 0
        max_timeout = 120
        last_hint = None

        while not done and timeout_count < max_timeout:
            try:
                msg = bus.pop_message()
                while msg is not None:
                    if msg.get_member() == "EnrollStatus":
                        args = msg.get_args_list()
                        if len(args) >= 2:
                            done = bool(args[0])
                            status = _status_str(args[1])
                            if done:
                                # fprintd >= 1.90: "enroll-completed" / "enroll-failed";
                                # legacy int codes: 0 = complete. Unknown → assume success.
                                success = (status == "enroll-completed" if status is not None
                                           else (args[1] == 0 if isinstance(args[1], int) else True))
                            elif status == "enroll-stage-passed" or args[1] == 1:
                                stage += 1
                                print(json.dumps({"status": "scanning", "stage": stage, "message": "Lift and replace your finger"}))
                                sys.stdout.flush()
                            else:
                                hint = ENROLL_STATUS_HINTS.get(status) or ENROLL_HINTS.get(args[1] if isinstance(args[1], int) else None)
                                if hint and hint != last_hint:
                                    print(json.dumps({"status": "hint", "stage": stage, "message": hint}))
                                    sys.stdout.flush()
                                last_hint = hint
                    msg = bus.pop_message()

                if not done:
                    time.sleep(0.1)
                    timeout_count += 0.1
            except dbus.DBusException:
                time.sleep(0.1)
                timeout_count += 0.1
            except Exception:
                time.sleep(0.1)
                timeout_count += 0.1

        if done:
            result["success"] = success
            result["stage"] = stage
            if not success:
                result["error"] = "Enrollment failed"
        else:
            result["error"] = "Enrollment timed out"

    except Exception as e:
        result["error"] = str(e)

    print(json.dumps(result))


def delete_finger(finger):
    """Delete an enrolled finger."""
    if not re.match(r"^[a-z-]+$", finger):
        print(json.dumps({"success": False, "error": "Invalid finger name", "finger": finger}))
        return

    result = {
        "success": False,
        "error": None,
        "finger": finger
    }

    if not HAS_DBUS:
        result["error"] = "python-dbus not installed"
        print(json.dumps(result))
        return

    try:
        bus = get_bus()
        if bus is None:
            result["error"] = "Failed to get D-Bus bus"
            print(json.dumps(result))
            return

        if not bus.name_has_owner(FPRINTD_SERVICE):
            result["error"] = "fprintd service not running"
            print(json.dumps(result))
            return

        device_path = _get_device_path(bus)
        device = dbus.Interface(
            bus.get_object(FPRINTD_SERVICE, device_path),
            FPRINTD_INTERFACE
        )

        # DeleteEnrolledFinger(finger) exists on fprintd >= 1.90. Older API only
        # has DeleteEnrolledFingers(username) which deletes ALL fingers — we
        # deliberately do NOT fall back to it to avoid wiping every enrollment.
        device.DeleteEnrolledFinger(finger)
        result["success"] = True

    except Exception as e:
        result["error"] = str(e)

    print(json.dumps(result))


def list_fingers():
    """List enrolled fingers."""
    result = {
        "available": False,
        "fingers": [],
        "error": None
    }

    if not HAS_DBUS:
        result["error"] = "python-dbus not installed"
        print(json.dumps(result))
        return

    try:
        bus = get_bus()
        if bus is None:
            result["error"] = "Failed to get D-Bus bus"
            print(json.dumps(result))
            return

        if not bus.name_has_owner(FPRINTD_SERVICE):
            result["error"] = "fprintd service not running"
            print(json.dumps(result))
            return

        result["available"] = True

        device_path = _get_device_path(bus)
        device = dbus.Interface(
            bus.get_object(FPRINTD_SERVICE, device_path),
            FPRINTD_INTERFACE
        )

        fingers = device.ListEnrolledFingers()
        result["fingers"] = _parse_finger_list(fingers)

    except Exception as e:
        result["error"] = str(e)

    print(json.dumps(result))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command specified"}))
        sys.exit(1)

    command = sys.argv[1]

    if command == "check":
        check_available()
    elif command == "verify":
        verify_finger()
    elif command == "enroll":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "No finger specified"}))
            sys.exit(1)
        enroll_finger(sys.argv[2])
    elif command == "delete":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "No finger specified"}))
            sys.exit(1)
        delete_finger(sys.argv[2])
    elif command == "list":
        list_fingers()
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)
