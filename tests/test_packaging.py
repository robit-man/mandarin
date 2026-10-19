import os
import tempfile
import unittest
from pathlib import Path

from scripts.package_policy import sanitize, violations


class PackagePolicyTests(unittest.TestCase):
    def test_privileged_and_writable_files_are_rejected_and_neutralized(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = root / "helper"
            helper.write_text("#!/bin/sh\nexit 0\n")
            helper.chmod(0o6777)
            os.setxattr(helper, "user.mandarin-test", b"unneeded metadata")
            self.assertTrue(violations(root))
            self.assertEqual(sanitize(root), ["helper"])
            self.assertEqual(helper.stat().st_mode & 0o7777, 0o755)
            self.assertEqual(os.listxattr(helper), [])
            self.assertEqual(violations(root), [])
