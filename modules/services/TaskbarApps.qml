pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.config
import qs.modules.services

Singleton {
    id: root

    function isPinned(appId) {
        const pinnedApps = Config.pinnedApps?.apps || [];
        return pinnedApps.some(id => id.toLowerCase() === appId.toLowerCase());
    }

    function togglePin(appId) {
        let pinnedApps = Config.pinnedApps?.apps || [];
        const normalizedAppId = appId.toLowerCase();

        if (isPinned(appId)) {
            Config.pinnedApps.apps = pinnedApps.filter(id => id.toLowerCase() !== normalizedAppId);
        } else {
            Config.pinnedApps.apps = pinnedApps.concat([appId]);
        }

        Config.savePinnedApps();
    }

    function getDesktopEntry(appId) {
        if (!appId) return null;
        return DesktopEntries.heuristicLookup(appId) || null;
    }

    function launchApp(appId) {
        const entry = getDesktopEntry(appId);
        if (entry) {
            AppSearch.launchApp(entry);
        }
    }

    property var _appCache: ({})
    property var _previousKeys: []
    property var _ignoredRegexKey: null
    property var _ignoredRegexCache: null
    property list<var> apps: []

    Timer {
        id: updateTimer
        interval: 100
        repeat: false
        onTriggered: root._updateApps()
    }

    Connections {
        target: ToplevelManager.toplevels
        function onObjectInsertedPost() {
            updateTimer.restart();
        }
        function onObjectRemovedPost() {
            updateTimer.restart();
        }
    }

    Connections {
        target: Config.pinnedApps ?? null
        function onAppsChanged() {
            updateTimer.restart();
        }
    }

    Connections {
        target: Config.dock ?? null
        function onIgnoredAppRegexesChanged() {
            updateTimer.restart();
        }
    }

    Component.onCompleted: {
        _updateApps();
    }

    function _updateApps() {
        var map = new Map();
        const pinnedApps = Config.pinnedApps?.apps ?? [];
        const ignoredRegexStrings = Config.dock?.ignoredAppRegexes ?? [];

        let ignoredRegexes = root._ignoredRegexCache;
        if (!ignoredRegexes || root._ignoredRegexKey !== ignoredRegexStrings) {
            ignoredRegexes = ignoredRegexStrings.map(pattern => new RegExp(pattern, "i"));
            root._ignoredRegexKey = ignoredRegexStrings;
            root._ignoredRegexCache = ignoredRegexes;
        }

        for (const appId of pinnedApps) {
            const key = appId.toLowerCase();
            if (!map.has(key)) {
                map.set(key, {
                    appId: appId,
                    pinned: true,
                    toplevels: []
                });
            }
        }

        var unpinnedRunningApps = new Map();
        const toplevels = ToplevelManager.toplevels.values;
        for (let i = 0; i < toplevels.length; i++) {
            const toplevel = toplevels[i];
            if (ignoredRegexes.some(re => re.test(toplevel.appId))) continue;

            const key = toplevel.appId.toLowerCase();

            if (map.has(key)) {
                map.get(key).toplevels.push(toplevel);
            } else {
                const existing = unpinnedRunningApps.get(key);
                if (!existing) {
                    unpinnedRunningApps.set(key, {
                        key: key,
                        appId: toplevel.appId,
                        toplevels: [toplevel]
                    });
                } else {
                    existing.toplevels.push(toplevel);
                }
            }
        }

        if (pinnedApps.length > 0 && unpinnedRunningApps.size > 0) {
            map.set("SEPARATOR", { 
                appId: "SEPARATOR", 
                pinned: false, 
                toplevels: [] 
            });
        }

        for (const [appKey, app] of unpinnedRunningApps) {
            map.set(appKey, {
                appId: app.appId,
                pinned: false,
                toplevels: app.toplevels
            });
        }

        var newKeys = Array.from(map.keys());

        for (const oldKey of _previousKeys) {
            if (!map.has(oldKey) && _appCache[oldKey]) {
                _appCache[oldKey].destroy();
                delete _appCache[oldKey];
            }
        }

        var values = [];
        for (const [key, value] of map) {
            if (_appCache[key]) {
                if (!_arraysEqual(_appCache[key].toplevels, value.toplevels)) {
                    _appCache[key].toplevels = value.toplevels;
                }
                if (_appCache[key].pinned !== value.pinned) {
                    _appCache[key].pinned = value.pinned;
                }
                values.push(_appCache[key]);
            } else {
                const entry = appEntryComp.createObject(root, { 
                    appId: value.appId, 
                    toplevels: value.toplevels, 
                    pinned: value.pinned 
                });
                _appCache[key] = entry;
                values.push(entry);
            }
        }

        _previousKeys = newKeys;

        let listChanged = root.apps.length !== values.length;
        if (!listChanged) {
            for (let i = 0; i < root.apps.length; i++) {
                if (root.apps[i] !== values[i]) {
                    listChanged = true;
                    break;
                }
            }
        }
        if (listChanged)
            root.apps = values;
    }

    function _arraysEqual(a, b) {
        if (a === b) return true;
        if (!a || !b || a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) {
            if (a[i] !== b[i]) return false;
        }
        return true;
    }

    component TaskbarAppEntry: QtObject {
        required property string appId
        property var toplevels: []
        property int toplevelCount: toplevels.length
        property bool pinned
    }
    
    Component {
        id: appEntryComp
        TaskbarAppEntry {}
    }
}
