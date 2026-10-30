#!/usr/bin/env python3
import subprocess
import sys
import unittest


class TestVPSLXCCLI(unittest.TestCase):
    def test_help(self):
        res = subprocess.run(
            [sys.executable, "scripts/vps_lxc.py", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("VPS LXC Multi-Container Deployment", res.stdout)
        self.assertIn("--auto-split", res.stdout)
        self.assertIn("--ssh-key", res.stdout)
        self.assertIn("--prepare-3xui", res.stdout)

    def test_dry_run_plan(self):
        res = subprocess.run(
            [sys.executable, "scripts/vps_lxc.py", "--ip", "198.51.100.1", "--ssh-pass", "secret", "--dry-run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("vps-01", res.stdout)
        self.assertIn("vps-02", res.stdout)
        self.assertIn("2201", res.stdout)
        self.assertIn("2202", res.stdout)
        self.assertIn("Isolation: Unprivileged LXC", res.stdout)
        self.assertIn("DRY-RUN completed", res.stdout)

    def test_custom_port_and_names(self):
        res = subprocess.run(
            [sys.executable, "scripts/vps_lxc.py", "--ip", "198.51.100.1", "--ssh-port", "2222",
             "--names", "node-a,node-b", "--ssh-base-port", "2300", "--dry-run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("node-a", res.stdout)
        self.assertIn("node-b", res.stdout)
        self.assertIn("2300", res.stdout)
        self.assertIn("2301", res.stdout)


if __name__ == "__main__":
    unittest.main()
