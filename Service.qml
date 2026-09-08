import QtQuick
import Quickshell.Io
import "lib/Model.js" as Model

Item {
    id: root
    property var shell: null
    property var manifest: null
    property var snapshot: ({ state: "Setup required", settings: {}, configured: false })
    property var capabilities: ({ installed: false, compatible: false, environment: { outputs: [], addresses: [] } })
    property string error: ""
    property string notice: ""
    property int viewers: 0
    property string action: ""
    property string payload: ""
    property bool enableAfterSave: false
    property bool savingSettings: false
    property int inventoryTicks: 0
    readonly property bool busy: worker.running
    readonly property string helper: Model.localPath(Qt.resolvedUrl("bin/remote-desktopctl"))
    signal passwordGenerated(string password)
    signal configurationSaved()

    function execute(command, data) {
        if (worker.running) return
        if (command !== "status" && command !== "check") {
            error = ""
            notice = ""
        }
        action = command
        payload = data === undefined ? "" : JSON.stringify(data)
        worker.command = ["/usr/bin/python3", helper, command]
        worker.running = true
    }

    function configure(data, enable) {
        if (busy) return
        savingSettings = true
        enableAfterSave = enable
        execute("configure", data)
    }

    function refresh() {
        if (!worker.running) execute("status")
    }

    function completed(result) {
        if (!result.ok) {
            error = String(result.error || "Action failed.").slice(0, 300)
            enableAfterSave = false
            savingSettings = false
            if (action !== "status") Qt.callLater(refresh)
            return
        }
        if (action === "check") {
            capabilities = result
            Qt.callLater(refresh)
        } else if (action === "status") {
            snapshot = result
        } else if (action === "generate-password") {
            passwordGenerated(result.password)
        } else if (action === "export") {
            notice = "Saved to " + result.path
        } else if (action === "configure") {
            configurationSaved()
            if (enableAfterSave) {
                enableAfterSave = false
                Qt.callLater(function() { root.execute("enable") })
            } else {
                notice = "Settings saved. Remote access is off."
                savingSettings = false
                Qt.callLater(refresh)
            }
        } else {
            notice = savingSettings && action === "enable" ? "Settings saved. Starting remote access…" : (result.message || "")
            savingSettings = false
            Qt.callLater(refresh)
        }
    }

    Process {
        id: worker
        stdinEnabled: true
        stdout: StdioCollector { id: output; waitForEnd: true }
        // The helper emits a bounded, redacted JSON result. Do not collect stderr.
        onStarted: {
            if (root.payload !== "") write(root.payload)
            root.payload = ""
            stdinEnabled = false
            deadline.restart()
        }
        onExited: {
            deadline.stop()
            stdinEnabled = true
            root.payload = ""
            root.completed(Model.decode(output.text))
        }
    }

    Timer {
        id: deadline
        interval: 60000
        onTriggered: {
            worker.signal(9)
            root.payload = ""
            root.error = "The action timed out. Refresh status before trying again."
        }
    }

    Timer {
        interval: 3000
        running: root.viewers > 0 || Model.active(root.snapshot.state)
        repeat: true
        onTriggered: {
            root.inventoryTicks++
            if (root.viewers > 0 && root.inventoryTicks % 3 === 0 && !root.busy)
                root.execute("check")
            else root.refresh()
        }
    }

    Component.onCompleted: execute("check")
}
