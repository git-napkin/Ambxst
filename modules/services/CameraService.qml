pragma Singleton
pragma ComponentBehavior: Bound

import Quickshell
import Quickshell.Io
import qs.modules.services
import QtQuick

Singleton {
    id: root

    signal cameraListChanged(var cameras)
    signal cameraUsageChanged(bool inUse, var users)

    property list<var> cameras: []
    property bool cameraInUse: false
    property list<var> cameraUsers: []
    property bool cameraDisabled: false
    property int pollInterval: 2000
    property string _camerasKey: ""
    property string _usersKey: ""

    readonly property string scriptPath: Qt.resolvedUrl("../../scripts/camera_monitor.py").toString().replace("file://", "")

    property int _restartAttempts: 0
    readonly property int _restartCap: 10

    property Process cameraProcess: Process {
        command: ["python3", root.scriptPath, String(root.pollInterval / 1000)]
        running: false

        stdout: SplitParser {
            onRead: data => {
                if (!data)
                    return;
                try {
                    root.updateFromData(JSON.parse(data));
                    root._restartAttempts = 0;
                } catch (e) {
                    console.warn("CameraService: failed to parse monitor output");
                }
            }
        }

        onExited: {
            if (SuspendManager.isSuspending)
                return;
            root._restartAttempts++;
            if (root._restartAttempts >= root._restartCap) {
                console.warn("CameraService: restart cap reached, giving up until the next init/suspend cycle");
                return;
            }
            restartTimer.restart();
        }
    }

    property Timer restartTimer: Timer {
        interval: 5000
        repeat: false
        onTriggered: {
            if (!SuspendManager.isSuspending && root._restartAttempts < root._restartCap)
                cameraProcess.running = true;
        }
    }

    function _syncRunning() {
        if (SuspendManager.isSuspending)
            cameraProcess.running = false;
        else if (root._restartAttempts < root._restartCap)
            cameraProcess.running = true;
    }

    property var suspendConnections: Connections {
        target: SuspendManager
        function onIsSuspendingChanged() {
            root._syncRunning();
        }
        function onWakingUp() {
            root._restartAttempts = 0;
            root._syncRunning();
        }
    }

    function updateFromData(data) {
        const newCameras = data.cameras || [];
        const newUsers = data.users || [];
        const newInUse = !!data.inUse;
        const camKey = JSON.stringify(newCameras);
        const userKey = JSON.stringify(newUsers);

        if (camKey !== root._camerasKey) {
            root._camerasKey = camKey;
            root.cameras = newCameras;
            root.cameraListChanged(newCameras);
        }

        if (newInUse !== root.cameraInUse || userKey !== root._usersKey) {
            root._usersKey = userKey;
            root.cameraInUse = newInUse;
            root.cameraUsers = newUsers;
            root.cameraUsageChanged(newInUse, newUsers);
        }
    }

    reloadableId: "camera"

    Component.onCompleted: root._syncRunning()
}
