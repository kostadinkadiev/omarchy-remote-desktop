import json
from pathlib import Path
import subprocess
import re
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

    def test_setup_never_places_password_in_command_array(self):
        service = (ROOT / "Service.qml").read_text()
        self.assertIn('worker.command = ["/usr/bin/python3", helper, command]', service)
        self.assertIn('write(root.payload)', service)
        self.assertIn('root.payload = ""', service)


if __name__ == "__main__":
    unittest.main()
