import QtQuick
import QtQuick.Window
import Quickshell
import "." as Plugin

ShellRoot {
    id: root
    property int stage: 0
    property QtObject backend: QtObject {
        property bool busy: false
        property int viewers: 0
        property string error: ""
        property string notice: ""
        property var snapshot: ({ state: "Setup required", configured: false, settings: {} })
        property var capabilities: ({ compatible: true, installed: true, environment: {
            outputs: [{ name: "DP-1", label: "Main monitor" }],
            addresses: [{ address: "192.168.1.50", interface: "eth0" }]
        } })
        signal passwordGenerated(string password)
        signal configurationSaved()
        function execute(command) {}
        function configure(data, enable) {}
    }
    property QtObject shell: QtObject {
        function serviceFor(name) { return root.backend }
    }
    property QtObject bar: QtObject {
        property var shell: root.shell
        property color foreground: "#cacccc"
        property color barForeground: "#cacccc"
        property color urgent: "#a55555"
        property color background: "#101315"
        property bool vertical: false
        property bool foregroundAnimationEnabled: false
        property string fontFamily: "monospace"
        property int barSize: 32
        property string position: "top"
        property var activePopout: null
        function requestPopout(owner) { activePopout = owner }
        function releasePopout(owner) { activePopout = null }
        function hideTooltip(owner) {}
        function showTooltip(owner, text) {}
    }
    Window {
        id: window
        visible: true
        width: 800
        height: 800
        color: "#101315"
        Plugin.Panel {
            id: panel
            bar: root.bar
        }
    }
    Timer {
        interval: 350
        running: true
        repeat: true
        onTriggered: {
            root.stage++
            if (root.stage === 1) panel.open()
            else if (root.stage === 2) {
                if (panel.implicitWidth <= 0 || panel.implicitHeight <= 0 || !panel.opened) { Qt.exit(1); return }
                panel.close()
                root.backend.snapshot = { state: "Off", configured: true,
                    address: "192.168.1.50:3389", settings: { output: "DP-1", username: "user" } }
                panel.open()
            } else if (root.stage === 3) {
                panel.instructions = true
                panel.editing = true
            } else {
                panel.close()
                if (root.backend.viewers !== 0) { Qt.exit(1); return }
                console.log("PANEL PASS")
                Qt.quit()
            }
        }
    }
}
