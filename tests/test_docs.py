#!/usr/bin/env python3
"""Docs are part of the skill: agents follow them, so losing a section breaks real use."""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("path,min_lines", [("SKILL.md", 150), ("README.md", 120), ("i18n/SKILL_zh.md", 120),
                                            ("i18n/README_zh.md", 100), ("docs/host-requirements.md", 100),
                                            ("docs/software-versions.md", 25)])
def test_docs_are_not_truncated(path, min_lines):
    assert len(read(path).splitlines()) >= min_lines


@pytest.mark.parametrize("text", ["## Reboot Rules", "--check-host", "--traffic-limit-gb", "docs/software-versions.md"])
def test_skill_keeps_its_key_sections(text):
    assert text in read("SKILL.md")


def test_agent_skill_entry_is_the_same_file():
    assert read(".agents/skills/vps-lxc-creator/SKILL.md") == read("SKILL.md")
