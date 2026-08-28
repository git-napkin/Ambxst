pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property string desktopDir: ""
    property bool initialLoadComplete: false
    property string positionsFile: Quickshell.dataPath("desktop-positions.json")
    property int maxRowsHint: 15
    property int maxColumnsHint: 10
    property bool gridReady: false
    property bool positionsLoaded: false

    onMaxRowsHintChanged: checkGridReady()
    onMaxColumnsHintChanged: checkGridReady()
    onPositionsLoadedChanged: checkGridReady()

    function checkGridReady() {
        if (maxRowsHint > 0 && maxColumnsHint > 0 && positionsLoaded && !gridReady) {
            gridReady = true;
            if (tempItems.length > 0)
                finalizeItems();
        }
    }

    property ListModel items: ListModel {
        id: itemsModel
    }

    property var iconPositions: ({})

    function savePositions() {
        positionsView.setText(JSON.stringify(iconPositions, null, 2));
    }

    function loadPositions() {
        positionsView.reload();
    }

    function updateIconPosition(path, gridX, gridY) {
        iconPositions[path] = {
            x: gridX,
            y: gridY
        };
        savePositions();
    }

    function getIconPosition(path) {
        return iconPositions[path] || null;
    }

    function calculateAutoPosition(index) {
        var usedPositions = {};

        for (var key in iconPositions) {
            var pos = iconPositions[key];
            usedPositions[pos.x + "," + pos.y] = true;
        }

        var gridX = 0;
        var gridY = 0;
        var checked = 0;

        while (checked <= index) {
            var posKey = gridX + "," + gridY;
            if (!usedPositions[posKey]) {
                if (checked === index) {
                    return {
                        x: gridX,
                        y: gridY
                    };
                }
                checked++;
            }
            gridY++;
            if (gridY >= maxRowsHint) {
                gridY = 0;
                gridX++;
            }
        }

        return {
            x: gridX,
            y: gridY
        };
    }

    function getDesktopDir() {
        root.desktopDir = Quickshell.env("XDG_DESKTOP_DIR") || (Quickshell.env("HOME") + "/Desktop");
        loadPositions();
        scanDesktop();
        directoryWatcher.path = root.desktopDir;
        directoryWatcher.reload();
    }

    function generateThumbnails() {
        if (desktopDir) {
            thumbnailProcess.running = true;
        }
    }

    function scanDesktop() {
        if (desktopDir) {
            if (scanProcess.running) {
                needsRescan = true;
            } else {
                scanProcess.running = true;
            }
        }
    }

    function executeDesktopFile(filePath) {
        var escapedPath = filePath.replace(/'/g, "'\\''");
        runInActiveWorkspace("gio launch '" + escapedPath + "'");
    }

    function openFile(filePath) {
        var escapedPath = filePath.replace(/'/g, "'\\''");
        runInActiveWorkspace("xdg-open '" + escapedPath + "'");
    }

    function runInActiveWorkspace(command) {
        Quickshell.execDetached(["axctl", "system", "execute", command]);
    }

    function trashFile(filePath) {
        Quickshell.execDetached(["gio", "trash", filePath]);
    }

    function saveAllPositions() {
        iconPositions = {};

        for (var i = 0; i < items.count; i++) {
            var item = items.get(i);
            if (!item.isPlaceholder && item.path) {
                var col = Math.floor(i / maxRowsHint);
                var row = i % maxRowsHint;
                iconPositions[item.path] = {
                    x: col,
                    y: row
                };
            }
        }

        savePositions();
    }

    function moveItem(fromIndex, toIndex) {
        if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0 || fromIndex >= items.count) {
            return;
        }

        if (toIndex >= items.count) {
            toIndex = items.count - 1;
        }

        var targetIsPlaceholder = items.get(toIndex).isPlaceholder === true;

        if (targetIsPlaceholder) {
            var item = items.get(fromIndex);
            items.setProperty(toIndex, "name", item.name);
            items.setProperty(toIndex, "path", item.path);
            items.setProperty(toIndex, "type", item.type);
            items.setProperty(toIndex, "icon", item.icon);
            items.setProperty(toIndex, "isDesktopFile", item.isDesktopFile);
            items.setProperty(toIndex, "isPlaceholder", false);

            items.setProperty(fromIndex, "name", "");
            items.setProperty(fromIndex, "path", "");
            items.setProperty(fromIndex, "type", "placeholder");
            items.setProperty(fromIndex, "icon", "");
            items.setProperty(fromIndex, "isDesktopFile", false);
            items.setProperty(fromIndex, "isPlaceholder", true);

            var col = Math.floor(toIndex / maxRowsHint);
            var row = toIndex % maxRowsHint;
            items.setProperty(toIndex, "gridX", col);
            items.setProperty(toIndex, "gridY", row);
        } else {
            items.move(fromIndex, toIndex, 1);

            var sourceCol = Math.floor(toIndex / maxRowsHint);
            var sourceRow = toIndex % maxRowsHint;
            items.setProperty(toIndex, "gridX", sourceCol);
            items.setProperty(toIndex, "gridY", sourceRow);

            var targetCol = Math.floor(fromIndex / maxRowsHint);
            var targetRow = fromIndex % maxRowsHint;
            items.setProperty(fromIndex, "gridX", targetCol);
            items.setProperty(fromIndex, "gridY", targetRow);
        }

        saveAllPositions();
    }

    function getFileType(fileName) {
        var ext = fileName.toLowerCase().split('.').pop();

        if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext)) {
            return 'image';
        } else if (['mp4', 'webm', 'mov', 'avi', 'mkv', 'mp3', 'wav', 'ogg', 'flac'].includes(ext)) {
            return 'media';
        } else if (['pdf'].includes(ext)) {
            return 'pdf';
        } else if (['txt', 'md', 'log'].includes(ext)) {
            return 'text';
        } else if (['zip', 'tar', 'gz', 'rar', '7z'].includes(ext)) {
            return 'archive';
        } else if (['doc', 'docx', 'odt'].includes(ext)) {
            return 'document';
        }
        return 'file';
    }

    function getIconForType(type) {
        switch (type) {
        case 'folder':
            return 'folder';
        case 'image':
            return 'image-x-generic';
        case 'media':
            return 'video-x-generic';
        case 'pdf':
            return 'application-pdf';
        case 'text':
            return 'text-x-generic';
        case 'archive':
            return 'package-x-generic';
        case 'document':
            return 'x-office-document';
        default:
            return 'text-x-generic';
        }
    }

    property bool _initialized: false

    function initialize() {
        if (_initialized) return;
        _initialized = true;
        Qt.callLater(() => getDesktopDir());
    }

    FileView {
        id: positionsView
        path: root.positionsFile
        printErrors: false

        onLoaded: {
            const raw = text().trim();
            if (raw.length > 0) {
                try {
                    const parsed = JSON.parse(raw);
                    for (const key in root.iconPositions)
                        delete root.iconPositions[key];
                    for (const k in parsed) {
                        root.iconPositions[k] = {
                            x: parsed[k].x,
                            y: parsed[k].y
                        };
                    }
                } catch (e) {
                    console.warn("Error parsing positions file:", e);
                }
            }
            root.positionsLoaded = true;
        }

        onLoadFailed: root.positionsLoaded = true
    }

    FileView {
        id: directoryWatcher
        path: ""
        watchChanges: true
        printErrors: false

        onFileChanged: {
            scanDesktop();
            thumbnailTimer.restart();
        }
    }

    Process {
        id: scanProcess
        running: false
        command: ["python3", decodeURIComponent(Qt.resolvedUrl("../../scripts/desktop_scan.py").toString().replace("file://", "")), root.desktopDir]

        stdout: StdioCollector {
            onStreamFinished: {
                var scanned = [];
                try {
                    scanned = JSON.parse(text.trim() || "[]");
                } catch (e) {
                    console.warn("Error scanning desktop:", e);
                    return;
                }

                for (var i = 0; i < scanned.length; i++) {
                    if (!scanned[i].type) {
                        scanned[i].type = root.getFileType(scanned[i].name);
                        scanned[i].icon = root.getIconForType(scanned[i].type);
                    }
                }

                tempItems = scanned;
                if (gridReady && positionsLoaded)
                    finalizeItems();
            }
        }

        onExited: {
            if (needsRescan) {
                needsRescan = false;
                scanDesktop();
            }
        }
    }

    property var tempItems: []
    property bool needsRescan: false

    function finalizeItems() {
        var allItems = tempItems.slice();

        allItems.sort((a, b) => {
            if (a.sortOrder !== b.sortOrder) {
                return a.sortOrder - b.sortOrder;
            }
            return a.name.localeCompare(b.name);
        });

        items.clear();

        var gridSize = maxRowsHint * maxColumnsHint;

        for (var i = 0; i < gridSize; i++) {
            items.append({
                name: "",
                path: "",
                type: "placeholder",
                icon: "",
                isDesktopFile: false,
                isPlaceholder: true,
                gridX: Math.floor(i / maxRowsHint),
                gridY: i % maxRowsHint
            });
        }

        var usedIndices = {};

        for (var i = 0; i < allItems.length; i++) {
            var item = allItems[i];
            var savedPos = getIconPosition(item.path);
            var gridIndex = -1;

            if (savedPos && savedPos.x < maxColumnsHint && savedPos.y < maxRowsHint) {
                gridIndex = savedPos.x * maxRowsHint + savedPos.y;

                if (usedIndices[gridIndex]) {
                    gridIndex = -1;
                }
            }

            if (gridIndex === -1) {
                for (var j = 0; j < gridSize; j++) {
                    if (!usedIndices[j]) {
                        gridIndex = j;
                        break;
                    }
                }
            }

            if (gridIndex !== -1 && gridIndex < items.count) {
                usedIndices[gridIndex] = true;
                var col = Math.floor(gridIndex / maxRowsHint);
                var row = gridIndex % maxRowsHint;

                items.setProperty(gridIndex, "name", item.name);
                items.setProperty(gridIndex, "path", item.path);
                items.setProperty(gridIndex, "type", item.type);
                items.setProperty(gridIndex, "icon", item.icon);
                items.setProperty(gridIndex, "isDesktopFile", item.isDesktopFile);
                items.setProperty(gridIndex, "isPlaceholder", false);
                items.setProperty(gridIndex, "gridX", col);
                items.setProperty(gridIndex, "gridY", row);
            }
        }

        root.initialLoadComplete = true;
    }

    Process {
        id: thumbnailProcess
        running: false
        command: ["python3", decodeURIComponent(Qt.resolvedUrl("../../scripts/desktop_thumbgen.py").toString().replace("file://", "")), desktopDir, Quickshell.env("HOME") + "/.cache/ambxst+/desktop_thumbnails"]
    }

    Timer {
        id: thumbnailTimer
        interval: 1000
        running: false
        onTriggered: generateThumbnails()
    }

    onDesktopDirChanged: {
        if (desktopDir) {
            thumbnailTimer.running = true;
        }
    }
}
