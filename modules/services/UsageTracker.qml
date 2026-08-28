pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property string usageFilePath: (Quickshell.env("XDG_CACHE_HOME") || (Quickshell.env("HOME") + "/.cache")) + "/ambxst+/usage.json"
    property var usageData: ({})
    property bool dataLoaded: false

    signal usageDataReady

    readonly property int maxBoostScore: 200
    readonly property int dayInMs: 86400000

    FileView {
        id: usageFile
        path: root.usageFilePath
        printErrors: false
        onLoaded: root.loadUsageData()
        onLoadFailed: {
            root.usageData = {};
            root.dataLoaded = true;
            root.usageDataReady();
        }
    }

    function loadUsageData() {
        try {
            const data = usageFile.text();
            if (!data || data.trim() === "") {
                root.usageData = {};
            } else {
                root.usageData = JSON.parse(data);
            }
        } catch (e) {
            console.warn("UsageTracker: Failed to parse usage.json:", e);
            root.usageData = {};
        }
        root.dataLoaded = true;
        root.usageDataReady();
    }

    function saveUsageData() {
        usageFile.setText(JSON.stringify(usageData, null, 2));
    }

    function recordUsage(appId) {
        if (!appId)
            return;

        var now = Date.now();

        if (usageData[appId]) {
            usageData[appId].count++;
            usageData[appId].lastUsed = now;
        } else {
            usageData[appId] = {
                count: 1,
                lastUsed: now
            };
        }

        usageData = usageData;
        saveUsageData();
    }

    function getUsageScore(appId) {
        if (!appId || !usageData[appId])
            return 0;

        var data = usageData[appId];
        var daysSinceLastUse = (Date.now() - data.lastUsed) / dayInMs;
        var timeBoost = maxBoostScore * Math.exp(-daysSinceLastUse / 7);
        var frequencyScore = Math.log(data.count + 1) * 20;
        return timeBoost + frequencyScore;
    }

    function getTopApps(limit) {
        if (!limit)
            limit = 10;

        var apps = [];
        for (var appId in usageData) {
            apps.push({
                appId: appId,
                score: getUsageScore(appId),
                count: usageData[appId].count,
                lastUsed: usageData[appId].lastUsed
            });
        }

        apps.sort(function (a, b) {
            return b.score - a.score;
        });

        return apps.slice(0, limit);
    }

    function pruneOldEntries() {
        var now = Date.now();
        var ninetyDaysInMs = dayInMs * 90;
        var changed = false;

        for (var appId in usageData) {
            if (now - usageData[appId].lastUsed > ninetyDaysInMs) {
                delete usageData[appId];
                changed = true;
            }
        }

        if (changed) {
            usageData = usageData;
            saveUsageData();
        }
    }
}
