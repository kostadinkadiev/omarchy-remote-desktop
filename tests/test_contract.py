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
        self.assertGreater(len(labels), 10)
        for body in labels:
            self.assertIn("textFormat: Text.PlainText", body)

    def test_setup_never_places_password_in_command_array(self):
        service = (ROOT / "Service.qml").read_text()
        self.assertIn('worker.command = ["/usr/bin/python3", helper, command]', service)
        self.assertIn('write(root.payload)', service)
        self.assertIn('root.payload = ""', service)


if __name__ == "__main__":
    unittest.main()
