#!/usr/bin/env python3
"""Path guard unit tests."""

import unittest
import os
import tempfile
import shutil
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from core.path_guard import build_path_policy, check_path_access


class DummyConfig:
    def __init__(self, cwd: Path, sandbox_policy: str):
        self.cwd = cwd
        self.sandbox_policy = sandbox_policy


class TestPathGuard(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp())
        self.outside = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)
        shutil.rmtree(self.outside, ignore_errors=True)

    def test_workspace_write_allows_inside(self):
        config = DummyConfig(self.workspace, "workspace_write")
        policy = build_path_policy(config)
        inside_file = self.workspace / "a.txt"

        allowed, reason = check_path_access(policy, inside_file, "read")
        self.assertTrue(allowed, reason)

        allowed, reason = check_path_access(policy, inside_file, "write")
        self.assertTrue(allowed, reason)

    def test_workspace_write_denies_outside(self):
        config = DummyConfig(self.workspace, "workspace_write")
        policy = build_path_policy(config)
        outside_file = self.outside / "b.txt"

        allowed, _ = check_path_access(policy, outside_file, "read")
        self.assertFalse(allowed)

        allowed, _ = check_path_access(policy, outside_file, "write")
        self.assertFalse(allowed)

    def test_full_access_allows_outside(self):
        config = DummyConfig(self.workspace, "none")
        policy = build_path_policy(config)
        outside_file = self.outside / "c.txt"

        allowed, reason = check_path_access(policy, outside_file, "read")
        self.assertTrue(allowed, reason)

        allowed, reason = check_path_access(policy, outside_file, "write")
        self.assertTrue(allowed, reason)

    def test_read_only_denies_write(self):
        config = DummyConfig(self.workspace, "strict")
        policy = build_path_policy(config)
        inside_file = self.workspace / "d.txt"

        allowed, _ = check_path_access(policy, inside_file, "read")
        self.assertTrue(allowed)

        allowed, _ = check_path_access(policy, inside_file, "write")
        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
