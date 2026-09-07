from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_installer_refuses_background_execution(self):
        result = subprocess.run([sys.executable, str(ROOT / "bin/install-backend")],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("terminal", result.stderr)

    def test_recipe_binds_source_and_dependencies(self):
        recipe = (ROOT / "backend/PKGBUILD").read_text()
        self.assertRegex(recipe, r"_commit=[0-9a-f]{40}\n")
        self.assertRegex(recipe, r"sha256sums=\('[0-9a-f]{64}'\)")
        self.assertIn("cargo fetch --locked", recipe)
        self.assertIn("cargo build --frozen --release", recipe)
        self.assertNotIn("SKIP", recipe)
        self.assertNotIn("systemctl", recipe)


if __name__ == "__main__":
    unittest.main()
