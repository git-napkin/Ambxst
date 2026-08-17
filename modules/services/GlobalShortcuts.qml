pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import qs.modules.globals
import qs.modules.services
import qs.config

import Quickshell.Io

QtObject {
    id: root

    readonly property string appId: "ambxst+"
    readonly property string ipcPipe: "/tmp/ambxst+_ipc.pipe"

    // Restart the IPC pipe reader if it exits unexpectedly (OOM, /tmp cleared,
    // hot-reload race, etc.) so the command channel never dies silently.
    property Timer pipeRestartTimer: Timer {
        interval: 1000
        repeat: false
        onTriggered: {
            if (!SuspendManager.isSuspending)
                root.pipeListener.running = true;
        }
    }

    // High-performance Pipe Listener (Daemon mode)
    property Process pipeListener: Process {
        command: ["bash", "-c", "rm -f " + root.ipcPipe + "; mkfifo " + root.ipcPipe + "; tail -f " + root.ipcPipe]
        running: true

        stdout: SplitParser {
            onRead: data => {
                const cmd = data.trim();
                if (cmd !== "") {
                    root.run(cmd);
                }
            }
        }

        onExited: (code) => {
            // Restart on abnormal exit; a clean stop (e.g. shell shutdown) is 0.
            if (code !== 0 && !SuspendManager.isSuspending)
                root.pipeRestartTimer.restart();
        }
    }

    // Super keys bound with the release flag (launcher/dashboard) would also
    // fire after a chord (e.g. SUPER + T): Hyprland has no "exclude when part
    // of a chord" flag and its Lua API cannot express catchall binds. Instead
    // the shell arms a slot on modkey press and treats any OTHER ambxst+ IPC
    // arriving while a slot is armed as the chord; the release bind then only
    // toggles when the slot is still clean (a bare tap of the modkey).
    property var superSlots: ({})  // key -> { action: string, chord: bool }

    function superPress(key, action) {
        superSlots[key] = { action: action, chord: false };
    }

    function superChord() {
        for (const key in superSlots) {
            superSlots[key].chord = true;
        }
    }

    function superRelease(key) {
        const slot = superSlots[key];
        delete superSlots[key];
        if (slot && !slot.chord && slot.action) {
            root.run(slot.action);
        }
    }

    function run(command) {
        console.log("IPC run command received:", command);
        const parts = command.split(" ");
        const verb = parts[0];
        if (verb === "super-press") {
            superPress(parts[1], parts.slice(2).join(" "));
            return;
        }
        if (verb === "super-release") {
            superRelease(parts[1]);
            return;
        }
        switch (verb) {
            // Launcher (Standalone Notch Module)
            case "launcher": superChord(); toggleLauncher(); break;
            case "clipboard": superChord(); toggleLauncherWithPrefix(1, (Config.prefix?.clipboard ?? "") + " "); break;
            case "emoji": superChord(); toggleLauncherWithPrefix(2, (Config.prefix?.emoji ?? "") + " "); break;
            case "tmux": superChord(); toggleLauncherWithPrefix(3, (Config.prefix?.tmux ?? "") + " "); break;
            case "notes": superChord(); toggleLauncherWithPrefix(4, (Config.prefix?.notes ?? "") + " "); break;

            // Dashboard
            case "dashboard": superChord(); toggleDashboardTab(0); break;
            case "wallpapers": superChord(); toggleDashboardTab(1); break;
            case "assistant": superChord(); toggleAssistant(); break;
            case "dashboard-widgets": superChord(); toggleDashboardTab(0); break;
            case "dashboard-wallpapers": superChord(); toggleDashboardTab(1); break;
            case "dashboard-kanban": superChord(); toggleDashboardTab(2); break;
            case "dashboard-assistant": superChord(); toggleAssistant(); break;
            case "dashboard-controls": superChord(); toggleSettings(); break;

            // System
            case "overview": superChord(); toggleSimpleModule("overview"); break;
            case "powermenu": superChord(); toggleSimpleModule("powermenu"); break;
            case "tools": superChord(); toggleSimpleModule("tools"); break;
            case "config": superChord(); toggleSettings(); break;
            case "screenshot": superChord(); Screenshot.initialize(); GlobalStates.screenshotToolVisible = true; break;
            case "screenrecord": superChord(); ScreenRecorder.initialize(); GlobalStates.screenRecordToolVisible = true; break;
            case "lens": 
                superChord();
                Screenshot.initialize();
                Screenshot.captureMode = "lens";
                GlobalStates.screenshotToolVisible = true;
                break;
            case "lockscreen": superChord(); GlobalStates.lockscreenVisible = true; break;

            // Audio
            case "volume-up": superChord(); Audio.incrementVolume(); break;
            case "volume-down": superChord(); Audio.decrementVolume(); break;
            case "volume-up-fine": superChord(); Audio.incrementVolumeFine(); break;
            case "volume-down-fine": superChord(); Audio.decrementVolumeFine(); break;
            case "volume-mute": superChord(); Audio.toggleMute(); break;
            case "mic-mute": superChord(); Audio.toggleMicMute(); break;

            // Media
            case "media-seek-backward": superChord(); seekActivePlayer(-mediaSeekStepMs); break;
            case "media-seek-forward": superChord(); seekActivePlayer(mediaSeekStepMs); break;
            case "media-play-pause": 
                superChord();
                if (MprisController.canTogglePlaying) MprisController.togglePlaying();
                break;
            case "media-next": superChord(); MprisController.next(); break;
            case "media-prev": superChord(); MprisController.previous(); break;
                
            default: console.warn("Unknown IPC command:", command);
        }
    }

    property IpcHandler ipcHandler: IpcHandler {
        target: "ambxst+"

        function run(command: string) {
            root.run(command);
        }
    }

    function toggleSettings(screenName) {
        const willOpen = !GlobalStates.settingsWindowVisible;
        if (willOpen) {
            const targetMonitor = screenName ? AxctlService.monitorFor(screenName) : AxctlService.focusedMonitor;
            GlobalStates.settingsTargetWorkspaceId = targetMonitor?.activeWorkspace?.id || AxctlService.focusedMonitor?.activeWorkspace?.id || AxctlService.focusedWorkspace?.id || 0;
            GlobalStates.settingsTargetScreenName = targetMonitor?.name || AxctlService.focusedMonitor?.name || "";
            if (targetMonitor && targetMonitor.id !== AxctlService.focusedMonitor?.id) {
                AxctlService.dispatch(`focusmonitor ${targetMonitor.id}`);
            }
            Qt.callLater(() => Visibilities.setActiveModule(""));
        }
        GlobalStates.settingsWindowVisible = willOpen;
    }

    function toggleSimpleModule(moduleName) {
        if (Visibilities.currentActiveModule === moduleName) {
            Visibilities.setActiveModule("");
        } else {
            Visibilities.setActiveModule(moduleName);
        }
    }

    function toggleLauncher() {
        const isActive = Visibilities.currentActiveModule === "launcher";
        if (isActive && GlobalStates.widgetsTabCurrentIndex === 0 && GlobalStates.launcherSearchText === "") {
            Visibilities.setActiveModule("");
        } else {
            GlobalStates.widgetsTabCurrentIndex = 0;
            GlobalStates.launcherSearchText = "";
            GlobalStates.launcherSelectedIndex = -1;
            if (!isActive) {
                Visibilities.setActiveModule("launcher");
            }
        }
    }

    function toggleLauncherWithPrefix(tabIndex, prefix) {
        const isActive = Visibilities.currentActiveModule === "launcher";
        const currentTab = GlobalStates.widgetsTabCurrentIndex;
        const currentText = GlobalStates.launcherSearchText;

        if (isActive && currentTab === tabIndex && (currentText === prefix || currentText === "")) {
            Visibilities.setActiveModule("");
            GlobalStates.clearLauncherState();
            return;
        }

        GlobalStates.widgetsTabCurrentIndex = tabIndex;
        GlobalStates.launcherSearchText = prefix;
        
        if (!isActive) {
            Visibilities.setActiveModule("launcher");
        }
    }

    function toggleDashboardTab(tabIndex) {
        const isActive = Visibilities.currentActiveModule === "dashboard";
        
        // Special handling for widgets tab (launcher)
        if (tabIndex === 0) {
            if (isActive && GlobalStates.dashboardCurrentTab === 0 && GlobalStates.launcherSearchText === "") {
                // Only toggle off if we're already in launcher without prefix
                Visibilities.setActiveModule("");
                return;
            }
            
            // Otherwise, always go to launcher (clear any prefix and ensure tab 0)
            GlobalStates.dashboardCurrentTab = 0;
            GlobalStates.launcherSearchText = "";
            GlobalStates.launcherSelectedIndex = -1;
            if (!isActive) {
                Visibilities.setActiveModule("dashboard");
            }
            return;
        }
        
        // For other tabs, normal toggle behavior
        if (isActive && GlobalStates.dashboardCurrentTab === tabIndex) {
            Visibilities.setActiveModule("");
            return;
        }

        GlobalStates.dashboardCurrentTab = tabIndex;
        if (!isActive) {
            Visibilities.setActiveModule("dashboard");
        }
    }

    function toggleDashboardWithPrefix(prefix) {
        const isActive = Visibilities.currentActiveModule === "dashboard";
        
        if (isActive && GlobalStates.dashboardCurrentTab === 0 && GlobalStates.launcherSearchText === prefix) {
            Visibilities.setActiveModule("");
            GlobalStates.clearLauncherState();
            return;
        }

        GlobalStates.dashboardCurrentTab = 0;
        
        if (!isActive) {
            Visibilities.setActiveModule("dashboard");
            Qt.callLater(() => {
                GlobalStates.launcherSearchText = prefix;
            });
        } else {
            GlobalStates.launcherSearchText = prefix;
        }
    }

    function toggleAssistant() {
        GlobalStates.toggleAssistant();
    }
    function seekActivePlayer(offset) {
        const player = MprisController.activePlayer;
        if (!player || !player.canSeek) {
            return;
        }

        const maxLength = typeof player.length === "number" && !isNaN(player.length)
                ? player.length
                : Number.MAX_SAFE_INTEGER;
        const clamped = Math.max(0, Math.min(maxLength, player.position + offset));
        player.position = clamped;
    }
}
