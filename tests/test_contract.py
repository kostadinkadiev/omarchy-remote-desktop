import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_manifest(self):
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["id"], "kokd.remote-desktop")
        for path in manifest["entryPoints"].values():
            self.assertTrue((ROOT / path).is_file())

    def test_all_owned_labels_explicitly_render_plain_text(self):
        # Every Label is owned by this plugin, including labels showing helpers'
        # external data. Native controls receive only static strings or sanitized IDs.
        source = (ROOT / "Panel.qml").read_text()
        labels = re.findall(r"\bLabel\s*\{([^{}]*)\}", source, re.S)
        self.assertGreaterEqual(len(labels), 1)
        self.assertIn("component Caption: Label", source)
        self.assertNotIn("Text.RichText", source)
        self.assertNotIn("Text.AutoText", source)
        for body in labels:
            self.assertIn("textFormat: Text.PlainText", body)

    def test_disconnect_action_is_offered_only_while_connected(self):
        source = (ROOT / "Panel.qml").read_text()
        block = re.search(r"DesktopButton\s*\{[^{}]*execute\(\"disconnect\"\)[^{}]*\}", source, re.S)
        self.assertIsNotNone(block)
        self.assertIn('visible: root.snapshot.state === "Connected"', block.group(0))

    def test_theme_colours_are_addressed_through_the_commons_alias(self):
        # Quickshell ships its own Color value type, which shadows the Commons
        # singleton wherever Commons is imported unqualified. Every colour then
        # silently reads as undefined, so the alias is load-bearing.
        source = (ROOT / "Panel.qml").read_text()
        self.assertIn("import qs.Commons as Commons", source)
        self.assertIn("Commons.Color.", source)
        self.assertEqual(re.findall(r"(?<![.\w])Color\.", source), [])

    def test_virtual_display_controls_are_mutually_exclusive(self):
        source = (ROOT / "Panel.qml").read_text()
        for name, shown in (("monitor", "!root.virtualDisplay"),
                            ("resolution", "root.virtualDisplay"),
                            ("displayScale", "root.virtualDisplay")):
            block = re.search(r"Ui\.Dropdown\s*\{[^{}]*id: " + name + r"\b.*?\n                        \}",
                              source, re.S)
            self.assertIsNotNone(block, name)
            self.assertIn("visible: " + shown, block.group(0))
        self.assertIn('mode: displayMode.value || "monitor"', source)
        # Frame rate applies to both display modes, so it is never hidden.
        block = re.search(r"Ui\.Dropdown\s*\{[^{}]*id: frameRate\b.*?\n                        \}", source, re.S)
        self.assertIsNotNone(block)
        self.assertNotIn("visible:", block.group(0))
        self.assertIn("fps: Number(frameRate.value || 30)", source)

    def test_repository_ships_no_installer_build_recipe_or_privileged_command(self):
        # The backend is installed by Omarchy's own helper, so nothing here should
        # look like an installer, a build recipe, or a privilege escalation. Those
        # are exactly the patterns a marketplace capability scan reports.
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.split()
        for name in tracked:
            self.assertNotIn("PKGBUILD", name)
            self.assertFalse(re.search(r"(^|/)(install|setup|uninstall)[^/]*$", name, re.I), name)
        for name in tracked:
            if name.startswith(".github/"):
                continue
            body = (ROOT / name).read_bytes()
            if b"\x00" in body[:4096]:
                continue
            # Built at runtime so this guard does not match its own source.
            for word in (b"su" + b"do ", b"pk" + b"exec"):
                self.assertNotIn(word, body, f"{name} reintroduces a privilege reference")

    def test_every_text_input_refuses_native_paste(self):
        # Qt's native paste reads the clipboard synchronously in the shared shell
        # with no size or time limit; GuardedField closes every path to it.
        source = (ROOT / "Panel.qml").read_text()
        component = source[source.index("component GuardedField: Ui.TextField {"):]
        component = component[:component.index("\n    component ", 1)]
        for defence in ("readOnly: !active", "ContextMenu.menu: null",
                        "event.matches(StandardKey.Paste)", "event.accepted = true",
                        "event.key === Qt.Key_Menu", "Qt.MiddleButton | Qt.RightButton"):
            self.assertIn(defence, component)
        # No raw native text input may bypass it.
        self.assertEqual(source.count("Ui.TextField {"), 1)
        self.assertNotIn("Ui.NumberField", source)
        self.assertNotIn("TextInput {", source)
        for name in ("username", "password", "port"):
            block = re.search(r"GuardedField\s*\{\s*id: " + name + r"\b(.*?)\n\s*\}", source, re.S)
            self.assertIsNotNone(block, name)
            self.assertIn("active: root.formActive", block.group(1))
        self.assertIn("pasteAllowed: false", re.search(r"id: port\b.*?\n\s*\}", source, re.S).group(0))
        # The Qt-level test exercises the same handler statements.
        mirror = (ROOT / "tests/qml/tst_pasteguard.qml").read_text()
        for statement in ("event.matches(StandardKey.Paste)", "event.key === Qt.Key_Menu",
                          "Qt.MiddleButton | Qt.RightButton", "readOnly: !active"):
            self.assertIn(statement, mirror)

    def test_clipboard_is_only_read_through_the_bounded_helper(self):
        service = (ROOT / "Service.qml").read_text()
        panel = (ROOT / "Panel.qml").read_text()
        self.assertIn('command: ["/usr/bin/python3", root.helper, "clipboard"]', service)
        for source in (service, panel):
            # Writing the clipboard (Copy address) is fine; reading it is the same
            # synchronous fetch as native paste, so every use must be an assignment.
            for use in re.finditer(r"clipboardText", source):
                self.assertRegex(source[use.end():use.end() + 4], r"^\s*=[^=]")
            self.assertNotIn(".paste()", source)

    def install_command(self):
        panel = (ROOT / "Panel.qml").read_text()
        match = re.search(r'"omarchy", "launch", "terminal", "--", "sh", "-c",\s*"([^"]+)"', panel)
        self.assertIsNotNone(match, "install action not found")
        return match.group(1)

    def test_documented_installation_installs_the_backend_first(self):
        # The marketplace lists this plugin as manual setup with a note pointing at
        # these instructions, because adding the plugin alone yields no backend.
        readme = (ROOT / "README.md").read_text()
        section = readme[readme.index("## Install the plugin"):readme.index("## Connect")]
        self.assertLess(section.index("omarchy pkg aur add hypr-rdp"), section.index("omarchy plugin add"))
        self.assertIn("omarchy pkg drop omarchy-remote-desktop-backend", section)
        # A fixed string: nothing external is interpolated into the shell command.
        self.assertEqual(self.install_command(),
                         "omarchy pkg drop omarchy-remote-desktop-backend && omarchy pkg aur add hypr-rdp")

    def test_install_action_replaces_the_former_backend_package_before_installing(self):
        # The package earlier versions built provides hypr-rdp, so Omarchy's helper
        # would otherwise treat the backend as installed and do nothing. Run the
        # exact shipped command against a stand-in omarchy that records its calls.
        with tempfile.TemporaryDirectory() as temporary:
            bindir = Path(temporary)
            log = bindir / "calls"
            fake = bindir / "omarchy"
            fake.write_text('#!/bin/sh\necho "$*" >> "$CALL_LOG"\n'
                            '[ "$1 $2" = "pkg drop" ] && exit "${DROP_STATUS:-0}"\nexit 0\n')
            fake.chmod(0o755)
            env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "CALL_LOG": str(log)}
            subprocess.run(["sh", "-c", self.install_command()], env=env, check=True)
            self.assertEqual(log.read_text().splitlines(),
                             ["pkg drop omarchy-remote-desktop-backend", "pkg aur add hypr-rdp"])
            # If removing the old package fails, nothing is installed over it.
            log.unlink()
            result = subprocess.run(["sh", "-c", self.install_command()], env={**env, "DROP_STATUS": "1"})
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(log.read_text().splitlines(), ["pkg drop omarchy-remote-desktop-backend"])

    def test_setup_never_places_password_in_command_array(self):
        service = (ROOT / "Service.qml").read_text()
        self.assertIn('worker.command = ["/usr/bin/python3", helper, command]', service)
        self.assertIn('write(root.payload)', service)
        self.assertIn('root.payload = ""', service)


if __name__ == "__main__":
    unittest.main()
