import QtQuick
import qs.modules.components
import qs.modules.theme
import qs.modules.globals
import Quickshell.Io

import qs.modules.services

ActionGrid {
    id: root

    signal itemSelected

    QtObject {
        id: recordAction
        property string icon: ScreenRecorder.isRecording ? Icons.stop : Icons.recordScreen
        property string text: ScreenRecorder.isRecording ? ScreenRecorder.duration : ""
        property string tooltip: ScreenRecorder.isRecording ? "Stop Recording" : "Screen Recorder"
        property string command: ""
        property string variant: ScreenRecorder.isRecording ? "error" : "primary"
        property string type: "button"
    }

    layout: "row"
    buttonSize: 48
    iconSize: 20
    spacing: 8

    actions: [
        {
            icon: Icons.camera,
            tooltip: "Screenshot",
            command: ""
        },
        {
            icon: Icons.screenshots,
            tooltip: "Open Screenshots",
            command: ""
        },
        {
            type: "separator"
        },
        recordAction,
        {
            icon: Icons.recordings,
            tooltip: "Open Recordings",
            command: ""
        },
        {
            type: "separator"
        },
        {
            icon: Icons.picker,
            tooltip: "Color Picker",
            command: ""
        },
        {
            icon: Icons.textT,
            tooltip: "OCR",
            command: ""
        },
        {
            icon: Icons.qrCode,
            tooltip: "QR Code",
            command: ""
        },
        {
            icon: Icons.google,
            tooltip: "Google Lens",
            command: ""
        },
        {
            icon: GlobalStates.mirrorWindowVisible ? Icons.webcamSlash : Icons.webcam,
            tooltip: "Mirror",
            command: ""
        }
    ]

    Process {
        id: colorPickerProc
    }

    Process {
        id: openFolderProc
        command: ["bash", "-c", "nohup xdg-open \"$0\" > /dev/null 2>&1 &"]
    }

    onActionTriggered: action => {
        if (action.tooltip === "Screenshot") {
            Screenshot.initialize();
            GlobalStates.screenshotToolVisible = true;
            root.itemSelected();
        } else if (action.tooltip === "Screen Recorder") {
            ScreenRecorder.initialize();
            GlobalStates.screenRecordToolVisible = true;
            root.itemSelected();
        } else if (action.tooltip === "Stop Recording") {
            ScreenRecorder.toggleRecording();
            root.itemSelected();
        } else if (action.tooltip === "Open Screenshots") {
            var cmd = "dir=\"$(xdg-user-dir PICTURES)/Screenshots\"; mkdir -p \"$dir\"; nohup xdg-open \"$dir\" > /dev/null 2>&1 &";
            
            openFolderProc.command = ["bash", "-c", cmd];
            openFolderProc.running = true;
            
            root.itemSelected();
        } else if (action.tooltip === "Open Recordings") {
            var cmd = "dir=\"$(xdg-user-dir VIDEOS)/Recordings\"; mkdir -p \"$dir\"; nohup xdg-open \"$dir\" > /dev/null 2>&1 &";
            
            openFolderProc.command = ["bash", "-c", cmd];
            openFolderProc.running = true;
            
             root.itemSelected();
        } else if (action.tooltip === "Color Picker") {
            var scriptPath = Qt.resolvedUrl("../../../scripts/colorpicker.py").toString().replace("file://", "");
            // Run detached so it survives when the menu closes
            colorPickerProc.command = ["bash", "-c", "nohup python3 \"" + scriptPath + "\" > /dev/null 2>&1 &"];
            colorPickerProc.running = true;
            root.itemSelected();
        } else if (action.tooltip === "OCR") {
            Screenshot.initialize();
            Screenshot.captureMode = "ocr";
            GlobalStates.screenshotToolVisible = true;
            root.itemSelected();
        } else if (action.tooltip === "QR Code") {
            Screenshot.initialize();
            Screenshot.captureMode = "qr";
            GlobalStates.screenshotToolVisible = true;
            root.itemSelected();
        } else if (action.tooltip === "Google Lens") {
            Screenshot.captureMode = "lens";
            GlobalStates.screenshotToolVisible = true;
            root.itemSelected();
        } else if (action.tooltip === "Mirror") {
            GlobalStates.mirrorWindowVisible = !GlobalStates.mirrorWindowVisible;
        }
    }
}
