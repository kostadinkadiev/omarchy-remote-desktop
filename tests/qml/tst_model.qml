import QtQuick
import QtTest
import "../../lib/Model.js" as Model

TestCase {
    name: "RemoteDesktopModel"
    function test_response_limits() {
        verify(!Model.decode("x".repeat(65537)).ok)
        verify(!Model.decode("not json").ok)
        verify(!Model.decode("[]").ok)
        verify(!Model.decode('{"ok":"yes"}').ok)
        verify(Model.decode('{"ok":true,"state":"Off"}').ok)
    }
    function test_text_boundaries() {
        compare(Model.label('<img src="https://example.invalid">&'), 'img src="https://example.invalid"')
        compare(Model.label("x".repeat(1000)).length, 160)
        compare(Model.localPath("file:///tmp/remote%20desktop/bin/helper"), "/tmp/remote desktop/bin/helper")
    }
    function test_observed_states() {
        verify(Model.active("Ready"))
        verify(Model.active("Connected"))
        verify(Model.active("Starting"))
        verify(!Model.active("Error"))
        verify(!Model.active("Off"))
    }
}
