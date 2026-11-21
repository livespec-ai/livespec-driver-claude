"""Literal shell assignments are the only values sanctioned apply expands."""

from __future__ import annotations

import sys
from pathlib import Path

__all__: list[str] = []

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"


def test_literal_expansion_is_scoped_and_invalidates_unsafe_values() -> None:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    from _sanctioned_apply import _expanded, remember_literals

    variables = {"PB": ["old.yml"]}
    remember_literals(tokens=["A=ansible/window.yml -e action=cordon"], variables=variables)
    assert _expanded(tokens=["$A", "literal"], variables=variables) == [
        "ansible/window.yml",
        "-e",
        "action=cordon",
        "literal",
    ]

    remember_literals(tokens=["PB=$(printf unsafe.yml)"], variables=variables)
    assert "PB" not in variables

    variables["BROKEN"] = ["old.yml"]
    remember_literals(tokens=['BROKEN=unterminated"'], variables=variables)
    assert "BROKEN" not in variables
