"""Tests for the privacy check's generic patterns (no real personal data here, only fakes)."""
from __future__ import annotations

import unittest

from privacy_check import scan_text


class PrivacyPatternTests(unittest.TestCase):
    def hits(self, text: str, deny: list[str] | None = None) -> list[str]:
        return scan_text(text, "t", deny or [])

    def test_personal_email_caught(self) -> None:
        self.assertTrue(self.hits("contact jane.doe123@example.com"))

    def test_noreply_allowed(self) -> None:
        self.assertFalse(self.hits("someone@users.noreply.github.com"))
        self.assertFalse(self.hits("Co-Authored-By: Claude <noreply@anthropic.com>"))

    def test_hardware_caught(self) -> None:
        for t in ["my MacBook", "32 GB RAM", "an Apple M3 chip", "M4 Pro", "RTX 4090", "a 16-core GPU"]:
            self.assertTrue(self.hits(t), t)

    def test_paths_and_keys_caught(self) -> None:
        for t in ["/Users/someone/repo", "/home/someone/x", "C:\\Users\\x",
                  "sk-abcdefghijklmnopqrstuvwxyz", "ghp_" + "a" * 36, "192.168.1.10",
                  "https://claude.ai/code/session_abc"]:
            self.assertTrue(self.hits(t), t)

    def test_normal_text_passes(self) -> None:
        for t in ["everyday office wear", "home_family scene", "Onam morning at home",
                  "SDXL reads 77 tokens", "version 4.26.0", "CPU, CUDA and Apple MPS",
                  "rural/urban/home/work", "`/Users/...` or `/home/<name>/...`"]:
            self.assertFalse(self.hits(t), t)

    def test_denylist_reported_by_number_only(self) -> None:
        h = self.hits("built by Fakename Person", deny=["fakename person"])
        self.assertEqual(h, ["t:1: matches denylist entry #1"])
        self.assertNotIn("fakename", " ".join(h).lower())


if __name__ == "__main__":
    unittest.main()
