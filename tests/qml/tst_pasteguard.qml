import QtQuick
import QtTest

// Mirrors the handlers of Panel.qml's GuardedField on a plain TextInput, which is
// what TextField is built on, so the Qt behaviour they rely on is checked wherever
// Qt runs. test_contract.py pins both copies to the same statements.
Item {
    width: 400
    height: 200

    TextInput {
        id: control
        width: 200
        height: 30
    }

    TextInput {
        id: guarded
        y: 60
        width: 200
        height: 30
        property bool active: true
        property bool pasteAllowed: true
        property int requests: 0
        property int swallowed: 0
        readOnly: !active
        Keys.onPressed: function(event) {
            if (event.matches(StandardKey.Paste)) {
                event.accepted = true
                if (guarded.pasteAllowed && !guarded.readOnly) guarded.requests++
            } else if (event.key === Qt.Key_Menu) {
                event.accepted = true
            }
        }
        MouseArea {
            anchors.fill: parent
            z: 2
            acceptedButtons: Qt.MiddleButton | Qt.RightButton
            onPressed: function(mouse) { mouse.accepted = true; guarded.swallowed++ }
        }
    }

    TestCase {
        name: "PasteGuard"
        when: windowShown

        function init() {
            guarded.active = true
            guarded.pasteAllowed = true
            guarded.text = ""
            guarded.requests = 0
            guarded.swallowed = 0
        }

        function seedClipboard(text) {
            control.text = text
            control.selectAll()
            control.copy()
            control.text = ""
            control.forceActiveFocus()
            keySequence(StandardKey.Paste)
            if (control.text !== text) skip("No usable clipboard on this platform")
        }

        function test_native_paste_shortcuts_are_refused_and_a_bounded_paste_requested() {
            seedClipboard("from-clipboard")
            guarded.forceActiveFocus()
            keySequence(StandardKey.Paste)
            compare(guarded.text, "")
            compare(guarded.requests, 1)
            keyClick(Qt.Key_Insert, Qt.ShiftModifier)
            compare(guarded.text, "")
            keyClick(Qt.Key_Menu)
            compare(guarded.text, "")
        }

        function test_field_that_disallows_paste_requests_nothing() {
            seedClipboard("from-clipboard")
            guarded.pasteAllowed = false
            guarded.forceActiveFocus()
            keySequence(StandardKey.Paste)
            compare(guarded.text, "")
            compare(guarded.requests, 0)
        }

        function test_inactive_field_is_read_only_and_requests_nothing() {
            guarded.active = false
            guarded.forceActiveFocus()
            keySequence(StandardKey.Paste)
            verify(guarded.readOnly)
            compare(guarded.requests, 0)
        }

        function test_middle_and_right_buttons_never_reach_the_input() {
            seedClipboard("from-clipboard")
            mouseClick(guarded, 20, 10, Qt.MiddleButton)
            mouseClick(guarded, 20, 10, Qt.RightButton)
            compare(guarded.swallowed, 2)
            compare(guarded.text, "")
        }
    }
}
