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
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    readonly property var backend: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
    readonly property var snapshot: backend ? backend.snapshot : ({ state: "Setup required", settings: {}, configured: false })
    readonly property bool busy: backend ? backend.busy : true
    readonly property bool serving: Model.active(snapshot.state)
    readonly property var capabilities: backend ? backend.capabilities : ({ environment: { outputs: [], addresses: [] } })
    property bool editing: false
    property bool instructions: false
    property bool confirmRemove: false
    property bool counted: false
    property string chosenOutput: ""
    property string chosenAddress: ""

    function restoreChoices() {
        if (!chosenOutput && monitor.options.length) chosenOutput = monitor.options[0].value
        if (!chosenAddress && network.options.length) chosenAddress = network.options[0].value
    }

    function fillSettings() {
        var config = snapshot.settings || {}
        username.text = config.username || Quickshell.env("USER") || "user"
        password.text = ""
        port.value = config.port || 3389
        audio.checked = config.audio === true
        chosenOutput = config.output || ""
        chosenAddress = config.address || ""
        restoreChoices()
    }

    function save(enable) {
        backend.configure({
            output: monitor.value || "", address: network.value || "",
            username: username.text, password: password.text, port: port.value,
            audio: audio.checked
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
            editing = false
            instructions = false
        }
    }
    Component.onDestruction: if (backend && counted) backend.viewers = Math.max(0, backend.viewers - 1)

    Connections {
        target: root.backend
        function onPasswordGenerated(value) { password.text = value; showPassword.checked = true }
        function onConfigurationSaved() { root.editing = false; password.text = "" }
    }

    Ui.BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "󰢹"
        active: root.serving
        activeColor: Color.accent
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
                        Caption {
                            text: root.editing ? "Remote Desktop settings" : "Remote Desktop"
                            textFormat: Text.PlainText
                            color: Color.foreground
                            font.bold: true
                            font.pixelSize: Style.font.subtitle
                            Layout.fillWidth: true
                        }
                        Ui.ToggleSwitch {
                            id: access
                            visible: !root.editing
                            Accessible.name: "Enable Remote Desktop and resume after desktop login"
                            checked: root.serving
                            enabled: !root.busy && root.snapshot.configured
                            onToggled: root.backend.execute(checked ? "disable" : "enable")
                        }
                    }
                    Caption {
                        Layout.fillWidth: true
                        visible: !root.editing
                        text: root.snapshot.state === "Connected" ? "Connected"
                            : root.snapshot.state === "Ready" ? "Ready to connect"
                            : root.snapshot.state === "Off" ? "Remote access is off" : root.snapshot.state
                        textFormat: Text.PlainText
                        color: Color.foreground
                        opacity: 0.7
                    }
                    Caption {
                        Layout.fillWidth: true
                        visible: !root.editing
                        text: "When on, resumes after desktop login."
                        opacity: 0.6
                        wrapMode: Text.Wrap
                    }
                    Caption {
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: (root.backend ? root.backend.error : "") || root.snapshot.error || ""
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        color: Color.urgent
                    }
                    Caption {
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
                        Caption {
                            Layout.fillWidth: true
                            text: root.capabilities.message || "Checking compatibility…"
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                        }
                        RowLayout {
                            DesktopButton {
                                text: "Install RDP backend"
                                enabled: !root.busy
                                onClicked: Quickshell.execDetached(["omarchy", "launch", "terminal", "--", "/usr/bin/python3", Model.localPath(Qt.resolvedUrl("bin/install-backend"))])
                            }
                            DesktopButton { text: "Check again"; enabled: !root.busy; onClicked: root.backend.execute("check") }
                        }
                    }

                    Ui.PanelSeparator { Layout.fillWidth: true }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Style.space(8)
                        visible: root.snapshot.configured && !root.editing
                        Caption {
                            text: "CONNECT TO THIS COMPUTER"
                            font.pixelSize: Style.font.caption
                            opacity: 0.6
                            textFormat: Text.PlainText
                            color: Color.foreground
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Caption {
                                Layout.fillWidth: true
                                text: root.snapshot.address || ""
                                textFormat: Text.PlainText
                                color: Color.foreground
                                font.bold: true
                                wrapMode: Text.WrapAnywhere
                            }
                            DesktopButton {
                                text: copied ? "Copied" : "Copy address"
                                property bool copied: false
                                onClicked: { Quickshell.clipboardText = root.snapshot.address || ""; copied = true; copyReset.restart() }
                                Timer { id: copyReset; interval: 1800; onTriggered: parent.copied = false }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Caption {
                                Layout.fillWidth: true
                                text: "Username: " + (root.snapshot.settings.username || "")
                                textFormat: Text.PlainText
                                color: Color.foreground
                            }

                        }
                        Caption {
                            Layout.fillWidth: true
                            text: "Sharing " + (root.snapshot.settings.output || "")
                            visible: root.serving
                            opacity: 0.6
                        }
                        RowLayout {
                            DesktopButton { text: root.instructions ? "Hide connection help" : "How to connect"; onClicked: root.instructions = !root.instructions }
                            DesktopButton {
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
                        Caption { text: "Share this desktop"; textFormat: Text.PlainText; color: Color.foreground }
                        Ui.Dropdown {
                            id: monitor
                            Layout.fillWidth: true
                            label: "Monitor"
                            options: (root.capabilities.environment.outputs || []).map(function(item) { return { value: item.name, label: item.name } })
                            value: root.chosenOutput
                            onChanged: function(value) { root.chosenOutput = value }
                            onOptionsChanged: Qt.callLater(root.restoreChoices)
                        }
                        Ui.Dropdown {
                            id: network
                            Layout.fillWidth: true
                            label: "Network address"
                            options: (root.capabilities.environment.addresses || []).map(function(item) { return { value: item.address, label: item.address } })
                            value: root.chosenAddress
                            onChanged: function(value) { root.chosenAddress = value }
                            onOptionsChanged: Qt.callLater(root.restoreChoices)
                        }
                        Caption {
                            Layout.fillWidth: true
                            visible: monitor.options.length === 0 || network.options.length === 0
                            text: "Connect a physical monitor and a private LAN or VPN, and they will appear here."
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                        }
                        Caption { text: root.snapshot.configured ? "Login details" : "Create login details"; textFormat: Text.PlainText; color: Color.foreground }
                        Ui.TextField {
                            id: username
                            Layout.fillWidth: true
                            placeholderText: "Username"
                            maximumLength: 64
                            Accessible.name: "RDP username"
                        }
                        Ui.TextField {
                            id: password
                            Layout.fillWidth: true
                            placeholderText: root.snapshot.configured ? "New password (blank keeps current)" : "Password · at least 16 characters"
                            maximumLength: 256
                            echoMode: showPassword.checked ? TextInput.Normal : TextInput.Password
                            inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                            Accessible.name: "RDP password"
                        }
                        RowLayout {
                            DesktopButton { text: "Generate password"; onClicked: root.backend.execute("generate-password") }
                            Ui.Toggle { id: showPassword; label: "Show"; Accessible.name: "Show password"; Layout.fillWidth: true; onClicked: checked = !checked }
                        }
                        Caption {
                            Layout.fillWidth: true
                            visible: !root.snapshot.configured
                            text: "Save these credentials before enabling. They are separate from your Linux login."
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                            opacity: 0.7
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            RowLayout {
                                Caption { text: "Port"; textFormat: Text.PlainText; color: Color.foreground }
                                Ui.NumberField { id: port; from: 1024; to: 65535; value: 3389; onModified: function(value) { port.value = value }; Accessible.name: "RDP port" }
                            }
                            Ui.Toggle { id: audio; label: "Share audio"; description: "Play on this computer and the remote device"; Layout.fillWidth: true; onClicked: checked = !checked }
                        }
                        Caption {
                            Layout.fillWidth: true
                            visible: !root.snapshot.configured
                            text: "Your screen and clipboard are shared. Locking and sleep still apply."
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                        }
                        Caption {
                            Layout.fillWidth: true
                            visible: root.editing
                            text: root.serving ? "Saving restarts sharing and disconnects the current session." : "Saving keeps remote access off."
                            wrapMode: Text.Wrap
                            opacity: 0.7
                        }
                        RowLayout {
                            DesktopButton {
                                text: root.editing ? "Save settings" : "Enable Remote Desktop"
                                enabled: root.capabilities.compatible === true && monitor.options.length > 0 && network.options.length > 0
                                onClicked: root.save(root.editing ? root.serving : true)
                            }
                            DesktopButton { visible: root.editing; text: "Cancel"; onClicked: { password.text = ""; root.editing = false } }
                        }
                    }

                    ColumnLayout {
                        visible: root.instructions && !root.editing
                        Layout.fillWidth: true
                        DesktopButton { text: "Save connection file (.rdp)"; enabled: !root.busy; onClicked: root.backend.execute("export") }
                        Caption {
                            Layout.fillWidth: true
                            text: "Android: connect Tailscale when using a Tailscale address, then add this PC in Windows App.\n\nWindows: open Remote Desktop Connection (mstsc), enter the address above and your RDP credentials. You can also open the exported connection file.\n\nMac: in Microsoft Windows App, import the .rdp file or choose Add PC and enter the address and RDP credentials.\n\nConnect both computers to the same LAN or private VPN. Do not forward the RDP port on your router. A sleeping or logged-out computer cannot be reached. Server Mode is an optional companion for sleep protection.\n\nIf Omarchy is locked, its normal unlock is still required after RDP authentication."
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Color.foreground
                        }
                        Caption {
                            Layout.fillWidth: true
                            text: "Before accepting the first certificate, compare its SHA-256 fingerprint:\n" + (root.snapshot.fingerprint || "Available after setup")
                            textFormat: Text.PlainText
                            wrapMode: Text.WrapAnywhere
                            color: Color.foreground
                        }
                    }

                    RowLayout {
                        visible: root.editing
                        DesktopButton {
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
    component DesktopButton: Ui.Button {
        focusable: true
        bordered: false
    }

    component Caption: Label {
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        textFormat: Text.PlainText
        color: Color.foreground
    }

}
