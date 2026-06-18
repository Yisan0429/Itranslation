import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DesktopEnvironmentTests(unittest.TestCase):
    def test_desktop_reports_missing_tkinter_before_gui_import(self):
        script = textwrap.dedent(
            r"""
            import builtins
            import runpy

            real_import = builtins.__import__

            def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "_tkinter" or name == "tkinter" or name.startswith("tkinter."):
                    raise ModuleNotFoundError("No module named '_tkinter'")
                return real_import(name, globals, locals, fromlist, level)

            builtins.__import__ = fake_import
            runpy.run_path("desktop.py", run_name="__main__")
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        combined_output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1)
        self.assertIn("Tkinter", combined_output)
        self.assertIn("python-tk@3.11", combined_output)
        self.assertNotIn("Traceback", combined_output)


if __name__ == "__main__":
    unittest.main()
