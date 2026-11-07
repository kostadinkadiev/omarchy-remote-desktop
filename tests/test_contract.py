import json
from pathlib import Path
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

    def test_setup_never_places_password_in_command_array(self):
        service = (ROOT / "Service.qml").read_text()
        self.assertIn('worker.command = ["/usr/bin/python3", helper, command]', service)
        self.assertIn('write(root.payload)', service)
        self.assertIn('root.payload = ""', service)


if __name__ == "__main__":
    unittest.main()
