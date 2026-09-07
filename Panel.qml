import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import qs.Commons
import qs.Ui as Ui
import "lib/Model.js" as Model

Ui.Panel {
    id: root
    moduleName: "kokd.remote-desktop"
    manageIpc: false
    readonly property var backend: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
    readonly property var snapshot: backend ? backend.snapshot : ({ state: "Setup required", settings: {}, configured: false })
    readonly property bool busy: backend ? backend.busy : true
    readonly property bool serving: Model.active(snapshot.state)
    readonly property var capabilities: backend ? backend.capabilities : ({ environment: { outputs: [], addresses: [] } })
    property bool editing: false
    property bool instructions: false
    property bool advanced: false
    property bool confirmRemove: false
    property bool counted: false
    property string chosenOutput: ""
    property string chosenAddress: ""

    function restoreChoices() {
        for (var i = 0; i < monitor.count; i++)
            if (monitor.valueAt(i) === chosenOutput) monitor.currentIndex = i
        for (var j = 0; j < network.count; j++)
            if (network.valueAt(j) === chosenAddress) network.currentIndex = j
    }

    function fillSettings() {
        var config = snapshot.settings || {}
        username.text = config.username || Quickshell.env("USER") || "user"
        password.text = ""
        port.value = config.port || 3389
        autostart.checked = config.autostart === true
        audio.checked = config.audio === true
        chosenOutput = config.output || ""
        chosenAddress = config.address || ""
        restoreChoices()
    }

    function save(enable) {
        backend.configure({
            output: monitor.currentValue || "", address: network.currentValue || "",
            username: username.text, password: password.text, port: port.value,
            autostart: autostart.checked, audio: audio.checked
        }, enable)
        password.text = ""
    }

    onOpenedChanged: {
        if (backend && opened && !counted) {
            backend.viewers++
            counted = true
            backend.execute("check")
            fillSettings()
        } else if (backend && !opened && counted) {
            backend.viewers = Math.max(0, backend.viewers - 1)
            counted = false
            password.text = ""
            confirmRemove = false
        }
    }
    Component.onDestruction: if (backend && counted) backend.viewers = Math.max(0, backend.viewers - 1)

    Connections {
        target: root.backend
        function onPasswordGenerated(value) { password.text = value; showPassword.checked = true }
        function onConfigurationSaved() { root.editing = false; password.text = "" }
    }

    Ui.WidgetButton {
        id: button
        bar: root.bar
        text: "󰢹"
        active: root.serving
        tooltipText: "Remote Desktop · " + root.snapshot.state
        onPressed: root.toggle()
    }

    Ui.KeyboardPanel {
        id: popup
        anchorItem: button
        owner: root
        bar: root.bar
        open: root.opened
        focusTarget: content
        contentWidth: popup.fittedContentWidth(Style.space(360))
        contentHeight: popup.fittedContentHeight(column.implicitHeight, Style.space(620))

        Pane {
            id: content
            objectName: "remoteDesktopContent"
            anchors.fill: parent
            padding: 0
            background: null
            palette.window: Color.background
            palette.windowText: Color.foreground
            palette.base: Color.background
            palette.text: Color.foreground
            palette.button: Qt.lighter(Color.background, 1.5)
            palette.buttonText: Color.foreground
            palette.highlight: Color.accent
            palette.highlightedText: Color.background
            Keys.onEscapePressed: root.close()

            ScrollView {
                anchors.fill: parent
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    id: column
                    width: content.width
                    spacing: Style.space(10)

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "Remote Desktop"
                            textFormat: Text.PlainText
                            color: Color.foreground
                            font.bold: true
                            font.pixelSize: Style.font.subtitle
                            Layout.fillWidth: true
                        }
                        Switch {
                            id: access
                            Accessible.name: "Enable Remote Desktop"
                            checked: root.serving
                            enabled: !root.busy && root.snapshot.configured
                            onClicked: root.backend.execute(checked ? "enable" : "disable")
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        text: root.snapshot.state + " · Experimental"
                        textFormat: Text.PlainText
                        color: Color.foreground
                        opacity: 0.7
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: (root.backend ? root.backend.error : "") || root.snapshot.error || ""
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        color: Color.urgent
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: root.backend ? root.backend.notice : ""
                        textFormat: Text.PlainText
                        wrapMode: Text.WrapAnywhere
                        color: Color.foreground
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: !root.capabilities.compatible
                        Label {
                            Layout.fillWidth: true
                            text: root.capabilities.message || "Checking compatibility…"
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                        }
                        RowLayout {
                            Button {
                                text: "Install experimental backend"
                                enabled: !root.busy
                                onClicked: Quickshell.execDetached(["omarchy", "launch", "terminal", "--", "/usr/bin/python3", Model.localPath(Qt.resolvedUrl("bin/install-backend"))])
                            }
                            Button { text: "Check again"; enabled: !root.busy; onClicked: root.backend.execute("check") }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.snapshot.configured && !root.editing
                        Label {
                            text: Model.label(root.snapshot.settings.output)
                            textFormat: Text.PlainText
                            color: Color.foreground
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                Layout.fillWidth: true
                                text: root.snapshot.address || ""
                                textFormat: Text.PlainText
                                color: Color.foreground
                                font.bold: true
                                wrapMode: Text.WrapAnywhere
                            }
                            Button { text: "Copy"; onClicked: Quickshell.clipboardText = root.snapshot.address || "" }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                Layout.fillWidth: true
                                text: "Username: " + (root.snapshot.settings.username || "")
                                textFormat: Text.PlainText
                                color: Color.foreground
                            }
                            Button { text: "Copy"; onClicked: Quickshell.clipboardText = root.snapshot.settings.username || "" }
                        }
                        Button { text: "Windows connection file"; enabled: !root.busy; onClicked: root.backend.execute("export") }
                        RowLayout {
                            Button { text: "How to connect"; onClicked: root.instructions = !root.instructions }
                            Button {
                                text: "Settings"
                                enabled: !root.busy
                                onClicked: { root.fillSettings(); root.editing = true; root.backend.execute("check") }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: !root.snapshot.configured || root.editing
                        enabled: !root.busy
                        Label { text: "1. Choose what to share"; textFormat: Text.PlainText; color: Color.foreground }
                        ComboBox {
                            id: monitor
                            Layout.fillWidth: true
                            Accessible.name: "Monitor to share"
                            model: root.capabilities.environment.outputs || []
                            textRole: "name"
                            valueRole: "name"
                            onActivated: root.chosenOutput = currentValue
                            onModelChanged: Qt.callLater(root.restoreChoices)
                        }
                        ComboBox {
                            id: network
                            Layout.fillWidth: true
                            Accessible.name: "Private network address"
                            model: root.capabilities.environment.addresses || []
                            textRole: "address"
                            valueRole: "address"
                            onActivated: root.chosenAddress = currentValue
                            onModelChanged: Qt.callLater(root.restoreChoices)
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: monitor.count === 0 || network.count === 0
                            text: "Connect a physical monitor and a private LAN or VPN, then refresh."
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                        }
                        Label { text: "2. Create RDP credentials"; textFormat: Text.PlainText; color: Color.foreground }
                        TextField {
                            id: username
                            Layout.fillWidth: true
                            placeholderText: "Username"
                            maximumLength: 64
                            Accessible.name: "RDP username"
                        }
                        TextField {
                            id: password
                            Layout.fillWidth: true
                            placeholderText: root.snapshot.configured ? "New password (blank keeps current)" : "Password · at least 16 characters"
                            maximumLength: 256
                            echoMode: showPassword.checked ? TextInput.Normal : TextInput.Password
                            inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                            Accessible.name: "RDP password"
                        }
                        RowLayout {
                            Button { text: "Generate password"; onClicked: root.backend.execute("generate-password") }
                            CheckBox { id: showPassword; text: "Show" }
                        }
                        Label {
                            Layout.fillWidth: true
                            text: "Save these credentials before enabling. They are separate from your Linux login."
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                            opacity: 0.7
                        }
                        Button { text: root.advanced ? "Fewer settings" : "More settings"; onClicked: root.advanced = !root.advanced }
                        ColumnLayout {
                            visible: root.advanced
                            Layout.fillWidth: true
                            RowLayout {
                                Label { text: "Port"; textFormat: Text.PlainText; color: Color.foreground }
                                SpinBox { id: port; from: 1024; to: 65535; value: 3389; editable: true; Accessible.name: "RDP port" }
                            }
                            CheckBox { id: autostart; text: "Start after desktop login" }
                            CheckBox { id: audio; text: "Send audio to remote computer" }
                        }
                        Label {
                            Layout.fillWidth: true
                            text: "Your screen stays visible locally. Clipboard contents are shared. Normal locking and sleep still apply. Windows and Mac acceptance tests are pending."
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                        }
                        RowLayout {
                            Button {
                                text: root.editing ? "Save and enable" : "Enable Remote Desktop"
                                enabled: root.capabilities.compatible && monitor.count > 0 && network.count > 0
                                onClicked: root.save(true)
                            }
                            Button { visible: root.editing; text: "Save off"; onClicked: root.save(false) }
                        }
                        Button { visible: root.editing; text: "Cancel"; onClicked: { password.text = ""; root.editing = false } }
                    }

                    ColumnLayout {
                        visible: root.instructions
                        Layout.fillWidth: true
                        Label {
                            Layout.fillWidth: true
                            text: "Windows: open Remote Desktop Connection (mstsc), enter the address above and your RDP credentials. You can also open the exported connection file.\n\nMac: install Microsoft Windows App, choose Add PC and enter the address and RDP credentials. Mac compatibility is not yet verified.\n\nConnect both computers to the same LAN or private VPN. Do not forward the RDP port on your router. A sleeping or logged-out computer cannot be reached. Server Mode is an optional companion for sleep protection.\n\nIf Omarchy is locked, its normal unlock is still required after RDP authentication."
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                        }
                        Label {
                            Layout.fillWidth: true
                            text: "Before accepting the first certificate, compare its SHA-256 fingerprint:\n" + (root.snapshot.fingerprint || "Available after setup")
                            textFormat: Text.PlainText
                            wrapMode: Text.WrapAnywhere
                            color: Color.foreground
                        }
                    }

                    RowLayout {
                        Button { text: "Refresh"; enabled: !root.busy; onClicked: root.backend.execute("check") }
                        Button {
                            visible: root.editing
                            text: root.confirmRemove ? "Confirm removal" : "Remove setup"
                            enabled: !root.busy
                            onClicked: {
                                if (!root.confirmRemove) { root.confirmRemove = true; return }
                                root.backend.execute("remove")
                                root.editing = false
                                root.confirmRemove = false
                            }
                        }
                    }
                }
            }
        }
    }
}
