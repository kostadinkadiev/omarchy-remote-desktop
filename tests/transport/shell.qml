import QtQuick
import Quickshell
import "../../" as Plugin

// Runs under Quickshell (its imports are statically linked into that executable).
// No desktop windows, installation, real secrets or RDP listener are created.
ShellRoot {
    id: root
    property int stage: 0
    property int ticks: 0
    property bool generated: false
    Plugin.Service {
        id: backend
        onPasswordGenerated: function(value) {
            if (value.length < 24) root.fail("Password generation failed")
            root.generated = true
        }
    }
    function fail(message) {
        console.error("TRANSPORT FAIL: " + message)
        Qt.exit(1)
    }
    Timer {
        interval: 100
        running: true
        repeat: true
        onTriggered: {
            root.ticks++
            if (root.ticks > 200) { root.fail("Timed out"); return }
            if (backend.busy) return
            if (root.stage === 0) {
                root.stage = 1
                backend.execute("generate-password")
            } else if (root.stage === 1) {
                if (!root.generated || backend.payload !== "") { root.fail("Secret transport failed"); return }
                root.stage = 2
                backend.configure({ address: "invalid", password: "DO-NOT-ECHO-THIS-TEST-VALUE" }, false)
            } else {
                if (backend.error !== "Choose a local IPv4 address." || backend.payload !== "") {
                    root.fail("Input rejection or secret clearing failed"); return
                }
                console.log("TRANSPORT PASS")
                Qt.quit()
            }
        }
    }
}
