import QtQuick
import Quickshell.Io

Item {
    id: inhibitor

    property bool enabled: false
    property var _inhibitorId: 0

    property var _createProcess: Process {
        id: _createProcess
        running: false
        stdout: StdioCollector {
            id: _createStdout
        }
        onExited: (code) => {
            if (code === 0 && _createStdout.text) {
                try {
                    var json = JSON.parse(_createStdout.text.trim());
                    _inhibitorId = json.id;
                } catch (e) {
                    console.error("Failed to parse inhibitor response:", _createStdout.text);
                }
            } else {
                console.error("Failed to create inhibitor: code=", code, "output:", _createStdout.text);
            }
        }
    }

    property var _destroyProcess: Process {
        id: _destroyProcess
        running: false
        onExited: (code) => {
            _inhibitorId = 0;
        }
    }

    property var _toggleProcess: Process {
        id: _toggleProcess
        running: false
    }

    function _run(proc, args) {
        proc.running = false;
        proc.command = ["axctl", "system"].concat(args);
        proc.running = true;
    }

    function _createInhibitor() {
        _run(_createProcess, ["idle-inhibitor-create", enabled ? "1" : "0"]);
    }

    function _destroyInhibitor() {
        if (_inhibitorId > 0) {
            _run(_destroyProcess, ["idle-inhibitor-destroy", String(_inhibitorId)]);
        }
    }

    function _toggleInhibitor(enable) {
        if (_inhibitorId > 0) {
            _run(_toggleProcess, ["idle-inhibitor-set", String(_inhibitorId), enable ? "1" : "0"]);
        }
    }

    onEnabledChanged: {
        if (_inhibitorId === 0) {
            _createInhibitor();
        } else {
            _toggleInhibitor(enabled);
        }
    }

    Component.onDestruction: {
        _destroyInhibitor();
    }

    Component.onCompleted: {
        if (enabled) {
            _createInhibitor();
        }
    }
}
