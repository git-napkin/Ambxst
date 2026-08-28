pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import qs.config

Singleton {
    id: root

    readonly property string binary: Config.system?.terminal ?? "kitty"
    readonly property bool advanced: Config.system?.terminalAdvanced ?? false
    readonly property string commandTemplate: Config.system?.terminalCommand ?? "$TERMINAL -e $COMMAND"

    function execDetached(shellCmd) {
        if (!binary) {
            console.warn("TerminalService: no terminal configured. Set Config.system.terminal.");
            return;
        }

        if (advanced) {
            const rendered = commandTemplate
                .replace(/\$TERMINAL/g, binary)
                .replace(/\$COMMAND/g, shellCmd);
            Quickshell.execDetached(["bash", "-c", rendered]);
        } else {
            Quickshell.execDetached([binary, "-e", "bash", "-c", shellCmd]);
        }
    }
}
