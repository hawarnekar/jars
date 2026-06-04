"""jars_tui — Textual front-end for the jars_lib library."""

from __future__ import annotations

__all__ = ["main"]


def main() -> int:  # thin re-export so `jars` works without importing textual eagerly
    from .app import main as _main

    return _main()
